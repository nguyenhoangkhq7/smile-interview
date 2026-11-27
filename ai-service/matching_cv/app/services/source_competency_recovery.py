"""Recover named engineering competencies from attributable CV and JD clauses."""

from collections import defaultdict
from dataclasses import dataclass
import re

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.services.section_tagger import find_section_spans
from matching_cv.research.data.canonical_skill_normalizer import ENGINEERING_COMPETENCY_ALIASES


@dataclass(frozen=True)
class CompetencyRule:
    skill_id: str
    mention: re.Pattern[str]
    activity: re.Pattern[str]


def _rule(skill_id: str, mention: str, activity: str) -> CompetencyRule:
    return CompetencyRule(skill_id, re.compile(rf"\b(?:{mention})\b", re.I), re.compile(rf"\b(?:{activity})\b", re.I))


_OWNERSHIP = r"own(?:s|ed|ing)?|led|lead(?:s|ing)?|responsible\s+for"
_BUILD = r"built|build(?:s|ing)?|creat(?:e|es|ed|ing)|design(?:s|ed|ing)?|develop(?:s|ed|ing)?|implement(?:s|ed|ing)?"
_OPTIMIZE = r"optimi[sz](?:e|es|ed|ing)|improv(?:e|es|ed|ing)|tun(?:e|es|ed|ing)|measur(?:e|es|ed|ing)|monitor(?:s|ed|ing)?"
_DEPLOY = r"deploy(?:s|ed|ing)?"
_PRODUCTIONIZE = r"productioni[sz](?:e|es|ed|ing)"
_MODELS = r"(?:(?:ml|machine[\s-]+learning)\s+)?models?"
_DEPLOYED_MODEL = (
    rf"(?:{_DEPLOY})\s+(?:trained|ml|machine[\s-]+learning)\s+models?"
    rf"|(?:{_DEPLOY})\s+(?:(?!\b(?:and|or|data\s+models?)\b)[^.;!?•]){{0,72}}?\bmodels?\b"
    r"(?:\s*\([^()\n]{0,48}\))?\s+(?:to|in|into)\s+production"
)
_RULES = (
    _rule("data-modeling",
          r"data[\s-]+modell?ing|(?:design(?:s|ed|ing)?|creat(?:e|es|ed|ing)|built|build(?:s|ing)?)"
          r"\s+(?:relational\s+)?data\s+models?", f"{_OWNERSHIP}|{_BUILD}"),
    _rule("query-performance",
          r"(?:sql\s+|database\s+)?query[\s-]+performance|performance\s+of\s+(?:(?:sql|database)\s+)?queries",
          f"{_OWNERSHIP}|{_OPTIMIZE}|maintain(?:s|ed|ing)?"),
    _rule("design-system", r"design[\s-]+systems?",
          f"{_OWNERSHIP}|{_BUILD}|extend(?:s|ed|ing)?|maintain(?:s|ed|ing)?|contribut(?:e|es|ed|ing)\\s+to"),
    _rule("core-web-vitals", r"core[\s-]+web[\s-]+vitals?",
          f"{_OWNERSHIP}|{_OPTIMIZE}|track(?:s|ed|ing)?|diagnos(?:e|es|ed|ing)"),
    _rule("data-quality", r"data[\s-]+quality(?:[\s-]+(?:checks?|assurance|validation|engineering|monitoring))?",
          f"{_OWNERSHIP}|{_BUILD}|{_OPTIMIZE}|validat(?:e|es|ed|ing)|enforc(?:e|es|ed|ing)|test(?:s|ed|ing)?"),
    _rule("model-deployment",
          rf"{_MODELS}[\s-]+deployments?|(?:{_PRODUCTIONIZE})\s+{_MODELS}|{_DEPLOYED_MODEL}",
          f"{_OWNERSHIP}|{_BUILD}|{_DEPLOY}|{_PRODUCTIONIZE}|automat(?:e|es|ed|ing)"),
    _rule("containerized-deployment",
          r"containeri[sz]ed[\s-]+deployments?|container[\s-]+based[\s-]+deployments?|"
          rf"(?:{_DEPLOY})\s+containeri[sz]ed\s+(?:applications?|services?|workloads?)",
          rf"{_BUILD}|{_OWNERSHIP}|{_DEPLOY}|automat(?:e|es|ed|ing)|operat(?:e|es|ed|ing)"),
    _rule("model-serving",
          rf"{_MODELS}[\s-]+serving|serv(?:e|es|ed|ing)\s+(?:trained|ml|machine[\s-]+learning)\s+models?",
          rf"{_OWNERSHIP}|{_BUILD}|operat(?:e|es|ed|ing)|serv(?:e|es|ed|ing)|experience\s+across"),
)

_QUALIFICATION = re.compile(r"\b(?:experience|expertise|knowledge|background|familiarity|proficiency)\s+(?:in|with|of|on)\b", re.I)
_NEGATED = re.compile(r"\b(?:no|never|not|without\s+experience|lack(?:s|ing)?|(?:didn|haven|hasn)[’']t|chưa|không)\b", re.I)
_ASPIRATIONAL = re.compile(r"\b(?:plan(?:s|ning)?\s+to|hop(?:e|es|ing)\s+to|want(?:s)?\s+to|looking\s+to|interested\s+in|learning|assigned\s+to)\b", re.I)
_NOT_REQUIRED = re.compile(r"^\s*(?:(?:is|are)\s+)?not\s+required\b", re.I)
_BOUNDARY = re.compile(r"\r?\n(?=\s*[•●▪*-]\s)|\r?\n\s*\r?\n|(?<=[.!?;])\s+")
_START_TRIM = "•●▪*- \t\r\n"
_CV_SECTIONS = {"skills", "summary", "experience", "projects", "header"}
_JD_SECTIONS = {"requirements", "responsibilities", "nice_to_have", "header"}


def _clauses(text: str, side: str):
    eligible = _CV_SECTIONS if side == "CV" else _JD_SECTIONS
    for section in find_section_spans(text, side):
        if section.name not in eligible:
            continue
        start = section.start
        if section.heading_text:
            heading_end = text.find("\n", start, section.end)
            if heading_end < 0:
                continue
            start = heading_end + 1
        # Keep character offsets from the source, including line wraps from PDFs.
        ends = [(match.start(), match.end()) for match in _BOUNDARY.finditer(text, start, section.end)]
        for end, next_start in [*ends, (section.end, section.end)]:
            raw = text[start:end]
            clause = raw.lstrip(_START_TRIM).rstrip()
            if clause:
                yield section.name, start + len(raw) - len(raw.lstrip(_START_TRIM)), clause
            start = next_start


def _qualified(rule: CompetencyRule, phrase: re.Match[str], clause: str, section: str, side: str) -> bool:
    before = clause[:phrase.start()]
    claim = clause[max(0, phrase.start() - 140):phrase.end()]
    if _NEGATED.search(before) or _NOT_REQUIRED.match(clause[phrase.end():]):
        return False
    if side == "CV" and _ASPIRATIONAL.search(clause):
        return False
    if section in {"skills", "requirements", "nice_to_have"}:
        return True
    return bool(rule.activity.search(claim) or _QUALIFICATION.search(claim))


def recover_engineering_competencies(entities: list[ExtractedSkill], text: str, side: str) -> list[ExtractedSkill]:
    """Add uncovered competencies with verbatim evidence from a skill, work, or requirements section."""
    grounded = {
        ENGINEERING_COMPETENCY_ALIASES.get(skill.skill_id, skill.skill_id)
        for skill in entities if skill.kind == "skill"
        and any(ev.verbatim_ok and ev.offset_resolved for ev in skill.evidences)
    }
    missing_rules = [rule for rule in _RULES if rule.skill_id not in grounded]
    if not missing_rules:
        return []

    citations: dict[str, list[Evidence]] = defaultdict(list)
    for section, start, clause in _clauses(text, side):
        for rule in missing_rules:
            mention = rule.mention.search(clause)
            if mention is None or not _qualified(rule, mention, clause, section, side):
                continue
            citations[rule.skill_id].append(Evidence(
                sentence=clause, surface_form=mention.group(), kind="skill", category="Engineering Practice",
                section=section, start=start, end=start + len(clause),
                mention_start=start + mention.start(), mention_end=start + mention.end(),
                offset_resolved=True, verbatim_ok=True,
            ))
    return [ExtractedSkill(skill_id=key, evidences=evidence, sections=list(dict.fromkeys(e.section for e in evidence)))
            for key, evidence in citations.items()]

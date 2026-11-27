"""Verify JD skill evidence in the CV for graph construction and reporting."""

from dataclasses import dataclass
import re
from typing import Collection, Iterable

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence, ImplicitEvidenceSnippet, ImplicitExtractedSkill,
)
from matching_cv.app.schemas.standardized_output import ProficiencySkill
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services.extraction_adapter import AdaptedSkillItem, ExtractionDataAdapter
from matching_cv.app.services.section_tagger import find_section_spans
from matching_cv.app.services.text_locator import locate_sentence, norm_casefold
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from skill_gap.domain.models import MatchResult


@dataclass(frozen=True)
class EvidenceMatch:
    cv_skill_id: str
    spans: tuple[str, ...]
    score: float


_DIRECT = 1.0
_DEMONSTRATED = 0.90
_RELATED_TOOL = 0.70

_TOOL_NAMES = {"junit": "JUnit", "junit-5": "JUnit 5", "mockito": "Mockito", "jenkins": "Jenkins"}

_WORK_SECTIONS = {"summary", "experience", "projects", "header"}
_EVIDENCE_SECTIONS = _WORK_SECTIONS | {"skills"}
_BLOCK_BOUNDARY = re.compile(r"(?:\r?\n[^\S\n]*(?=[•●▪*-]\s)|\r?\n[^\S\n]*\r?\n)")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WORK = re.compile(
    r"\b(?:built|build(?:ing)?|develop(?:ed|ing)?|design(?:ed|ing)?|implement(?:ed|ing)?|"
    r"migrat(?:ed|ing)|maintain(?:ed|ing)?|operat(?:ed|ing)|deploy(?:ed|ing)?|own(?:ed|ing|s)?|"
    r"writ(?:e|ing)|wrote|ran|automat(?:ed|ing)|optimi[sz](?:ed|ing)|"
    r"reduc(?:ed|ing)|improv(?:ed|ing)|tun(?:ed|ing)|worked|working|managed|used|configured|"
r"(?:experience|background) (?:in|with)|xây dựng|phát triển|triển khai|sử dụng|dùng|"
r"thực hiện|vận hành|tối ưu|kinh nghiệm (?:về|với|trong))\b"
)
_NON_EXPERIENCE = re.compile(
    r"\b(?:not|never|without\s+(?:any\s+)?(?:experience|using|working|ever)|"
r"(?:didn|don|doesn|haven|hasn)[’']t|no\s+(?:prior\s+)?experience|"
    r"interest(?:ed)?\s+in|"
    r"looking\s+to|want\s+to|learning|plan(?:ning)?\s+to|chưa|không)\b"
)
_FINTECH = re.compile(r"\b(?:fintech|financial technology)\b")
_PAYMENTS = re.compile(
    r"\b(?:payment(?:s)? (?:modules?|services?|systems?|gateways?|platforms?|flows?|processing)|"
    r"merchant settlement|card processing|processed payments|(?:building|handling|operating) payments)\b"
)
_QUERY = re.compile(r"\b(?:query (?:optimi[sz]ation|tuning|indexing)|optimi[sz](?:e|ed|ing) (?:sql )?quer(?:y|ies))\b")
_QUERY_PERFORMANCE_TECHNIQUE = (
    r"(?:query (?:indexing|tuning|optimi[sz]ation)|(?:sql|database) (?:indexing|tuning)|"
    r"(?:added|created) (?:[\w-]+ ){0,3}indexes|"
    r"(?:rewrote|optimi[sz]ed) (?:[\w-]+ ){0,3}queries|"
    r"tối ưu truy vấn|lập chỉ mục (?:truy vấn|cơ sở dữ liệu))"
)
_QUERY_PERFORMANCE_OUTCOME = (
    r"(?:(?:reduced|cut|lowered|improved|giảm|cải thiện) (?:[\w-]+ ){0,4}"
    r"(?:latency|execution time|query time|response time|độ trễ|thời gian truy vấn)|"
    r"(?:increased|improved|boosted|tăng|cải thiện) (?:[\w-]+ ){0,4}(?:throughput|thông lượng))"
)
# Require a reported outcome linked to the query technique in the same passage.
_QUERY_PERFORMANCE = re.compile(
    rf"\b(?:{_QUERY_PERFORMANCE_OUTCOME}[^;]{{0,64}}"
    rf"\b(?:through|using|via|with|by|nhờ|bằng|thông qua)\s+{_QUERY_PERFORMANCE_TECHNIQUE}|"
    rf"{_QUERY_PERFORMANCE_TECHNIQUE}[^;]{{0,64}}"
    rf"\b(?:which|thereby|and|qua đó|nhờ đó)\s+{_QUERY_PERFORMANCE_OUTCOME})\b"
)
_REST = re.compile(r"\b(?:rest(?:ful)?\s+apis?|rest(?:ful)?\s+microservices?)\b")
_MICROSERVICE = re.compile(r"\bmicroservices?\b")
_UNIT_TEST = re.compile(r"\bunit[ -]test(?:s|ing)?\b")
_CICD = re.compile(
    r"\b(?:ci\s*[/–-]\s*cd|continuous integration\s+and\s+(?:continuous\s+)?(?:delivery|deployment))\b"
)
_GITHUB_ACTIONS = re.compile(r"\bgithub[ -]+actions\b")
_JUNIT = re.compile(r"\bjunit(?:\s*\d+)?\b")
_MOCKITO = re.compile(r"\bmockito\b")
_JENKINS = re.compile(r"\bjenkins\b")

_WORK_REQUIREMENTS = {
    "fintech": (_FINTECH, _DIRECT),
    "payments": (_PAYMENTS, _DEMONSTRATED),
    "query-optimization": (_QUERY, _DEMONSTRATED),
    "query-performance": (_QUERY_PERFORMANCE, _DEMONSTRATED),
}
_CICD_IDS = {"ci-cd", "ci-cd-pipeline", "ci-cd-pipelines"}
_LISTABLE_REQUIREMENTS = {
    "unit-tests": _UNIT_TEST,
    "unit-testing": _UNIT_TEST,
    **dict.fromkeys(_CICD_IDS, _CICD),
    "github-actions": _GITHUB_ACTIONS,
}
_REQUIREMENTS = {*_WORK_REQUIREMENTS, *_LISTABLE_REQUIREMENTS, "restful-microservices"}
_GRAPH_WORK_REQUIREMENTS = {
    "indexing": re.compile(r"\b(?:query|sql|database) indexing\b"),
    "relational-databases": re.compile(r"\brelational databases?\b"),
}
_GRAPH_REQUIREMENTS = _REQUIREMENTS | _GRAPH_WORK_REQUIREMENTS.keys() | {"junit"}


@dataclass(frozen=True)
class ResumePassage:
    section: str
    block: int
    span: str
    normalized: str


def _resume_passages(text: str) -> Iterable[ResumePassage]:
    block_id = 0
    for section in find_section_spans(text):
        if section.name not in _EVIDENCE_SECTIONS:
            continue
        body = text[section.start:section.end]
        if section.heading_text:
            body = body.partition("\n")[2]
        for block in _BLOCK_BOUNDARY.split(body):
            block_id += 1
            for sentence in _SENTENCE_BOUNDARY.split(block):
                span = sentence.strip().lstrip("•●▪*- ").strip()
                normalized = norm_casefold(span)
                if normalized and not _NON_EXPERIENCE.search(normalized):
                    yield ResumePassage(section.name, block_id, span, normalized)


def _work_passages(passages: list[ResumePassage], keyword: re.Pattern) -> list[ResumePassage]:
    return [
        passage for passage in passages
        if passage.section in _WORK_SECTIONS
        and _WORK.search(passage.normalized)
        and keyword.search(passage.normalized)
    ]


def _tool_spans(passages: list[ResumePassage], keyword: re.Pattern) -> list[str]:
    return [
        passage.span for passage in passages
        if keyword.search(passage.normalized)
        and (passage.section == "skills" or _WORK.search(passage.normalized))
    ]


def _restful_microservice_spans(passages: list[ResumePassage]) -> list[str]:
    rest_passages = _work_passages(passages, _REST)
    microservice_passages = _work_passages(passages, _MICROSERVICE)
    for rest in rest_passages:
        if _MICROSERVICE.search(rest.normalized):
            return [rest.span]
        for microservice in microservice_passages:
            if microservice.block == rest.block:
                return [rest.span, microservice.span]
    return []


def _evidence(spans: list[str], skill_id: str, score: float) -> EvidenceMatch | None:
    if not spans:
        return None
    return EvidenceMatch(skill_id, tuple(dict.fromkeys(spans)), score)


def _confirmed_match(
    jd_id: str, passages: list[ResumePassage], cv_skill_ids: Collection[str]
) -> EvidenceMatch | None:
    if jd_id in _WORK_REQUIREMENTS:
        pattern, score = _WORK_REQUIREMENTS[jd_id]
        return _evidence([p.span for p in _work_passages(passages, pattern)], jd_id, score)
    if jd_id == "restful-microservices":
        return _evidence(_restful_microservice_spans(passages), jd_id, _DEMONSTRATED)

    named_skill = _evidence(_tool_spans(passages, _LISTABLE_REQUIREMENTS[jd_id]), jd_id, _DIRECT)
    if named_skill:
        return named_skill
    if jd_id in ("unit-tests", "unit-testing"):
        junit_id = "junit-5" if "junit-5" in cv_skill_ids else "junit"
        return _evidence(_tool_spans(passages, _JUNIT), junit_id, _RELATED_TOOL) or _evidence(
            _tool_spans(passages, _MOCKITO), "mockito", _RELATED_TOOL
        )
    if jd_id in _CICD_IDS:
        return _evidence(_tool_spans(passages, _JENKINS), "jenkins", _RELATED_TOOL)
    return None


def _verified_cv_spans(
    jd_id: str, passages: list[ResumePassage], cv_skill_ids: set[str]
) -> tuple[str, ...]:
    if jd_id in _GRAPH_WORK_REQUIREMENTS:
        return tuple(p.span for p in _work_passages(passages, _GRAPH_WORK_REQUIREMENTS[jd_id]))
    if jd_id == "junit":
        return tuple(_tool_spans(passages, _JUNIT))
    match = _confirmed_match(jd_id, passages, cv_skill_ids)
    return match.spans if match and match.cv_skill_id == jd_id else ()


def _graph_skill(
    jd_skill: AdaptedSkillItem, spans: tuple[str, ...], cv_text: str
) -> ImplicitExtractedSkill | None:
    evidence = []
    for span in dict.fromkeys(spans):
        location = locate_sentence(cv_text, span)
        if location is None:
            return None
        start, end = location
        evidence.append(ImplicitEvidence(
            inferred_from_raw=span,
            snippets=[ImplicitEvidenceSnippet(text=cv_text[start:end], start=start, end=end, verbatim_ok=True)],
            basis="activity",
        ))
    if not evidence:
        return None
    category = "Domain Knowledge" if normalize_canonical_skill(jd_skill.skill_id) in {"fintech", "payments"} else None
    return ImplicitExtractedSkill(
        skill_id=jd_skill.skill_id, label=jd_skill.display_name,
        category=category, basis="activity", evidences=evidence,
    )


def _collect_graph_skills(
    cv: DocumentUnifiedResult, jd: DocumentUnifiedResult, cv_text: str
) -> list[ImplicitExtractedSkill]:
    jd_skills = ExtractionDataAdapter.extract_active_skills(jd.model_copy(deep=True)).active_skills
    required = {normalize_canonical_skill(skill.skill_id): skill for skill in jd_skills}
    if _GRAPH_REQUIREMENTS.isdisjoint(required):
        return []
    cv_skills = ExtractionDataAdapter.extract_active_skills(cv.model_copy(deep=True)).active_skills
    cv_ids = {normalize_canonical_skill(skill.skill_id) for skill in cv_skills}
    passages = list(_resume_passages(cv_text))
    added = []
    for skill_id in sorted((_GRAPH_REQUIREMENTS & required.keys()) - cv_ids):
        spans = _verified_cv_spans(skill_id, passages, cv_ids)
        skill = _graph_skill(required[skill_id], spans, cv_text)
        if skill is not None:
            added.append(skill)
    return added


def enrich_verified_resume_skills(
    pair: UnifiedExtractFileResponse, cv_text: str
) -> UnifiedExtractFileResponse:
    """Add verified CV skills before embedding, without mutating cached extraction or JD skills."""
    cv, jd = pair.cv, pair.jd
    if cv is None or cv.explicit is None or jd is None or jd.explicit is None or not cv_text:
        return pair
    additions = _collect_graph_skills(cv, jd, cv_text)
    if not additions:
        return pair
    enriched_cv = cv.model_copy(deep=True)
    enriched_cv._verified_resume_skills.extend(additions)
    return pair.model_copy(update={"cv": enriched_cv})


def _unsupported_match(match: MatchResult, matched_skill: ProficiencySkill | None) -> bool:
    jd_id, cv_id = match.jd_skill_id, match.matched_cv_skill_id
    if jd_id == "github-actions" and cv_id != jd_id:
        return True
    if jd_id in ("unit-tests", "unit-testing") and cv_id == "testcontainers":
        return True
    if jd_id not in {"fintech", "payments", "github-actions"} or cv_id != jd_id or matched_skill is None:
        return False

    spans = matched_skill.evidence_spans
    return bool(spans) and all(_NON_EXPERIENCE.search(norm_casefold(span)) for span in spans)


def apply_resume_evidence(
    cv_text: str,
    cv_skills: dict[str, ProficiencySkill],
    jd_skills: dict[str, ProficiencySkill],
    matches: list[MatchResult],
) -> tuple[dict[str, ProficiencySkill], list[MatchResult]]:
    """Prefer source-backed matches for requirements with known misleading name matches."""
    if _REQUIREMENTS.isdisjoint(jd_skills):
        return cv_skills, matches
    passages = list(_resume_passages(cv_text))
    skills = dict(cv_skills)
    resolved: list[MatchResult] = []
    for match in matches:
        jd_id = match.jd_skill_id
        if jd_id not in _REQUIREMENTS:
            resolved.append(match)
            continue

        support = _confirmed_match(jd_id, passages, skills)
        if support is not None:
            skill = skills.get(support.cv_skill_id)
            name = (
                jd_skills[jd_id].skill_name if support.cv_skill_id == jd_id else _TOOL_NAMES[support.cv_skill_id]
            )
            if skill is None:
                skill = ProficiencySkill(skill_id=support.cv_skill_id, skill_name=name, type="implicit")
            spans: dict[str, str] = {}
            for span in (*support.spans, *skill.evidence_spans):
                spans.setdefault(" ".join(span.split()), span)
            skills[support.cv_skill_id] = skill.model_copy(update={"evidence_spans": list(spans.values())})
            match = match.model_copy(
                update={"matched_cv_skill_id": support.cv_skill_id, "soft_match": support.score}
            )
        elif _unsupported_match(match, skills.get(match.matched_cv_skill_id)):
            match = match.model_copy(update={"matched_cv_skill_id": "none", "soft_match": 0.0})
        resolved.append(match)
    return skills, resolved

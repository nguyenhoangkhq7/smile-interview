"""Ground explicit competencies in source text and separate them from context."""

import re
from collections.abc import Iterable

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.services.section_tagger import find_section_spans, section_at
from matching_cv.app.services.source_competency_recovery import recover_engineering_competencies
from matching_cv.app.services.text_locator import locate_sentence, norm_casefold


# A contextual noun can still be a competency if the document independently asks for experience with it.
_DOMAIN_OBJECT = re.compile(
    r"\b(?:updates?|checkout|flows?|workflows?|systems?|requirements?|"
    r"(?:customer|client|business|user) needs|technical topics|"
    r"(?:regulated|consumer) products?|components?)$"
)
_DOMAIN_SCOPE = re.compile(r"^(?:(?:another|other) )?(?:highly )?regulated (?:domain|industry|sector|(?:consumer )?products?)$")
_DOMAIN_QUALIFICATION = re.compile(
    r"\b(?:experience|expertise|background|knowledge|familiarity|proficiency)"
    r"\s+(?:(?:working\s+)?(?:in|with|of|on)\s+)|"
    r"\b(?:kinh nghiệm|kiến thức|am hiểu)\s+(?:về\s+|trong\s+|với\s+)?"
)
_GAP_CUE = re.compile(r"\b(?:no|not|without|lack(?:s|ing)?|never|chưa|không)\b")
_COMPANY_PRODUCT = re.compile(
    r"^(?:[A-Z][\w&.'-]*[ \t]+){1,5}(?:builds|offers|provides|operates|develops)\s+(?:a|an|the)\s+",
)
_PAYMENT_WORK = re.compile(
    r"\b(?:migrat(?:ed|ing)|design(?:ed|ing)|implement(?:ed|ing)|built|build(?:ing)?|"
    r"develop(?:ed|ing)|operat(?:ed|ing)|maintain(?:ed|ing)|led|owned|"
    r"phát triển|triển khai|vận hành|xây dựng|thiết kế)\b"
    r"[^.;!?\n•]{0,95}?\b(?P<mention>payments\b|payment(?=\s+"
    r"(?:modules?|microservices?|services?|systems?|gateways?|processing|platforms?|flows?)\b)|thanh toán\b)",
    re.IGNORECASE,
)
_REGISTERED_STACKS = {
    "java-spring-boot": (("java", r"java"), ("spring-boot", r"spring\s+boot")),
}
_DESIGN_SYSTEM_WORK = re.compile(
    r"\b(?:build(?:ing)?|built|design(?:ed|ing)?|maintain(?:ed|ing)?|extend(?:ed|ing)?|"
    r"develop(?:ed|ing)?|contribut(?:e|ed|ing)\s+to)\b[^.;!?]{0,55}\bdesign systems?\b"
)
_PAYMENT_DOMAIN_IDS = {"payments", "payment-gateway", "payment-processing"}
INTEGRATION_TEST_SKILL_ID = "integration-tests"
INTEGRATION_TEST_VARIANTS = {"integration-test", "integration-testing"}
_INTEGRATION_TEST = re.compile(r"\bintegration[\s-]+test(?:s|ing)?\b", re.IGNORECASE)
_TEST_ACTIVITY = re.compile(
    r"\b(?:writ(?:e|es|ing)|wrote|built|ran|run|running|design(?:ed|ing)|develop(?:ed|ing)|"
    r"implement(?:ed|ing)|automat(?:ed|ing)|perform(?:ed|ing)|execut(?:ed|ing)|"
    r"experience\s+(?:in|with)|viết|chạy|thực hiện)\b",
    re.IGNORECASE,
)
_FUTURE_ACTIVITY = re.compile(r"\b(?:want to|plan(?:ning)? to|hop(?:e|ing) to|interested in|learning)\b", re.IGNORECASE)
_WORK_SECTIONS = {"summary", "experience", "projects", "header"}
_CV_SENTENCE_BOUNDARIES = re.compile(r"\n(?=\s*[•●▪*-]\s)|\n\s*\n|(?<=[.;!?])\s+")


def _has_domain_qualification(evidence: Evidence) -> bool:
    sentence = norm_casefold(evidence.sentence)
    mention = norm_casefold(evidence.surface_form)
    if not mention:
        return False
    for cue in _DOMAIN_QUALIFICATION.finditer(sentence):
        clause = re.split(r"[.;!?]", sentence[cue.end():], maxsplit=1)[0][:110]
        if mention in clause and not _GAP_CUE.search(sentence[max(0, cue.start() - 24):cue.start()]):
            return True
    return False


def _is_contextual_domain(skill: ExtractedSkill, side: str | None) -> bool:
    if skill.kind != "domain" and skill.category != "Domain Knowledge":
        return False
    label = norm_casefold(skill.label)
    if _DOMAIN_SCOPE.fullmatch(label):
        return True
    if not skill.evidences or any(_has_domain_qualification(ev) for ev in skill.evidences):
        return False
    if _DOMAIN_OBJECT.search(label):
        return True
    return side == "JD" and all(
        ev.section == "about" or _COMPANY_PRODUCT.search(ev.sentence.strip())
        for ev in skill.evidences
    )


def _as_context(skill: ExtractedSkill) -> ExtractedSkill:
    evidences = [ev.model_copy(update={"kind": "context", "kind_source": "inferred"}) for ev in skill.evidences]
    return skill.model_copy(update={"kind": "context", "evidences": evidences})


_COVERAGE_ANALYSIS_LABEL = re.compile(r"(?:(?:code|test) )?coverage analysis|analysis of (?:(?:code|test) )?coverage")
_COVERAGE_REVIEW = re.compile(
    r"\b(?:analy[sz](?:e|es|ed|ing)|review(?:s|ed|ing)?|audit(?:s|ed|ing)?|"
    r"evaluat(?:e|es|ed|ing)|investigat(?:e|es|ed|ing)|interpret(?:s|ed|ing)?)\s+"
    r"(?:(?!\b(?:and|but|then)\b)[^.!?;]){0,48}?\bcoverage\b"
)
_COVERAGE_PLAN_OR_NEGATION = re.compile(r"\b(?:no|never|not|plan(?:s|ned|ning)? to|(?:didn|haven|hasn)[’']t)\b")


def has_unsupported_coverage_analysis(label: str, spans: Iterable[str]) -> bool:
    """A reported change in test coverage does not establish a separate analysis activity."""
    if not _COVERAGE_ANALYSIS_LABEL.fullmatch(norm_casefold(label).replace("-", " ")):
        return False
    for span in spans:
        for clause in re.split(r"[.!?;•]", norm_casefold(span)):
            listed = re.sub(r"^(?:skills|testing|tools)\s*:\s*", "", clause.strip()).replace("-", " ")
            if any(_COVERAGE_ANALYSIS_LABEL.fullmatch(item.strip()) for item in listed.split(",")):
                return False
            for activity in _COVERAGE_REVIEW.finditer(clause):
                if not _COVERAGE_PLAN_OR_NEGATION.search(clause[max(0, activity.start() - 48):activity.start()]):
                    return False
    return True


def is_resume_system_object(label: str) -> bool:
    return norm_casefold(label).replace("-", " ") in {"monolith", "legacy monolith"}


def _refine_kind(skill: ExtractedSkill, side: str) -> ExtractedSkill:
    if side == "CV" and (
        is_resume_system_object(skill.label)
        or has_unsupported_coverage_analysis(skill.label, (ev.sentence for ev in skill.evidences if ev.offset_resolved))
    ):
        return _as_context(skill)
    if _is_contextual_domain(skill, side):
        return _as_context(skill)
    if skill.kind != "context" or skill.skill_id not in {"design-system", "design-systems"}:
        return skill
    if not any(
        ev.offset_resolved and ev.verbatim_ok
        and (_has_domain_qualification(ev) or _DESIGN_SYSTEM_WORK.search(norm_casefold(ev.sentence)))
        and not _GAP_CUE.search(norm_casefold(ev.sentence))
        for ev in skill.evidences
    ):
        return skill
    evidences = [ev.model_copy(update={"kind": "skill", "kind_source": "inferred"}) for ev in skill.evidences]
    return skill.model_copy(update={"kind": "skill", "evidences": evidences})


def _payment_evidence(text: str) -> Iterable[Evidence]:
    sections = find_section_spans(text)
    # Work claims can wrap across PDF lines. Normalize horizontal layout and locate the whole span again.
    for span in _CV_SENTENCE_BOUNDARIES.split(text):
        normalized = " ".join(span.strip().lstrip("•●▪*- ").split())
        match = _PAYMENT_WORK.search(normalized)
        claim = norm_casefold(normalized[:match.end()]) if match else ""
        if match is None or _GAP_CUE.search(claim) or re.search(r"\b(?:looking to|seeking to|want to|plan to)\b", claim):
            continue
        location = locate_sentence(text, normalized)
        if location is None:
            continue
        start, end = location
        section = section_at(sections, start)
        if section not in _WORK_SECTIONS:
            continue
        original = text[start:end]
        surface = match.group("mention")
        # Search the matched mention in the original span to get source offsets for wrapped PDF lines.
        offsets = re.search(r"(?<!\w)" + r"\s+".join(map(re.escape, surface.split())) + r"(?!\w)", original, re.I)
        if offsets is None:
            continue
        yield Evidence(
            surface_form=original[offsets.start():offsets.end()], sentence=original,
            kind="domain", category="Domain Knowledge", kind_source="inferred", section=section,
            start=start, end=end, offset_resolved=True, verbatim_ok=True,
            mention_start=start + offsets.start(), mention_end=start + offsets.end(),
        )


def _integration_test_claim(clause: str, mention: re.Match[str], section: str | None) -> bool:
    claim = clause if section == "skills" else clause[:mention.start()]
    if _GAP_CUE.search(norm_casefold(claim)) or _FUTURE_ACTIVITY.search(claim):
        return False
    return section == "skills" or (section in _WORK_SECTIONS and _TEST_ACTIVITY.search(claim) is not None)


def _integration_test_evidence(text: str) -> Iterable[Evidence]:
    sections = find_section_spans(text)
    end = 0
    for raw_clause in _CV_SENTENCE_BOUNDARIES.split(text):
        clause = raw_clause.lstrip("•●▪*- \t\r\n").rstrip()
        match = _INTEGRATION_TEST.search(clause)
        if match is None:
            continue
        start = text.index(clause, end)
        end = start + len(clause)
        section = section_at(sections, start + match.start())
        if _integration_test_claim(clause, match, section):
            yield Evidence(
                surface_form=match.group(), sentence=clause,
                kind="skill", category="Engineering Practice", section=section,
                start=start, end=end, offset_resolved=True, verbatim_ok=True,
                mention_start=start + match.start(), mention_end=start + match.end(),
            )


def _split_stack(skill: ExtractedSkill, text: str) -> list[ExtractedSkill]:
    components = _REGISTERED_STACKS.get(skill.skill_id)
    if components is None or skill.kind != "skill":
        return [skill]
    by_component: dict[str, list[Evidence]] = {key: [] for key, _ in components}
    for ev in skill.evidences:
        if not ev.verbatim_ok or not ev.offset_resolved:
            continue
        location = locate_sentence(text, ev.sentence)
        if location is None:
            continue
        start, end = location
        sentence = text[start:end]
        if not all(re.search(r"(?<!\w)" + term + r"(?!\w)", ev.surface_form, re.I) for _, term in components):
            continue
        for key, term in components:
            occurrence = re.search(r"(?<!\w)" + term + r"(?!\w)", sentence, re.I)
            if occurrence is not None:
                by_component[key].append(ev.model_copy(update={
                    "surface_form": occurrence.group(),
                    "sentence": sentence,
                    "start": start,
                    "end": end,
                    "mention_start": start + occurrence.start(),
                    "mention_end": start + occurrence.end(),
                }))
    if not all(by_component.values()):
        return [skill]
    return [
        ExtractedSkill(skill_id=key, kind=skill.kind, category=skill.category, evidences=evidence)
        for key, evidence in by_component.items()
    ]


def refine_competency_entities(
    entities: list[ExtractedSkill], text: str | None, side: str | None
) -> list[ExtractedSkill]:
    """Refine extraction and recover selected verbatim competencies before embedding."""
    if not text or side not in {"CV", "JD"}:
        return entities
    refined = [
        _refine_kind(skill, side)
        for entity in entities
        for skill in _split_stack(entity, text)
    ]
    refined.extend(recover_engineering_competencies(refined, text, side))
    if side != "CV":
        return refined
    if not any(
        skill.skill_id in _PAYMENT_DOMAIN_IDS and skill.kind == "domain"
        and any(ev.offset_resolved for ev in skill.evidences) for skill in refined
    ):
        evidence = list(_payment_evidence(text))
        if evidence:
            refined.append(ExtractedSkill(skill_id="payments", kind="domain", category="Domain Knowledge", evidences=evidence))
    if not any(
        (skill.skill_id == INTEGRATION_TEST_SKILL_ID or skill.skill_id in INTEGRATION_TEST_VARIANTS)
        and skill.kind == "skill"
        and any(ev.offset_resolved and ev.verbatim_ok for ev in skill.evidences)
        for skill in refined
    ):
        evidence = list(_integration_test_evidence(text))
        if evidence:
            refined.append(ExtractedSkill(
                skill_id=INTEGRATION_TEST_SKILL_ID, kind="skill", category="Engineering Practice", evidences=evidence,
            ))
    return refined

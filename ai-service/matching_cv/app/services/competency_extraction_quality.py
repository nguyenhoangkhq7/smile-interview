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
    r"\b(?:understanding of|familiar with|worked in|speciali[sz]ed in)\s+|"
    r"\b(?:kinh nghiệm|kiến thức|am hiểu|hiểu biết)\s+(?:về\s+|trong\s+|với\s+)?"
)
_GAP_CUE = re.compile(r"\b(?:no|not|without|lack(?:s|ing)?|never|chưa|không)\b")
_DOMAIN_CLAUSE_END = re.compile(
    r"[;!?•]|\.(?!\w)|\b(?:for|to|using|supporting|on behalf of|"
    r"in (?:a|an|the|our)|để|cho|nhằm|bằng)\b"
)
_CLAUSE_BOUNDARY = re.compile(r"[;!?•]|\.(?!\w)|\b(?:but|however|nhưng|tuy nhiên)\b")
_COMPANY_EXPERIENCE = re.compile(
    r"^(?:we|our (?:team|company)|the company)\s+(?:have|has|bring|brings|offer|offers|speciali[sz]e[sd]?)\b"
)
_CANDIDATE_REQUIREMENT = re.compile(
    r"\b(?:must|require[sd]?|preferred|candidates?|looking for|seeking|"
    r"you (?:have|bring|need|should)|ứng viên|yêu cầu|ưu tiên|bắt buộc)\b"
)
_DOMAIN_EXPERIENCE_SUFFIX = re.compile(
    r"\s+(?:(?:domain|industry)\s+)?(?:experience|knowledge|expertise|familiarity)\b"
)
_PROJECT_IMPLEMENTATION = re.compile(
    r"\b(?:build(?:ing)?|develop(?:ing|ment)?|implement(?:ing|ation)?|integrat(?:ing|ion)|"
    r"migrat(?:ing|ion)|deploy(?:ing|ment)?|maintain(?:ing)?|"
    r"triển khai|phát triển|xây dựng|tích hợp|bảo trì)\b"
)
_JD_REQUIREMENT_PREFIX = r"\b(?:must have|must understand|require[sd]?|yêu cầu|bắt buộc|ưu tiên)\s+"
_JD_REQUIREMENT_SUFFIX = r"\s+(?:is\s+|are\s+)?(?:required|preferred|mandatory|bắt buộc|là điểm cộng)\b"
_REGISTERED_STACKS = {
    "java-spring-boot": (("java", r"java"), ("spring-boot", r"spring\s+boot")),
}
_DESIGN_SYSTEM_WORK = re.compile(
    r"\b(?:build(?:ing)?|built|design(?:ed|ing)?|maintain(?:ed|ing)?|extend(?:ed|ing)?|"
    r"develop(?:ed|ing)?|contribut(?:e|ed|ing)\s+to)\b[^.;!?]{0,55}\bdesign systems?\b"
)
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
    if _FUTURE_ACTIVITY.search(sentence):
        return False
    term = rf"(?<!\w){re.escape(mention)}(?!\w)"
    for cue in _DOMAIN_QUALIFICATION.finditer(sentence):
        clause = _DOMAIN_CLAUSE_END.split(sentence[cue.end():], maxsplit=1)[0][:110]
        before = _CLAUSE_BOUNDARY.split(sentence[:cue.start()])[-1]
        occurrence = re.search(term, clause)
        if occurrence and not _GAP_CUE.search(before + clause) and not _PROJECT_IMPLEMENTATION.search(clause[:occurrence.start()]):
            return True
    return not _GAP_CUE.search(sentence) and bool(re.search(term + _DOMAIN_EXPERIENCE_SUFFIX.pattern, sentence))


def is_domain_skill(skill: ExtractedSkill) -> bool:
    return skill.kind == "domain" or (
        skill.category == "Domain Knowledge" and skill.kind in {None, "skill", "context"}
    )


def _has_jd_domain_requirement(evidence: Evidence) -> bool:
    sentence = norm_casefold(evidence.sentence)
    mention = norm_casefold(evidence.surface_form)
    if not mention or _GAP_CUE.search(sentence):
        return False
    term = rf"(?<!\w){re.escape(mention)}(?!\w)"
    return bool(re.search(_JD_REQUIREMENT_PREFIX + term + "|" + term + _JD_REQUIREMENT_SUFFIX, sentence))


def is_jd_requirement_context(sentence: str, section: str | None) -> bool:
    text = norm_casefold(sentence)
    return (
        section != "benefits" and not _COMPANY_EXPERIENCE.match(text)
        and (section != "about" or bool(_CANDIDATE_REQUIREMENT.search(text)))
    )


def _is_qualified_domain_evidence(evidence: Evidence, side: str, text: str) -> bool:
    if not evidence.verbatim_ok or locate_sentence(text, evidence.sentence) is None:
        return False
    sentence = norm_casefold(evidence.sentence)
    if side == "CV" and _COMPANY_EXPERIENCE.match(sentence):
        return False
    if side == "JD" and not is_jd_requirement_context(sentence, evidence.section):
        return False
    if _has_domain_qualification(evidence) or (side == "JD" and _has_jd_domain_requirement(evidence)):
        return True
    phrase = sentence.strip(" •-*.;:")
    return (
        side == "JD" and evidence.section in {"requirements", "nice_to_have"}
        and phrase == norm_casefold(evidence.surface_form) and not _DOMAIN_OBJECT.search(phrase)
    )


def _as_context(skill: ExtractedSkill) -> ExtractedSkill:
    evidences = [ev.model_copy(update={"kind": "context", "kind_source": "inferred"}) for ev in skill.evidences]
    return skill.model_copy(update={"kind": "context", "evidences": evidences})


def _with_evidences(skill: ExtractedSkill, evidences: list[Evidence]) -> ExtractedSkill:
    return skill.model_copy(update={
        "evidences": evidences,
        "surface_forms": list(dict.fromkeys(ev.surface_form for ev in evidences if ev.surface_form)),
        "sections": list(dict.fromkeys(ev.section for ev in evidences if ev.section)),
    })


def _refine_domain(skill: ExtractedSkill, side: str, text: str) -> list[ExtractedSkill]:
    if skill.kind == "context" or _DOMAIN_SCOPE.fullmatch(norm_casefold(skill.label)):
        return [_as_context(skill)]
    qualified, context = [], []
    for evidence in skill.evidences:
        destination = qualified if _is_qualified_domain_evidence(evidence, side, text) else context
        destination.append(evidence)
    if not qualified:
        return [_as_context(skill)]
    if not context:
        return [skill]
    return [_with_evidences(skill, qualified), _as_context(_with_evidences(skill, context))]


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
    refined = []
    for entity in entities:
        for skill in _split_stack(entity, text):
            if is_domain_skill(skill):
                refined.extend(_refine_domain(skill, side, text))
            else:
                refined.append(_refine_kind(skill, side))
    refined.extend(recover_engineering_competencies(refined, text, side))
    if side != "CV":
        return refined
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

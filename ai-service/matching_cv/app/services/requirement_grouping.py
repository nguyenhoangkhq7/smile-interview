"""Preserve source-stated JD alternatives before embedding and graph construction."""

from dataclasses import dataclass
import re

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services.competency_extraction_quality import is_domain_skill, is_jd_requirement_context
from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter
from matching_cv.app.services.resume_evidence_matching import enrich_verified_resume_skills
from matching_cv.app.services.section_tagger import find_section_spans, section_at
from matching_cv.app.services.text_locator import locate_sentence, norm_casefold
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill


@dataclass(frozen=True)
class RequirementRule:
    skill_id: str
    expression: str
    options: dict[str, str]
    aliases: tuple[str, ...] = ()
    certification: bool = False
    allow_examples: bool = False
    base_skill: tuple[str, str] | None = None
    domain: bool = False


@dataclass(frozen=True)
class RequirementGroup:
    rule: RequirementRule
    evidence: Evidence
    options: tuple[str, ...]


_NEGATED = re.compile(r"\b(?:no\s+(?:prior\s+)?experience|never|without\s+experience|not\s+certified|chưa|không)\b", re.I)
_OPEN_ALTERNATIVE = re.compile(r"\bor\b[^()\n]{0,25}\b(?:similar|equivalent|another|other)\b", re.I)
_REQUIRED = r"(?:must\s+(?:have|know|use)|required\s+(?:experience\s+)?(?:with|in)|experience\s+(?:working\s+)?(?:with|in)|proficiency\s+in|hands-on\s+(?:experience\s+with)?)"
_SUFFIX_REQUIRED = r"(?:experience\s+)?(?:is\s+(?:required|mandatory)|required)\b"
_JUNIT_VERSION = re.compile(r"junit-?v?(?P<version>\d+(?:\.\d+)*)$")
_DATABASE_INDEXING = re.compile(r"\b(?:query|sql|database|relational)[ -]+index(?:es|ing)?\b")
_INDEX_MENTION = re.compile(r"\bindex(?:es|ing)?\b")
_DATABASE_CONTEXT = re.compile(r"\b(?:sql|postgre(?:sql|s)|mysql|mariadb|relational|database|queries)\b")
_OTHER_INDEXING = re.compile(r"\b(?:search|vector|document|full[ -]text)[ -]+index(?:es|ing)?\b")


def _parenthesized(head):
    return rf"\b{head}\s*\((?P<options>[^()]{{1,115}})\)"


def _alternatives(options):
    word = "(?:" + "|".join(options.values()) + ")"
    return rf"(?P<options>(?<!\w){word}(?:\s*,\s*{word})*\s*(?:,\s*)?\bor\s+{word}(?!\w))"


_DATABASES = {"postgresql": r"postgres(?:ql)?", "mysql": "mysql", "mariadb": "mariadb", "sql-server": r"(?:microsoft\s+)?sql\s+server", "oracle-db": r"oracle(?:\s+database)?"}
_BROKERS = {"kafka": r"(?:apache\s+)?kafka", "rabbitmq": "rabbitmq", "activemq": "activemq", "nats": "nats", "amazon-sqs": r"(?:amazon\s+)?sqs"}
_CI_TOOLS = {"jenkins": "jenkins", "github-actions": r"github\s+actions", "gitlab-ci": r"gitlab\s+ci(?:/cd)?", "circleci": "circleci"}
_CERTIFIERS = {"aws": r"aws", "gcp": r"gcp|google\s+cloud", "azure": r"(?:microsoft\s+)?azure"}
_STATE_TOOLS = {"redux-toolkit": r"redux\s+toolkit", "zustand": "zustand", "react-query": r"(?:tanstack|react)\s+query"}
_NODEJS = r"node\.?js"
_HTTP_APIS = {"graphql": r"graphql(?:\s+apis?)?", "rest-api": r"rest(?:ful)?\s+apis?"}
_SCRIPTING = {"python": "python", "bash": "bash", "powershell": "powershell"}
_GITOPS = {"argocd": r"argo\s*cd", "flux": r"flux(?:cd)?"}
_SPARK = {"spark": r"(?:apache\s+)?spark", "pyspark": "pyspark"}
_COMMERCE_DOMAINS = {"retail": "retail", "e-commerce": r"e[-\s]?commerce", "marketing-analytics": r"marketing\s+analytics"}

_RULES = (
    RequirementRule("relational-databases", _parenthesized("relational databases?"), _DATABASES,
                    ("relational-database", "relational-database-management")),
    RequirementRule("message-broker", _parenthesized(r"(?:at\s+least\s+one|one|an?)\s+message\s+broker"), _BROKERS,
                    ("message-brokers", "message-brokerage")),
    RequirementRule("ci-cd", _parenthesized(r"ci\s*/\s*cd(?:\s+pipelines?)?"), _CI_TOOLS,
                    ("ci-cd-pipeline", "ci-cd-pipelines"), allow_examples=True),
    RequirementRule("cloud-provider-certification", _alternatives(_CERTIFIERS) + r"\s+(?:cloud\s+)?certifications?\b",
                    _CERTIFIERS, ("cloud-certification", "aws-certification", "gcp-certification", "azure-certification"),
                    certification=True),
    RequirementRule(
        "regulated-domain-experience",
        r"\b(?:experience|familiarity|background)\s+(?:in|with)\s+"
        r"(?P<options>(?:fintech\s*,\s*payments|healthcare)\s*,?\s+or\s+another\s+"
        r"(?:highly\s+)?regulated\s+(?:domain|consumer\s+product|industry))\b",
        {"fintech": "fintech", "payments": r"payments?", "healthcare": r"health\s*care"}, domain=True,
    ),
    RequirementRule("utility-first-css-framework", _parenthesized(r"utility[-\s]+first\s+framework"),
                    {"tailwind-css": r"tailwind(?:\s+css)?", "unocss": "unocss"}, ("utility-first-framework",)),
    RequirementRule("state-management", _parenthesized(r"state\s+management(?:\s+patterns?)?"), _STATE_TOOLS,
                    ("state-management-patterns", "state-management-pattern")),
    RequirementRule("component-documentation", r"\b(?P<options>storybook\s+or\s+other\s+component[-\s]documentation)\b",
                    {"storybook": "storybook"}),
    RequirementRule("nodejs-framework", _parenthesized(_NODEJS),
                    {"express": r"express(?:\.?js)?", "nestjs": r"nest\.?js"}, base_skill=("nodejs", _NODEJS)),
    RequirementRule("api-protocol", _alternatives(_HTTP_APIS), _HTTP_APIS),
    RequirementRule("scripting-language", _alternatives(_SCRIPTING), _SCRIPTING),
    RequirementRule("gitops-tool", _alternatives(_GITOPS), _GITOPS, ("gitops-tools",)),
    RequirementRule("spark-processing", _alternatives(_SPARK), _SPARK),
    RequirementRule("commerce-domain-experience", r"\b(?:background|experience)\s+(?:in|with)\s+" + _alternatives(_COMMERCE_DOMAINS),
                    _COMMERCE_DOMAINS, domain=True),
    RequirementRule("cloud-data-warehouse", _parenthesized(r"cloud\s+data\s+warehouse"),
                    {"snowflake": "snowflake", "bigquery": "bigquery", "redshift": "redshift"}),
    RequirementRule("model-tracking-tool", r"\b(?P<options>mlflow\s+or\s+a\s+similar\s+model[-\s]tracking(?:/serving)?\s+tool)\b",
                    {"mlflow": "mlflow"}),
)

_OPTION_ALIASES = {"express-js": "express", "expressjs": "express", "nest-js": "nestjs", "argo-cd": "argocd",
                   "fluxcd": "flux", "tailwind": "tailwind-css", "apache-spark": "spark", "amazon-redshift": "redshift"}


def _id(value):
    key = normalize_canonical_skill(value)
    return _OPTION_ALIASES.get(key, key)


def _option_in(phrase, text):
    return re.search(rf"(?<!\w)(?:{phrase})(?!\w)", text, re.I) is not None


def _has_alternatives(rule, options_text, options):
    if not options or re.search(r"\b(?:both|and)\b|\ball\s+of\b", options_text, re.I):
        return False
    if rule.allow_examples and len(options) > 1:
        return True
    return bool(re.search(r"\bor\b", options_text, re.I) and (len(options) > 1 or _OPEN_ALTERNATIVE.search(options_text)))


def _find_groups(text):
    sections = find_section_spans(text, "JD")
    groups = []
    for rule in _RULES:
        for match in re.finditer(rule.expression, text, re.I):
            option_text = match.group("options")
            options = tuple(key for key, phrase in rule.options.items() if _option_in(phrase, option_text))
            if not _has_alternatives(rule, option_text, options):
                continue
            start, end = match.span()
            section = section_at(sections, start)
            prefix = re.split(r"[;.!?]|\n\s*(?=[•●▪*-]\s)", text[max(0, start - 90):start])[-1]
            suffix = text[end:end + 40]
            if section == "benefits":
                continue
            if rule.domain and not is_jd_requirement_context(prefix.rsplit("\n", 1)[-1] + match.group(), section):
                continue
            if re.search(r"\b(?:no|without)\s*$", prefix, re.I):
                continue
            if re.match(r"\s+(?:(?:is|are)\s+)?not\s+required\b", suffix, re.I):
                continue
            kind, category = ("certification", "Certification") if rule.certification else ("skill", "Technical Concept")
            if rule.domain:
                kind, category = "domain", "Domain Knowledge"
            groups.append(RequirementGroup(rule, Evidence(
                surface_form=match.group(), sentence=match.group(), kind=kind, category=category,
                start=start, end=end, mention_start=start, mention_end=end,
                section=section, offset_resolved=True, verbatim_ok=True,
            ), options))
    return groups


def _independent_requirements(text, groups):
    # Mask recognized groups so the qualification for a choice stays attached to the group.
    outside = list(text)
    for group in groups:
        start, end = group.evidence.start, group.evidence.end
        outside[start:end] = " " * (end - start)
    clauses = re.split(r"[;!?]|\.(?!\w)|\n\s*(?=[•●▪*-]\s)|\n\s*\n", "".join(outside))
    patterns = {key: group.rule.options[key] for group in groups for key in group.options}
    patterns.update(group.rule.base_skill for group in groups if group.rule.base_skill is not None)
    return {
        key for key, phrase in patterns.items()
        if any(re.search(rf"\b{_REQUIRED}\s+(?:{phrase})(?!\w)|"
                         rf"(?<!\w)(?:{phrase})\s+{_SUFFIX_REQUIRED}", clause, re.I)
               for clause in clauses)
    }


def _group_source_ids(groups: list[RequirementGroup], independent: set[str]) -> set[str]:
    rule = groups[0].rule
    ids = {rule.skill_id, *rule.aliases, *(_id(group.evidence.surface_form) for group in groups)}
    if rule.base_skill and rule.base_skill[0] not in independent:
        ids.add(rule.base_skill[0])
    return ids


def _grouped_jd(jd, groups, text):
    independent = _independent_requirements(text, groups)
    by_id: dict[str, list[RequirementGroup]] = {}
    for group in groups:
        by_id.setdefault(group.rule.skill_id, []).append(group)
    source_ids = {key: _group_source_ids(members, independent) for key, members in by_id.items()}
    excluded = set().union(*source_ids.values())
    excluded.update({key for g in groups for key in g.options if key not in independent})
    updated = jd.model_copy(deep=True)
    original_skills = updated.explicit.skills
    updated.explicit.skills = [item for item in original_skills if _id(item.skill_id) not in excluded]
    updated.validation.accepted_implicit_skills = [
        item for item in jd.validation.accepted_implicit_skills if _id(item.skill_id) not in excluded
    ]
    if updated.implicit:
        updated.implicit.skills = [item for item in updated.implicit.skills if _id(item.skill_id) not in excluded]
    for key, members in by_id.items():
        citations = [group.evidence for group in members]
        citations.extend(evidence for item in original_skills if _id(item.skill_id) in source_ids[key]
                         for evidence in item.evidences)
        unique = {}
        for evidence in citations:
            unique.setdefault((evidence.start, evidence.end, evidence.surface_form, evidence.sentence), evidence)
        updated.explicit.skills.append(ExtractedSkill(
            skill_id=key, surface_forms=[" ".join(citations[0].surface_form.split())],
            sections=list(dict.fromkeys(ev.section for ev in unique.values() if ev.section)), evidences=list(unique.values()),
        ))
    updated._requirement_groups = {
        key: tuple(dict.fromkeys(option for group in members for option in group.options))
        for key, members in by_id.items()
    }
    updated._strict_requirement_group_ids = {group.rule.skill_id for group in groups if group.rule.skill_id != "ci-cd"}
    return updated


def _anchored_spans(item, text):
    spans = [getattr(evidence, "sentence", None) or getattr(evidence, "inferred_from_raw", "") for evidence in item.evidences]
    return {norm_casefold(span) for span in spans if locate_sentence(text, span) is not None and not _NEGATED.search(span)}


def _option_proof(candidate, group, text):
    item = candidate.raw_skill
    spans = _anchored_spans(item, text)
    eligible = group.rule.options if _OPEN_ALTERNATIVE.search(group.evidence.sentence) else group.options
    if group.rule.certification:
        if candidate.kind != "certification" and candidate.category != "Certification":
            return False
        return any(_option_in(group.rule.options[key], candidate.display_name) for key in group.options) and bool(spans)
    if group.rule.domain and (not isinstance(item, ExtractedSkill) or not is_domain_skill(item)):
        return False
    key = _id(candidate.skill_id)
    return key in eligible and any(_option_in(group.rule.options[key], span) for span in spans)


def _project_cv_options(cv, jd, groups, cv_text):
    required = {_id(item.skill_id) for item in jd.explicit.skills}
    projected = cv.model_copy(deep=True)
    for group in groups:
        target = group.rule.skill_id
        if target == "ci-cd":
            continue
        active = ExtractionDataAdapter.extract_active_skills(projected).active_skills
        if any(_id(item.skill_id) == target for item in active):
            continue
        options = [item for item in active if _option_proof(item, group, cv_text)]
        if not options:
            continue
        source = next((item for item in options if _id(item.skill_id) not in required), options[0])
        source_key = _id(source.skill_id)
        if source_key in required:
            _project_skill(projected, source.raw_skill, target, keep_original=True)
        else:
            for item in options:
                if _id(item.skill_id) == source_key:
                    _project_skill(projected, item.raw_skill, target, keep_original=False)
    return projected


def _project_skill(doc, source, target, *, keep_original):
    if isinstance(source, ExtractedSkill):
        skills = doc.explicit.skills
    elif source in doc.validation.accepted_implicit_skills:
        skills = doc.validation.accepted_implicit_skills
    else:
        skills = doc._verified_resume_skills
    projected = source.model_copy(update={"skill_id": target})
    if keep_original:
        skills.append(projected)
    else:
        skills[skills.index(source)] = projected


def _prepare_domain_skills(doc: DocumentUnifiedResult, allowed_domains: set[str] | None = None) -> DocumentUnifiedResult:
    """Remove inferred domains and keep unrequested explicit domains as context."""
    raw = doc.implicit.skills if doc.implicit else []
    inferred = [*raw, *doc.validation.accepted_implicit_skills, *doc._verified_resume_skills]
    unrequested = {
        skill.skill_id for skill in doc.explicit.skills
        if is_domain_skill(skill) and _id(skill.skill_id) not in allowed_domains
    } if allowed_domains is not None else set()
    if not unrequested and all(skill.category != "Domain Knowledge" for skill in inferred):
        return doc

    updated = doc.model_copy(deep=True)
    updated.validation.accepted_implicit_skills = [
        skill for skill in updated.validation.accepted_implicit_skills if skill.category != "Domain Knowledge"
    ]
    if updated.implicit:
        updated.implicit.skills = [skill for skill in updated.implicit.skills if skill.category != "Domain Knowledge"]
    updated._verified_resume_skills = [
        skill for skill in updated._verified_resume_skills if skill.category != "Domain Knowledge"
    ]
    if unrequested:
        updated.explicit.non_skill_entities.extend(
            skill for skill in updated.explicit.skills if skill.skill_id in unrequested
        )
        updated.explicit.skills = [skill for skill in updated.explicit.skills if skill.skill_id not in unrequested]
    return updated


def prepare_pipeline_skills(pair: UnifiedExtractFileResponse, cv_text: str, jd_text: str) -> UnifiedExtractFileResponse:
    """Only change the per-request representation shared by SBERT, JSI and GNN."""
    cv, jd = pair.cv, pair.jd
    if cv is None or cv.explicit is None or jd is None or jd.explicit is None:
        return pair
    groups = _find_groups(jd_text)
    if groups:
        jd = _grouped_jd(jd, groups, jd_text)
    jd = _prepare_domain_skills(jd)
    cv = _prepare_domain_skills(cv)
    pair = pair.model_copy(update={"cv": cv, "jd": jd})
    pair = enrich_verified_resume_skills(pair, cv_text)
    if groups:
        pair = pair.model_copy(update={"cv": _project_cv_options(pair.cv, pair.jd, groups, cv_text)})
    allowed_domains = {_id(skill.skill_id) for skill in jd.explicit.skills if is_domain_skill(skill)}
    pair = pair.model_copy(update={"cv": _prepare_domain_skills(pair.cv, allowed_domains)})
    return deduplicate_resume_evidence(pair, cv_text)


def _junit_redirects(evidence: dict[str, set[str]], required: set[str]) -> dict[str, str]:
    if "junit" not in evidence or not any(re.search(r"\bjunit(?:[ -]*v?\d+(?:\.\d+)*)?\b", span) for span in evidence["junit"]):
        return {}
    versions = []
    for key, spans in evidence.items():
        version = _JUNIT_VERSION.fullmatch(key)
        if version is not None and any(
            re.search(rf"\bjunit[ -]*v?{re.escape(version['version'])}(?!\d)", span) for span in spans
        ):
            versions.append(key)
    if len(versions) != 1:
        return {}
    version = versions[0]
    if version in required:
        return {} if "junit" in required else {"junit": version}
    return {version: "junit"}


def _is_database_indexing(span: str) -> bool:
    return not _OTHER_INDEXING.search(span) and bool(
        _DATABASE_INDEXING.search(span) or (_INDEX_MENTION.search(span) and _DATABASE_CONTEXT.search(span))
    )


def _resume_redirects(evidence: dict[str, set[str]], required: set[str]) -> dict[str, str]:
    redirects = _junit_redirects(evidence, required)
    indexing, query_indexing = evidence.get("indexing"), evidence.get("query-indexing")
    if indexing and query_indexing and all(_is_database_indexing(span) for span in indexing | query_indexing):
        if "query-indexing" not in required:
            redirects["query-indexing"] = "indexing"
        elif "indexing" not in required:
            redirects["indexing"] = "query-indexing"
    design = evidence.get("relational-database-design")
    if design and design == evidence.get("relational-databases") and "relational-database-design" not in required:
        redirects["relational-database-design"] = "relational-databases"
    return redirects


def _merge_explicit_redirects(skills: list[ExtractedSkill], redirects: dict[str, str]) -> list[ExtractedSkill]:
    targets = set(redirects.values())
    grouped: dict[str, list[ExtractedSkill]] = {}
    for skill in skills:
        skill_id = _id(skill.skill_id)
        target = redirects.get(skill_id, skill_id)
        if target in targets:
            grouped.setdefault(target, []).append(skill)
    kept = [skill for skill in skills if _id(skill.skill_id) not in targets and _id(skill.skill_id) not in redirects]
    for target, members in grouped.items():
        # Prefer the specific tool/version or practice name over a generic alias.
        preferred = next((skill for skill in members if _id(skill.skill_id) in redirects), members[0])
        if target == "query-indexing" or _JUNIT_VERSION.fullmatch(target):
            preferred = next((skill for skill in members if _id(skill.skill_id) == target), preferred)
        ordered = [preferred, *(skill for skill in members if skill is not preferred)]
        evidences = {}
        for skill in ordered:
            for evidence in skill.evidences:
                evidences.setdefault((norm_casefold(evidence.sentence), norm_casefold(evidence.surface_form)), evidence)
        kept.append(preferred.model_copy(update={
            "skill_id": target,
            "surface_forms": list(dict.fromkeys(form for skill in ordered for form in skill.surface_forms)),
            "sections": list(dict.fromkeys(section for skill in ordered for section in skill.sections)),
            "evidences": list(evidences.values()),
        }))
    return kept


def deduplicate_resume_evidence(pair: UnifiedExtractFileResponse, cv_text: str) -> UnifiedExtractFileResponse:
    cv, jd = pair.cv, pair.jd
    if cv is None or cv.explicit is None or jd is None or jd.explicit is None:
        return pair
    required = {_id(item.skill_id) for item in ExtractionDataAdapter.extract_active_skills(jd.model_copy(deep=True)).active_skills}
    active = ExtractionDataAdapter.extract_active_skills(cv.model_copy(deep=True)).active_skills
    evidence: dict[str, set[str]] = {}
    for item in active:
        evidence.setdefault(_id(item.skill_id), set()).update(_anchored_spans(item.raw_skill, cv_text))
    redirects = _resume_redirects(evidence, required)
    if not redirects:
        return pair

    updated = cv.model_copy(deep=True)
    updated.explicit.skills = _merge_explicit_redirects(updated.explicit.skills, redirects)
    for items in (updated.validation.accepted_implicit_skills, updated._verified_resume_skills):
        for index, item in enumerate(items):
            if target := redirects.get(_id(item.skill_id)):
                items[index] = item.model_copy(update={"skill_id": target})
    explicit = {skill.skill_id: _anchored_spans(skill, cv_text) for skill in updated.explicit.skills
                if skill.skill_id in redirects.values()}
    updated._verified_resume_skills = [
        skill for skill in updated._verified_resume_skills
        if skill.skill_id not in explicit or not _anchored_spans(skill, cv_text) <= explicit[skill.skill_id]
    ]
    return pair.model_copy(update={"cv": updated})

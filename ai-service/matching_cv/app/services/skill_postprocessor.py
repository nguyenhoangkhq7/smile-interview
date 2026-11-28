"""Service responsible for post-processing and validating skill extractions."""
import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional, Tuple

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.skill_extraction import (
    CategoryType,
    Evidence,
    ExtractedSkill,
    ExtractionMeta,
    ExtractionResult,
    ExtractionStats,
    KindSourceType,
    KindType,
    RawExtraction,
    RawSkillMention,
    check_verbatim_mention,
)
from matching_cv.app.services.competency_extraction_quality import (
    INTEGRATION_TEST_SKILL_ID,
    INTEGRATION_TEST_VARIANTS,
    is_domain_skill,
    refine_competency_entities,
)
from matching_cv.app.services.section_tagger import find_section_spans, section_at
from matching_cv.app.services.text_locator import locate_mention_in_sentence, locate_sentence
from matching_cv.research.data.canonical_skill_normalizer import DOMAIN_SKILL_ALIASES, ENGINEERING_COMPETENCY_ALIASES



VALID_CATEGORIES = {
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Certification",
    "Technical Standard",
}

VALID_KINDS = {
    "skill",
    "domain",
    "context",
    "certification",
    "education",
    "industry",
    "experience_years",
    "job_title",
}

# Deterministic guard: regex for years-of-experience patterns (English & Vietnamese)
YEARS_OF_EXPERIENCE_PATTERN = re.compile(
    r"^(?:(?:at\s+least|minimum(?:\s+of)?|min\.?|over|more\s+than|under|up\s+to|ít\s+nhất|tối\s+thiểu|trên|hơn|khoảng)\s+)?"
    r"\d+(?:\s*[\-\–\—\~tođến]+\s*\d+|\s*\+)?"
    r"\s*(?:years?|yrs?|năm)"
    r"(?:\s+(?:of\s+)?(?:[a-zA-ZÀ-ỹ\-]+\s+){0,3}(?:experience|kinh\s+nghiệm|làm\s+việc))?$"
    r"|"
    r"\b\d+(?:\s*[\-\–\—\~tođến]+\s*\d+|\s*\+)?\s*(?:years?|yrs?|năm)\s+(?:of\s+)?(?:[a-zA-ZÀ-ỹ\-]+\s+){0,2}(?:experience|kinh\s+nghiệm)\b",
    re.IGNORECASE,
)

# Deterministic guard: stoplist mapped to non-skill kinds, applied regardless of LLM kind
STOPLIST_KIND_MAP: Dict[str, KindType] = {
    # Bare certification words (no proper name)
    "certification": "certification",
    "certifications": "certification",
    "certificate": "certification",
    "certificates": "certification",
    "chứng chỉ": "certification",
    "chứng nhận": "certification",
    "bằng cấp": "certification",
    "chứng chỉ liên quan": "certification",
    "chứng chỉ chuyên môn": "certification",
    "professional certification": "certification",
    # Experience phrases
    "professional experience": "experience_years",
    "work experience": "experience_years",
    "working experience": "experience_years",
    "kinh nghiệm làm việc": "experience_years",
    "kinh nghiệm chuyên môn": "experience_years",
    "kinh nghiệm thực tế": "experience_years",
    "kinh nghiệm": "experience_years",
    # Environment / production phrases
    "production environment": "context",
    "production environments": "context",
    "môi trường sản xuất": "context",
    "môi trường production": "context",
    "môi trường vận hành": "context",
    "môi trường thực tế": "context",
    "production services": "context",
    "production service": "context",
    "dịch vụ sản xuất": "context",
    "dịch vụ production": "context",
    "production issues": "context",
    "production issue": "context",
    "debugging production issues": "context",
    "sự cố sản xuất": "context",
    "sự cố production": "context",
    "lỗi môi trường sản xuất": "context",
    "lỗi sản xuất": "context",
    # People / roles
    "product managers": "job_title",
    "product manager": "job_title",
    "quản lý sản phẩm": "job_title",
    "giám đốc sản phẩm": "job_title",
    # Education / majors
    "computer science": "education",
    "khoa học máy tính": "education",
    "software engineering": "education",
    "kỹ thuật phần mềm": "education",
    "information technology": "education",
    "công nghệ thông tin": "education",
    "information systems": "education",
    "hệ thống thông tin": "education",
    # Industry labels
    "it - software": "industry",
    "it - phần mềm": "industry",
    "cntt - phần mềm": "industry",
    # Generic duties & context artifacts
    "debugging": "context",
    "gỡ lỗi": "context",
    "troubleshooting": "context",
    "xử lý sự cố": "context",
    "code review": "context",
    "code reviews": "context",
    "review code": "context",
    "đánh giá mã nguồn": "context",
    "on-call rotation": "context",
    "on-call": "context",
    "trực on-call": "context",
    "order-management microservice": "context",
    "payment module": "context",
    "high write throughput": "context",
    "technical designs": "context",
    "thiết kế kỹ thuật": "context",
    # Adjectives, buzzwords & non-skill project descriptions
    "ai-powered": "context",
    "ai-assisted": "context",
    "ai-assisted development": "context",
    "type-safe": "context",
    "responsive ui": "context",
    "eisenhower matrix": "context",
    "interval-merging approach": "context",
    "rule-based auto-scheduling algorithm": "context",
    "email otp": "context",
    "real-time chat": "context",
    "chat module": "context",
    # Generic actions, UI effects & common nouns
    "migrations": "context",
    "migration": "context",
    "database migrations": "context",
    "database migration": "context",
    "authentication": "context",
    "authorization": "context",
    "form validation": "context",
    "data validation": "context",
    "validation": "context",
    "optimistic updates": "context",
    "optimistic update": "context",
    "client-side caching": "context",
    "third-party api integration": "context",
    "api integration": "context",
    "task planning": "context",
    "progress tracking": "context",
    "coding standards": "context",
    "database schema discussions": "context",
    "technical documentation": "context",
    "writing technical documentation": "context",
}

# Deterministic pattern guard for ad-hoc project approach/algorithm/buzzword phrases and online course titles
NON_SKILL_PHRASE_PATTERN = re.compile(
    r"^(?:ai|ml)[\-\s]+(?:powered|assisted|driven)(?:\s+[a-z0-9\-]+)*$"
    r"|"
    r"^rule[\-\s]+based\s+.+$"
    r"|"
    r"^.+\s+(?:approach|algorithm|discussions)$"
    r"|"
    r"^the\s+ultimate\s+.+$"
    r"|"
    r"\b(?:part\s+\d+\s*(?:&|and)\s*\d+|code\s+with\s+mosh|udemy|coursera)\b",
    re.IGNORECASE,
)

# Unconditional canonical skill_id normalization map (preserves surface_forms and evidences)
CANONICAL_SKILL_ID_MAP: Dict[str, str] = {
    **dict.fromkeys(INTEGRATION_TEST_VARIANTS, INTEGRATION_TEST_SKILL_ID),
    **ENGINEERING_COMPETENCY_ALIASES,
    "javascript-es6": "javascript",
    "javascript-es6+": "javascript",
    "es6": "javascript",
    "es6+": "javascript",
    "html5": "html",
    "css3": "css",
    "wcag-aa": "wcag",
    "wcag-aaa": "wcag",
    "wcag-2.0": "wcag",
    "wcag-2.1": "wcag",
    "wcag-2.2": "wcag",
    "next.js-app-router": "next.js",
    "nextjs-app-router": "next.js",
    "next.js-pages-router": "next.js",
    "graphql-api": "graphql",
    "graphql-apis": "graphql",
    "restful-apis": "rest-api",
    "rest-apis": "rest-api",
    "rest-api-development": "rest-api",
    "apache-kafka": "kafka",
    "restful-api": "rest-api",
    "express.js": "express",
}

# Parent-child sub-tool consolidation map (merged when both co-occur in the same document)
PARENT_TOOL_CONSOLIDATION_MAP: Dict[str, str] = {
    "docker-compose": "docker",
    "next.js-app-router": "next.js",
    "graphql-apis": "graphql",
    "graphql-api": "graphql",
    "rest-apis": "rest",
    "rest-api": "rest",
    "restful-apis": "rest",
    "restful-api": "rest",
}

# Protected slash-containing terms that represent a single atomic concept and must not be split
PROTECTED_SLASH_PREFIXES: Tuple[str, ...] = (
    "ci/cd",
    "ci / cd",
    "tcp/ip",
    "udp/ip",
    "http/1",
    "http/2",
    "http/3",
    "ssl/tls",
    "tls/ssl",
    "pl/sql",
    "os/2",
    "z/os",
    "as/400",
    "i/o",
    "ui/ux",
    "ux/ui",
    "a/b",
    "pub/sub",
    "publish/subscribe",
    "etl/elt",
    "ar/vr",
    "vr/ar",
    "ai/ml",
    "ml/ai",
    "active/active",
    "active/passive",
    "blue/green",
    "master/slave",
    "client/server",
    "read/write",
)

# Trailing generic suffixes attached to slash-combined skill mentions (e.g. "REST/GraphQL API integration")
SLASH_TRAILING_GENERIC_SUFFIX_RE = re.compile(
    r"\s+(?:apis?\s+integrations?|api\s+development|apis?|integrations?|backends?|frontends?|frameworks?|libraries|tools?|stack|endpoints?|services?)$",
    re.IGNORECASE,
)

# Architecture / design synonym group (merged into canonical representative when co-occurring)
ARCHITECTURE_SYNONYM_GROUP = {
    "system-design",
    "system-architecture",
    "full-stack-architecture",
    "software-architecture",
}
ARCHITECTURE_PREFERENCE_ORDER = [
    "system-design",
    "system-architecture",
    "software-architecture",
    "full-stack-architecture",
]

# Regex for versioned tool skill_id: e.g. "java-21" -> base "java", "python-3.11" -> "python"
VERSIONED_SKILL_ID_PATTERN = re.compile(r"^([a-z0-9\.\-]+?)-v?\d+(?:\.\d+)*$")

GENERIC_CERTIFICATION_WORDS = {
    "certification",
    "certifications",
    "certificate",
    "certificates",
    "certified",
    "credential",
    "credentials",
    "requirement",
    "requirements",
    "professional",
    "industry",
    "relevant",
    "related",
    "valid",
    "active",
    "in",
    "of",
    "for",
    "and",
    "or",
    "a",
    "an",
    "the",
    "chứng",
    "chỉ",
    "nhận",
    "bằng",
    "cấp",
    "liên",
    "quan",
    "chuyên",
    "môn",
    "ngành",
    "yêu",
    "cầu",
    "hoặc",
    "và",
    "có",
    "ưu",
    "tiên",
}


def normalize_guard_phrase(text: str) -> str:
    """Normalize whitespace, dashes, and case for deterministic stoplist lookup."""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s*[\-\–\—]\s*", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


STOPLIST_KIND_MAP = {normalize_guard_phrase(k): v for k, v in STOPLIST_KIND_MAP.items()}


def has_certification_proper_name(surface_form: str) -> bool:
    """Return True only when a certification surface form contains a proper name (not just certification/chứng chỉ)."""
    norm = normalize_guard_phrase(surface_form)
    if not norm or norm in STOPLIST_KIND_MAP:
        return False
    raw_tokens = re.findall(r"[\w\+\#\.]+", unicodedata.normalize("NFKC", surface_form or ""))
    non_generic = [t for t in raw_tokens if t.casefold() not in GENERIC_CERTIFICATION_WORDS]
    if not non_generic:
        return False
    return any(any(ch.isupper() or ch.isdigit() for ch in tok) for tok in non_generic)



class SkillPostprocessor:
    """Post-processor for raw LLM extraction into final ExtractionResult contract."""

    @staticmethod
    def slugify_skill(surface_form: str) -> str:
        """Compute canonical slug from surface_form with inflectional role normalization."""
        slug = re.sub(r"[^\w\-\.]+|_+", "-", unicodedata.normalize("NFKC", surface_form).lower()).strip("-.")
        # Normalize inflectional plural role suffixes (e.g. frontends -> frontend)
        slug = re.sub(r"-backends$", "-backend", slug)
        slug = re.sub(r"-frontends$", "-frontend", slug)
        slug = re.sub(r"-pipelines$", "-pipeline", slug)
        slug = re.sub(r"-systems$", "-system", slug)
        if not slug or not slug[0].isalnum():
            return f"unmapped:{slug if slug else 'unknown'}"
        return slug

    @staticmethod
    def apply_deterministic_guard(
        surface_form: str,
        kind: Optional[KindType],
    ) -> Tuple[Optional[KindType], bool]:
        """
        Apply deterministic guard (years-of-experience regex, stoplist, and non-skill phrase patterns)
        regardless of LLM kind.
        Returns (effective_kind, blocked_by_guard).
        """
        norm_sf = normalize_guard_phrase(surface_form)
        if YEARS_OF_EXPERIENCE_PATTERN.search(norm_sf):
            return "experience_years", True
        if norm_sf in STOPLIST_KIND_MAP:
            return STOPLIST_KIND_MAP[norm_sf], True
        if NON_SKILL_PHRASE_PATTERN.search(norm_sf):
            return "context", True
        return kind, False

    @classmethod
    def split_slash_skill_mention(
        cls,
        surface_form: str,
        kind: Optional[str],
        category: Optional[str],
        sentence: str,
    ) -> Optional[List[str]]:
        """
        Deterministically split slash-combined skill mentions (e.g. 'ESLint/Prettier',
        'REST/GraphQL API integration', 'REST/GraphQL APIs', 'JavaScript/TypeScript')
        into their independent constituent skills while protecting atomic slash terms
        ('CI/CD', 'TCP/IP', 'PL/SQL', etc.) and domain phrases ('booking/inventory systems').
        """
        if not surface_form or "/" not in surface_form or not sentence:
            return None
        if kind in ("domain", "certification", "education", "industry", "experience_years", "job_title", "context"):
            return None
        if category in ("Domain Knowledge", "Certification"):
            return None

        norm_sf = normalize_guard_phrase(surface_form)
        if norm_sf.startswith(PROTECTED_SLASH_PREFIXES):
            return None

        core_sf = SLASH_TRAILING_GENERIC_SUFFIX_RE.sub("", surface_form.strip()).strip()
        if "/" not in core_sf:
            return None

        parts = [p.strip() for p in core_sf.split("/") if p.strip()]
        if len(parts) < 2:
            return None

        for p in parts:
            if len(p) < 2 or not any(ch.isalpha() for ch in p):
                return None
            if normalize_guard_phrase(p) in STOPLIST_KIND_MAP:
                return None
            if not check_verbatim_mention(p, sentence):
                return None

        return parts

    @classmethod
    def _expand_slash_compound_raw_items(cls, raw_items: List[Any]) -> List[Any]:
        """
        Expand slash-combined skill mentions in raw_items into separate constituent items
        and deduplicate against already-present (mention.casefold(), sentence) pairs.
        If no item in raw_items qualifies for slash splitting, returns raw_items unchanged.
        """
        has_split = False
        existing_pairs = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            sf = item.get("surface_form") if "surface_form" in item else item.get("mention")
            sent = item.get("sentence") if "sentence" in item else item.get("source_sentence")
            if isinstance(sf, str) and isinstance(sent, str):
                parts = cls.split_slash_skill_mention(
                    sf,
                    item.get("kind"),
                    item.get("category"),
                    sent,
                )
                if parts is not None:
                    has_split = True
                else:
                    existing_pairs.add((sf.strip().casefold(), sent.strip()))

        if not has_split:
            return raw_items

        expanded: List[Any] = []
        emitted_split_pairs = set(existing_pairs)
        for item in raw_items:
            if not isinstance(item, dict):
                expanded.append(item)
                continue
            sf = item.get("surface_form") if "surface_form" in item else item.get("mention")
            sent = item.get("sentence") if "sentence" in item else item.get("source_sentence")
            if isinstance(sf, str) and isinstance(sent, str):
                parts = cls.split_slash_skill_mention(
                    sf,
                    item.get("kind"),
                    item.get("category"),
                    sent,
                )
                if parts is not None:
                    sf_key = "surface_form" if "surface_form" in item else "mention"
                    for p in parts:
                        pair_key = (p.casefold(), sent.strip())
                        if pair_key not in emitted_split_pairs:
                            emitted_split_pairs.add(pair_key)
                            cloned = dict(item)
                            cloned[sf_key] = p
                            expanded.append(cloned)
                    continue
            expanded.append(item)

        return expanded

    @classmethod
    def _consolidate_duplicate_skills(
        cls, skills: List[ExtractedSkill]
    ) -> List[ExtractedSkill]:
        """
        Deterministically normalize and consolidate redundant explicit skills within a document
        while preserving all surface forms, sections, and evidences:
        0. Unconditional canonical skill_id normalization (e.g. 'next.js-app-router' -> 'next.js',
           'graphql-apis' -> 'graphql', 'javascript-es6' -> 'javascript', 'css3' -> 'css',
           'html5' -> 'html', 'wcag-aa' -> 'wcag').
        1. Versioned tool -> base tool (e.g. 'java-21' -> 'java' when 'java' is present).
        2. Parent-child sub-tool -> parent tool (e.g. 'docker-compose' -> 'docker' when 'docker' is present).
        3. Architecture synonym group -> canonical representative (e.g. 'full-stack-architecture' and
           'system-architecture' -> 'system-design').
        """
        if not skills:
            return skills

        # Phase 0: Unconditional canonical skill_id normalization & merging
        canonicalized_by_id: Dict[str, ExtractedSkill] = {}
        canonicalized_list: List[ExtractedSkill] = []
        for s in skills:
            target_id = CANONICAL_SKILL_ID_MAP.get(s.skill_id, s.skill_id)
            if is_domain_skill(s):
                target_id = DOMAIN_SKILL_ALIASES.get(target_id, target_id)
            if target_id in canonicalized_by_id:
                target_skill = canonicalized_by_id[target_id]
                for sf in s.surface_forms:
                    if sf not in target_skill.surface_forms:
                        target_skill.surface_forms.append(sf)
                for sec in s.sections:
                    if sec not in target_skill.sections:
                        target_skill.sections.append(sec)
                target_skill.evidences.extend(s.evidences)
            else:
                if target_id != s.skill_id:
                    s.skill_id = target_id
                canonicalized_by_id[target_id] = s
                canonicalized_list.append(s)

        skills = canonicalized_list
        if len(skills) <= 1:
            return skills

        skill_map: Dict[str, ExtractedSkill] = {s.skill_id: s for s in skills}

        # Determine canonical target for architecture synonym group if >= 2 co-occur
        arch_present = [s.skill_id for s in skills if s.skill_id in ARCHITECTURE_SYNONYM_GROUP]
        arch_target: Optional[str] = None
        if len(arch_present) >= 2:
            for pref in ARCHITECTURE_PREFERENCE_ORDER:
                if pref in skill_map:
                    arch_target = pref
                    break
            if arch_target is None:
                arch_target = arch_present[0]

        redirect_map: Dict[str, str] = {}
        for s in skills:
            sid = s.skill_id
            # 1. Versioned tool check (R4)
            m_ver = VERSIONED_SKILL_ID_PATTERN.match(sid)
            if m_ver:
                base_id = m_ver.group(1)
                if base_id in skill_map and base_id != sid:
                    redirect_map[sid] = base_id
                    continue

            # 2. Explicit parent-child sub-tool check
            if sid in PARENT_TOOL_CONSOLIDATION_MAP:
                parent_id = PARENT_TOOL_CONSOLIDATION_MAP[sid]
                if parent_id in skill_map and parent_id != sid:
                    redirect_map[sid] = parent_id
                    continue

            # 3. Architecture synonym group check
            if arch_target and sid in ARCHITECTURE_SYNONYM_GROUP and sid != arch_target:
                redirect_map[sid] = arch_target

        if not redirect_map:
            return skills

        for child_id, target_id in redirect_map.items():
            # Follow transitive redirects if any
            while target_id in redirect_map:
                target_id = redirect_map[target_id]
            child_skill = skill_map[child_id]
            target_skill = skill_map[target_id]
            for sf in child_skill.surface_forms:
                if sf not in target_skill.surface_forms:
                    target_skill.surface_forms.append(sf)
            for sec in child_skill.sections:
                if sec not in target_skill.sections:
                    target_skill.sections.append(sec)
            target_skill.evidences.extend(child_skill.evidences)

        return [s for s in skills if s.skill_id not in redirect_map]

    @classmethod
    def is_retained_skill_entity(cls, entity: ExtractedSkill) -> bool:
        """
        Single routing boundary check:
        Only kind=='skill' and kind=='certification' whose surface form contains a proper name
        (and not matched by the deterministic guard) become skill entries.
        If ROUTE_DOMAIN_TO_SKILLS is True, kind=='domain' with category=='Domain Knowledge'
        stays in skills as before Stage A.
        """
        for sf in entity.surface_forms:
            _, blocked = cls.apply_deterministic_guard(sf, entity.kind)
            if blocked:
                return False
        if entity.kind == "skill":
            return True
        if entity.kind == "certification":
            return any(has_certification_proper_name(sf) for sf in entity.surface_forms)
        if getattr(settings, "ROUTE_DOMAIN_TO_SKILLS", True):
            if entity.kind == "domain" and entity.category == "Domain Knowledge":
                return True
        return False

    @classmethod
    def _route_and_build_result(
        cls,
        *,
        entities: List[ExtractedSkill],
        quarantined: List[Dict[str, Any]],
        text: Optional[str],
        filename: Optional[str],
        document_type: Optional[Literal["CV", "JD"]],
        extraction_meta: Optional[ExtractionMeta],
        is_compact: bool = False,
    ) -> ExtractionResult:
        skills: List[ExtractedSkill] = []
        non_skill_entities: List[ExtractedSkill] = []
        for entity in refine_competency_entities(entities, text, document_type):
            if cls.is_retained_skill_entity(entity):
                skills.append(entity)
            else:
                non_skill_entities.append(entity)

        skills = cls._consolidate_duplicate_skills(skills)

        all_entities = skills + non_skill_entities
        total_mentions = sum(len(s.evidences) for s in all_entities)
        unique_skills = len(skills)
        non_skill_count = len(non_skill_entities)
        unresolved_evidences = sum(
            1 for s in all_entities for ev in s.evidences if not ev.offset_resolved
        )
        non_verbatim_mentions = sum(
            1 for s in all_entities for ev in s.evidences if not ev.verbatim_ok
        )
        kind_conflicts = (
            0
            if is_compact
            else sum(
                1
                for s in all_entities
                if len({ev.kind for ev in s.evidences if ev.kind is not None}) > 1
            )
        )
        header_evidences = sum(
            1
            for s in all_entities
            for ev in s.evidences
            if ev.offset_resolved and ev.section == "header"
        )
        if is_compact:
            unresolved_mentions = sum(
                1 for s in all_entities if not any(ev.offset_resolved for ev in s.evidences)
            )
            ambiguous_mentions = sum(
                1
                for s in all_entities
                for ev in s.evidences
                if getattr(ev, "mention_ambiguous", False)
            )
            unknown_category_mentions = sum(
                1 for s in all_entities for ev in s.evidences if ev.category is None
            )
            invalid_kind_mentions = 0
        else:
            unresolved_mentions = sum(
                1 for s in all_entities for ev in s.evidences if ev.mention_start is None
            )
            ambiguous_mentions = sum(
                1 for s in all_entities for ev in s.evidences if ev.mention_ambiguous
            )
            unknown_category_mentions = sum(
                1
                for s in all_entities
                for ev in s.evidences
                if ev.category_raw is not None and ev.category is None
            )
            invalid_kind_mentions = sum(
                1 for s in all_entities for ev in s.evidences if ev.kind is None
            )
        quarantined_mentions = len(quarantined)

        kind_counts: Dict[str, int] = {}
        mention_kind_counts: Dict[str, int] = {}
        for entity in all_entities:
            k_key = entity.kind or "invalid"
            kind_counts[k_key] = kind_counts.get(k_key, 0) + 1
            for ev in entity.evidences:
                ev_k = ev.kind or "invalid"
                mention_kind_counts[ev_k] = mention_kind_counts.get(ev_k, 0) + 1

        stats = ExtractionStats(
            total_mentions=total_mentions,
            unique_skills=unique_skills,
            unresolved_evidences=unresolved_evidences,
            kind_conflicts=kind_conflicts,
            non_verbatim_mentions=non_verbatim_mentions,
            header_evidences=header_evidences,
            unresolved_mentions=unresolved_mentions,
            ambiguous_mentions=ambiguous_mentions,
            unknown_category_mentions=unknown_category_mentions,
            invalid_kind_mentions=invalid_kind_mentions,
            quarantined_mentions=quarantined_mentions,
            non_skill_count=non_skill_count,
            kind_counts=kind_counts,
            mention_kind_counts=mention_kind_counts,
        )

        text_sha256 = (
            hashlib.sha256(text.encode("utf-8")).hexdigest()
            if (text is not None and not is_compact)
            else None
        )

        skill_clusters = []
        topic_group_hint = []
        certification_hint_pairs = []

        if getattr(settings, "SKILL_CLUSTERING_ENABLED", False):
            from matching_cv.app.services.skill_clustering_service import skill_clustering_service

            clustering_res = skill_clustering_service.cluster_skills(skills)
            skill_clusters = clustering_res.clusters
            topic_group_hint = clustering_res.topic_group_hint
            certification_hint_pairs = clustering_res.certification_hint_pairs

        return ExtractionResult(
            filename=filename,
            document_type=document_type,
            text_sha256=text_sha256,
            stats=stats,
            skills=skills,
            non_skill_entities=non_skill_entities,
            quarantined=quarantined,
            extraction_meta=extraction_meta,
            skill_clusters=skill_clusters,
            topic_group_hint=topic_group_hint,
            certification_hint_pairs=certification_hint_pairs,
        )

    def refine_cached_extraction(
        self, result: ExtractionResult, text: str, side: Literal["CV", "JD"]
    ) -> ExtractionResult:
        """Apply current extraction rules to previous outputs tied to this document."""
        snapshot = result.model_copy(deep=True)
        compact = bool(snapshot.extraction_meta and snapshot.extraction_meta.schema_version == "explicit_compact_v1")
        return self._route_and_build_result(
            entities=snapshot.skills + snapshot.non_skill_entities,
            quarantined=snapshot.quarantined,
            text=text,
            filename=snapshot.filename,
            document_type=side,
            extraction_meta=snapshot.extraction_meta,
            is_compact=compact,
        )

    def process_extraction(
        self,
        raw_result: Any,
        text: str,
        filename: Optional[str] = None,
        document_type: Optional[Literal["CV", "JD"]] = None,
        extraction_meta: Optional[ExtractionMeta] = None,
    ) -> ExtractionResult:
        """
        Validate and post-process raw LLM extraction into final ExtractionResult contract:
        - Validates via RawExtraction schema.
        - Computes canonical skill_id (slug) for each surface_form.
        - Preserves raw category string in category_raw; sets category if in 6 known categories.
        - Locates sentence offsets (start, end) into cleaned document text.
        - If sentence is NOT found in cleaned text, sets start=None, end=None, offset_resolved=False.
        - Preserves LLM kind with kind_source='llm', or infers from category with kind_source='inferred'.
        - Verifies verbatim occurrence (surface_form in sentence, casefold, whitespace-tolerant) -> verbatim_ok.
        - Locates mention offsets (mention_start, mention_end) inside evidence span text[ev.start:ev.end].
        - Deduplicates mentions into canonical skills while preserving unique surface_forms and merging evidences.
        - Derives canonical skill kind from its first evidence.
        - Computes stats including unresolved_mentions, ambiguous_mentions, and unknown_category_mentions.
        - Enforces ExtractionResult invariants.
        """
        if extraction_meta is None and isinstance(raw_result, dict):
            meta_dict = raw_result.get("extraction_meta") or raw_result.get("_extraction_meta")
            if meta_dict and isinstance(meta_dict, dict):
                try:
                    extraction_meta = ExtractionMeta.model_validate(meta_dict)
                except Exception:
                    pass

        raw_items: List[Any] = []
        if isinstance(raw_result, dict):
            items_candidate = raw_result.get("skills") if "skills" in raw_result else raw_result.get("explicit_skills")
            if items_candidate is not None:
                raw_items = items_candidate if isinstance(items_candidate, list) else [items_candidate]
        elif isinstance(raw_result, list):
            raw_items = raw_result
        elif hasattr(raw_result, "skills"):
            raw_items = getattr(raw_result, "skills")
        elif hasattr(raw_result, "explicit_skills"):
            raw_items = getattr(raw_result, "explicit_skills")

        section_spans = find_section_spans(text, document_type or "CV") if text else []
        skills_by_id: Dict[str, ExtractedSkill] = {}
        quarantined: List[Dict[str, Any]] = []

        # Detect compact extraction schema (explicit_compact_v1)
        is_compact = False
        if extraction_meta and getattr(extraction_meta, "schema_version", None) == "explicit_compact_v1":
            is_compact = True
        elif isinstance(raw_result, dict) and raw_result.get("schema_version") == "explicit_compact_v1":
            is_compact = True
        elif raw_items and all(
            isinstance(it, dict)
            and ("mention" in it or "name" in it)
            and ("sentence" not in it and "source_sentence" not in it)
            for it in raw_items
        ):
            is_compact = True

        if is_compact:
            from matching_cv.app.services.span_first_locator import SpanFirstLocator
            locator = SpanFirstLocator(doc_type=document_type or "CV")

            for item in raw_items:
                if not isinstance(item, dict):
                    quarantined.append({
                        "raw_item": item,
                        "errors": [f"Item is not a dictionary / object (got {type(item).__name__})"],
                    })
                    continue

                name_val = item.get("name") or item.get("mention")
                mention_val = item.get("mention") or item.get("surface_form")
                if not mention_val or not str(mention_val).strip():
                    quarantined.append({
                        "raw_item": item,
                        "errors": ["Missing required field 'mention' (or 'surface_form') in compact item"],
                    })
                    continue

                mention_str = str(mention_val).strip()
                name_str = str(name_val).strip() if name_val else mention_str
                skill_id = self.slugify_skill(name_str)

                raw_category = item.get("category", "Technology/Tool")
                category: Optional[CategoryType] = (
                    raw_category if raw_category in VALID_CATEGORIES else None  # type: ignore[assignment]
                )
                inferred_kind: KindType = (
                    "domain"
                    if category == "Domain Knowledge"
                    else ("certification" if category == "Certification" else "skill")
                )
                eff_kind, _ = self.apply_deterministic_guard(mention_str, inferred_kind)

                grounded_mentions = locator.locate_mention(
                    document_text=text,
                    mention=mention_str,
                    section_spans=section_spans,
                    return_all_matches=True,
                )

                for gm in grounded_mentions:
                    gm_kind, _ = self.apply_deterministic_guard(gm.surface_form or mention_str, eff_kind)
                    evidence = Evidence(
                        surface_form=gm.surface_form,
                        kind=gm_kind,
                        kind_raw=gm_kind,
                        kind_source="inferred",
                        category=category,
                        category_raw=raw_category,
                        sentence=gm.sentence,
                        start=gm.start,
                        end=gm.end,
                        offset_resolved=gm.offset_resolved,
                        verbatim_ok=gm.verbatim_ok,
                        modifier_text=None,
                        section=gm.section,
                        mention_start=gm.mention_start,
                        mention_end=gm.mention_end,
                        mention_ambiguous=gm.is_ambiguous,
                    )

                    if skill_id in skills_by_id:
                        existing_skill = skills_by_id[skill_id]
                        existing_skill.evidences.append(evidence)
                        if gm.surface_form and gm.surface_form not in existing_skill.surface_forms:
                            existing_skill.surface_forms.append(gm.surface_form)
                        if gm.section and gm.section not in existing_skill.sections:
                            existing_skill.sections.append(gm.section)
                    else:
                        initial_sections = [gm.section] if gm.section else []
                        skills_by_id[skill_id] = ExtractedSkill(
                            skill_id=skill_id,
                            surface_forms=[gm.surface_form] if gm.surface_form else [mention_str],
                            category=category,
                            category_raw=raw_category,
                            kind=gm_kind,
                            type="explicit",
                            confidence=None,
                            sections=initial_sections,
                            evidences=[evidence],
                        )

            if extraction_meta is None:
                from datetime import datetime, timezone
                extraction_meta = ExtractionMeta(
                    prompt_sha256="compact_span_first_sha256",
                    prompt_variant="COMPACT",
                    model_configured="compact_extractor",
                    extracted_at=datetime.now(timezone.utc).isoformat(),
                    schema_version="explicit_compact_v1",
                )

            return self._route_and_build_result(
                entities=list(skills_by_id.values()),
                quarantined=quarantined,
                text=text,
                filename=filename,
                document_type=document_type,
                extraction_meta=extraction_meta,
                is_compact=True,
            )

        # Legacy Extraction Path (schema_version != explicit_compact_v1)
        raw_items = self._expand_slash_compound_raw_items(raw_items)
        for item in raw_items:
            # Check structural requirements
            if not isinstance(item, dict):
                quarantined.append({
                    "raw_item": item,
                    "errors": [f"Item is not a dictionary / object (got {type(item).__name__})"],
                })
                continue

            sf_val = item.get("surface_form") if "surface_form" in item else item.get("mention")
            sent_val = item.get("sentence") if "sentence" in item else item.get("source_sentence")

            errors: List[str] = []
            if sf_val is None:
                errors.append("Missing required field 'surface_form' (or 'mention')")
            elif not isinstance(sf_val, str):
                errors.append(f"Field 'surface_form' must be a string, got {type(sf_val).__name__}")
            elif not sf_val.strip():
                errors.append("Field 'surface_form' must not be empty or whitespace")

            if sent_val is None:
                errors.append("Missing required field 'sentence' (or 'source_sentence')")
            elif not isinstance(sent_val, str):
                errors.append(f"Field 'sentence' must be a string, got {type(sent_val).__name__}")
            elif not sent_val.strip():
                errors.append("Field 'sentence' must not be empty or whitespace")

            if errors:
                quarantined.append({
                    "raw_item": item,
                    "errors": errors,
                })
                continue

            try:
                mention_item = RawSkillMention.model_validate(item)
            except Exception as exc:
                quarantined.append({
                    "raw_item": item,
                    "errors": [f"Pydantic validation error: {str(exc)}"],
                })
                continue

            surface_form = mention_item.surface_form.strip()
            skill_id = self.slugify_skill(surface_form)

            raw_category = mention_item.category
            if raw_category in VALID_CATEGORIES:
                category = raw_category  # type: ignore[assignment]
            else:
                category = None

            # Resolve kind and kind_source: explicit LLM kind wins over category inference
            raw_kind = mention_item.kind
            if raw_kind is not None:
                raw_kind_str = str(raw_kind).strip().lower()
                if raw_kind_str in VALID_KINDS:
                    kind: Optional[KindType] = raw_kind_str  # type: ignore[assignment]
                    kind_raw = str(raw_kind)
                    kind_source: KindSourceType = "llm"
                else:
                    kind = None
                    kind_raw = str(raw_kind)
                    kind_source = "invalid"
            else:
                kind_raw = None
                if category == "Domain Knowledge":
                    kind = "domain"
                    kind_source = "inferred"
                elif category == "Certification":
                    kind = "certification"
                    kind_source = "inferred"
                else:
                    kind = "skill"
                    kind_source = "inferred"

            # Apply deterministic guard regardless of LLM kind
            kind, _ = self.apply_deterministic_guard(surface_form, kind)

            # Compute character offsets of sentence in raw_text using whitespace-tolerant locator
            sentence = mention_item.sentence
            span = locate_sentence(text, sentence)
            if span is not None:
                start: Optional[int] = span[0]
                end: Optional[int] = span[1]
                offset_resolved = True
                sentence_span_text = text[start:end]
                rel_start, rel_end, is_ambiguous = locate_mention_in_sentence(
                    sentence_span_text, surface_form
                )
                if rel_start is not None and rel_end is not None:
                    mention_start: Optional[int] = start + rel_start
                    mention_end: Optional[int] = start + rel_end
                    mention_ambiguous = is_ambiguous
                else:
                    mention_start = None
                    mention_end = None
                    mention_ambiguous = False
            else:
                start = None
                end = None
                offset_resolved = False
                mention_start = None
                mention_end = None
                mention_ambiguous = False

            evidence_section = section_at(section_spans, start) if start is not None else None
            verbatim_ok = check_verbatim_mention(surface_form, sentence)

            evidence = Evidence(
                surface_form=surface_form,
                kind=kind,
                kind_raw=kind_raw,
                kind_source=kind_source,
                category=category,
                category_raw=raw_category,
                sentence=sentence,
                start=start,
                end=end,
                offset_resolved=offset_resolved,
                verbatim_ok=verbatim_ok,
                modifier_text=mention_item.modifier_text,
                section=evidence_section,
                mention_start=mention_start,
                mention_end=mention_end,
                mention_ambiguous=mention_ambiguous,
            )

            if skill_id in skills_by_id:
                # Merge evidence into existing canonical skill
                existing_skill = skills_by_id[skill_id]
                existing_skill.evidences.append(evidence)
                if surface_form not in existing_skill.surface_forms:
                    existing_skill.surface_forms.append(surface_form)
                if evidence_section and evidence_section not in existing_skill.sections:
                    existing_skill.sections.append(evidence_section)
            else:
                initial_sections = [evidence_section] if evidence_section else []
                skills_by_id[skill_id] = ExtractedSkill(
                    skill_id=skill_id,
                    surface_forms=[surface_form],
                    category=category,
                    category_raw=raw_category,
                    kind=kind,
                    type="explicit",
                    confidence=None,
                    sections=initial_sections,
                    evidences=[evidence],
                )

        return self._route_and_build_result(
            entities=list(skills_by_id.values()),
            quarantined=quarantined,
            text=text,
            filename=filename,
            document_type=document_type,
            extraction_meta=extraction_meta,
            is_compact=False,
        )


skill_postprocessor = SkillPostprocessor()

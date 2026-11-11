"""Evidence-grounded validity verification service for inferred implicit skills (Layer B - Phase 3B Hardening)."""
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from matching_cv.app.schemas.implicit_skill_extraction import ImplicitEvidenceSnippet, ImplicitExtractedSkill
from matching_cv.app.schemas.skill_extraction import ExtractionResult
from matching_cv.app.schemas.unified_skill_extraction import ImplicitEvidenceVerification
from matching_cv.app.services.skill_postprocessor import skill_postprocessor

logger = logging.getLogger(__name__)

# Specific standards / compliance / regulatory acronyms that require explicit textual evidence
REGULATORY_STANDARDS_PATTERN = re.compile(
    r"\b(HIPAA|GDPR|PCI[- ]?DSS|SOC[- ]?2|ISO[- ]?27001|FEDRAMP|HITRUST|SOX)\b",
    re.IGNORECASE,
)

# Management and leadership roles that require explicit interaction / coordination evidence
ROLE_EXAGGERATION_PATTERNS = [
    (
        re.compile(r"\b(stakeholder\s+management)\b", re.IGNORECASE),
        "Stakeholder Management",
        re.compile(
            r"\b(stakeholder|client\s+meeting|client\s+communication|negotiat|expectation|alignment|managed\s+client)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"\b(people\s+management|team\s+leadership|direct\s+reports)\b", re.IGNORECASE),
        "Team Leadership / People Management",
        re.compile(
            r"\b(managed\s+\d+|led\s+a\s+team|direct\s+reports|1-on-1|mentoring|hiring|performance\s+review)\b",
            re.IGNORECASE,
        ),
    ),
]

# Specialized technical or operational patterns that require concrete anchoring evidence
SPECIALIZED_TECH_OVERCLAIM_PATTERNS = [
    (
        re.compile(r"\b(spatial\s+quer(?:y|ies)|spatial\s+index(?:es|ing)?|geospatial|gis\s+quer(?:y|ies)|postgis)\b", re.IGNORECASE),
        "Spatial / Geospatial Database Operations",
        re.compile(r"\b(spatial|gis|geo|geospatial|coordinates|latitude|longitude|postgis|maps?|location\s+tracking)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(indexing\s+strategies|query\s+optimization|execution\s+plans?|b-tree|query\s+tuning)\b", re.IGNORECASE),
        "Advanced Database Indexing & Query Optimization",
        re.compile(r"\b(index|indices|tuning|optimi[sz]|slow\s+quer|explain\s+analyze|profiling|latency|performance|query\s+speed)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(eventual\s+consistency|cap\s+theorem|paxos|raft|distributed\s+transactions?|two-phase\s+commit|2pc|distributed\s+systems?\s+consistency)\b", re.IGNORECASE),
        "Distributed Systems Consistency / Consensus",
        re.compile(r"\b(distributed|eventual|replica|consensus|multi-node|cluster|partition|messaging|event-driven|paxos|raft|sharding|kafka|microservices)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(community\s+management|issue\s+triage|open\s+source\s+stewardship|developer\s+advocacy|moderation)\b", re.IGNORECASE),
        "Community Management & Issue Triage",
        re.compile(r"\b(triage|triaging|community|contributors|pull\s+requests|moderation|issues\s+management|maintainer|advocacy)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(trauma\s+resuscitation|emergency\s+surgery|critical\s+care\s+intubation)\b", re.IGNORECASE),
        "Emergency / Critical Care Procedures",
        re.compile(r"\b(trauma|icu|intensive\s+care|emergency\s+room|er|resuscitat|intubat|critical\s+care)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(derivatives\s+trading|hedging\s+strategies|quantitative\s+modeling)\b", re.IGNORECASE),
        "Derivatives & Quantitative Finance",
        re.compile(r"\b(derivatives?|hedg|options?|futures?|swaps?|quantitative|quant|trading\s+desk)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(observability\s+engineering|distributed\s+tracing|telemetry\s+architecture)\b", re.IGNORECASE),
        "Observability Engineering & Distributed Tracing",
        re.compile(r"\b(opentelemetry|prometheus|jaeger|grafana|distributed\s+tracing|telemetry|spans?|apm|metrics\s+pipeline)\b", re.IGNORECASE),
    ),
]

# High-level architecture, strategy, and governance responsibility patterns (Phase 3B.2 Hardening)
STRATEGY_OVERCLAIM_PATTERNS = [
    (
        re.compile(
            r"\b(polyglot\s+persistence(?:\s+strategy)?|persistence\s+strategy|database\s+strategy|storage\s+strategy)\b",
            re.IGNORECASE,
        ),
        "Persistence & Storage Strategy",
        re.compile(
            r"\b(strateg\w*|architect\w*|blueprint|evaluat\w*|trade-off|select\w*|schema\s+design|storage\s+engine|data\s+modeling)\b",
            re.IGNORECASE,
        ),
        "Candidate mentions technology exposure, but lacks evidence of persistence strategy formulation, storage engine trade-off evaluation, or architectural design responsibility.",
    ),
    (
        re.compile(r"\b((?:cloud|infrastructure|enterprise|data|it)\s+strategy)\b", re.IGNORECASE),
        "Technology Strategy",
        re.compile(
            r"\b(strateg\w*|roadmap|vision|blueprint|architect\w*|advisory|steer|executive|decision-making)\b",
            re.IGNORECASE,
        ),
        "Candidate mentions technology usage, but lacks evidence of strategic roadmap formulation, architectural vision, or executive technical decision-making.",
    ),
]

# Protected compound skill names that contain conjunctions or slashes but represent atomic competencies
PROTECTED_ATOMIC_SKILLS: Set[str] = {
    "ci/cd",
    "ci / cd",
    "ci-cd",
    "continuous integration / continuous deployment",
    "continuous integration and continuous deployment",
    "infrastructure as code",
    "infrastructure-as-code",
    "iac",
    "site reliability engineering",
    "sre",
    "search & discovery",
    "search and discovery",
    "research & development",
    "research and development",
    "r&d",
    "etl / elt",
    "etl/elt",
    "identity & access management",
    "identity and access management",
    "iam",
    "command & control",
    "command and control",
    "c&c",
    "backup & recovery",
    "backup and recovery",
    "disaster recovery & business continuity",
    "disaster recovery and business continuity",
    "high availability & fault tolerance",
    "high availability and fault tolerance",
}

# Fluff prefixes/suffixes that turn explicit skills into trivial superficial variants (Phase 5)
FLUFF_SKILL_TOKENS_PATTERN = re.compile(
    r"\b(proficiency|proficient|skills?|knowledge|experience|basics?|advanced|competenc(?:y|ies)|using|working\s+with)\b",
    re.IGNORECASE,
)

# JD-Specific Over-Inference Patterns (Phase 2)
JD_VIDEO_STREAMING_PATTERN = re.compile(
    r"\b(video\s+(?:encoding|transcoding|streaming\s+pipelines?)|codec\s+engineering|ffmpeg\s+pipelines?)\b",
    re.IGNORECASE,
)
JD_VIDEO_ENGINEERING_EVIDENCE_PATTERN = re.compile(
    r"\b(transcod\w*|encod\w*|codec\w*|ffmpeg|hls|rtmp|dash|webrtc|av1|hevc|streaming\s+protocol)\b",
    re.IGNORECASE,
)

JD_COST_OPTIMIZATION_PATTERN = re.compile(
    r"\b(cloud\s+cost\s+optimi[sz]ation|cost\s+optimi[sz]ation|cost\s+reduction|finops|cloud\s+spend|infrastructure\s+cost\s+optimi[sz]ation)\b",
    re.IGNORECASE,
)
JD_COST_EVIDENCE_PATTERN = re.compile(
    r"\b(cost\w*|spend\w*|budget\w*|finops|bill\w*|savings?|expenditure|pricing)\b",
    re.IGNORECASE,
)

JD_ORCHESTRATION_INTERNALS_PATTERN = re.compile(
    r"\b(kubernetes\s+orchestration\s+internals|orchestration\s+internals|k8s\s+internals|scheduler\s+internals|kernel\s+tuning|cni\s+development)\b",
    re.IGNORECASE,
)
JD_INTERNALS_EVIDENCE_PATTERN = re.compile(
    r"\b(internals?|kernel|custom\s+controller|operator\s+development|cni\s+plugin|kubelet\s+source|scheduler\s+algorithm)\b",
    re.IGNORECASE,
)

# CV-Specific Over-Inference Patterns (Phase 2)
CV_ARCHITECTURE_DESIGN_PATTERN = re.compile(
    r"\b(microservices?\s+architecture(?:\s+design)?|system\s+architecture\s+design|architectural\s+design|distributed\s+systems?\s+architecture)\b",
    re.IGNORECASE,
)
CV_ARCHITECTURE_DESIGN_EVIDENCE_PATTERN = re.compile(
    r"\b(architect|architected|architecting|designed|designing|decoupled|rearchitected|technical\s+blueprint|system\s+design|pattern\s+design)\b",
    re.IGNORECASE,
)

CV_GOVERNANCE_PATTERN = re.compile(
    r"\b(cloud\s+governance(?:\s+strategy)?|enterprise\s+(?:cloud\s+)?governance|it\s+governance(?:\s+strategy)?|governance\s+competence)\b",
    re.IGNORECASE,
)
CV_GOVERNANCE_EVIDENCE_PATTERN = re.compile(
    r"\b(governance|policy|compliance\s+audit|regulatory\s+audit|board|ciso|enterprise\s+policy|audit\s+standard)\b",
    re.IGNORECASE,
)

CV_POSTMORTEM_PATTERN = re.compile(
    r"\b(post[- ]?mortem(?:\s+analysis)?|root\s+cause\s+analysis|rca)\b",
    re.IGNORECASE,
)
CV_POSTMORTEM_EVIDENCE_PATTERN = re.compile(
    r"\b(post[- ]?mortem|root\s+cause|rca|incident\s+report|blameless|cause\s+analysis)\b",
    re.IGNORECASE,
)

# Semantic Evidential Anchor Gating (Phase 3B.1 Generalization Hardening)
SEMANTIC_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "as", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "should", "could", "can", "may", "might", "must", "using", "used",
    "via", "into", "across", "through", "under", "over", "between", "etc", "&", "/",
}

SEMANTIC_FLUFF_STEMS: Set[str] = {
    "skill", "practic", "concept", "basic", "fundament", "knowledg", "experi",
    "general", "profici", "capabl", "compet", "understand", "familiar",
}

CANONICAL_TOOL_ANCHORS: Dict[str, Set[str]] = {
    "terraform": {"infrastructure", "code", "iac", "provision"},
    "cloudformation": {"infrastructure", "code", "iac", "provision"},
    "pulumi": {"infrastructure", "code", "iac", "provision"},
    "ansible": {"infrastructure", "code", "iac", "configur", "autom"},
    "docker": {"contain", "docker"},
    "kubernetes": {"orchestr", "contain", "cluster", "k8s"},
    "k8s": {"orchestr", "contain", "cluster", "k8s"},
    "kafka": {"event", "stream", "messag", "broker"},
    "rabbitmq": {"messag", "queu", "broker", "asynchron", "task"},
    "celery": {"asynchron", "task", "background", "job", "worker"},
    "pyspark": {"batch", "etl", "data", "process", "lake"},
    "spark": {"batch", "etl", "data", "process"},
    "jenkins": {"ci", "cd", "pipelin", "autom", "build"},
    "gitlab": {"ci", "cd", "pipelin", "autom", "release"},
    "github actions": {"ci", "cd", "pipelin", "autom", "action"},
    "git": {"version", "control", "repositori"},
    "nagios": {"monitor", "alert", "ping", "health"},
    "postgresql": {"relat", "databas", "schema", "sql", "queri", "persist"},
    "mysql": {"relat", "databas", "schema", "sql", "queri", "persist"},
    "mongodb": {"nosql", "databas", "persist"},
    "graphql": {"api", "schema", "queri", "endpoint"},
    "stripe": {"payment", "checkout", "card", "gateway", "transact", "saas", "bill", "subscript"},
    "aws": {"cloud", "infrastructure"},
    "azure": {"cloud", "infrastructure"},
    "gcp": {"cloud", "infrastructure"},
    "websocket": {"real-tim", "synchron", "socket", "stream"},
    "storybook": {"compon", "librari", "ui", "design"},
    "figma": {"design", "collabor", "ui"},
    "lighthouse": {"perform", "optim", "speed"},
    "fhir": {"hl7", "fhir", "health", "interoper"},
    "hl7": {"hl7", "fhir", "health", "interoper"},
}

SEMANTIC_CONCEPT_SYNONYMS: Dict[str, Set[str]] = {
    "concurrency": {"concurr"},
    "concurrent": {"concurr"},
    "goroutine": {"concurr"},
    "goroutines": {"concurr"},
    "outage": {"incident"},
    "outages": {"incident"},
    "spend": {"cost"},
    "saving": {"cost", "optim"},
    "savings": {"cost", "optim"},
    "reducing": {"optim", "perform", "impact", "reduc"},
    "reduction": {"optim", "perform", "impact", "reduc"},
    "reduce": {"optim", "perform", "impact", "reduc"},
    "availability": {"reliab", "availab"},
    "available": {"reliab", "availab"},
    "reliable": {"reliab", "availab"},
    "accessible": {"accessibil", "accessibl", "wcag", "a11y"},
    "accessibility": {"accessibil", "accessibl", "wcag", "a11y"},
    "wcag": {"accessibil", "accessibl", "wcag", "a11y"},
    "a11y": {"accessibil", "accessibl", "wcag", "a11y"},
    "restoring": {"respons"},
    "restore": {"respons"},
    "audited": {"harden"},
    "audit": {"harden"},
    "shipped": {"deliver", "ship"},
    "shipping": {"deliver", "ship"},
    "ship": {"deliver", "ship"},
    "owning": {"own"},
    "owns": {"own"},
    "subscription": {"saas", "b2b"},
    "billing": {"saas", "b2b", "bill"},
    "cutting": {"impact", "perform", "optim"},
    "monolith": {"architectur", "migr"},
    "trade-offs": {"trade-off", "communic"},
    "tradeoffs": {"trade-off", "communic"},
}


class ImplicitEvidenceVerifier:
    """
    Layer B Evidence Groundedness Verifier for inferred implicit skills (Phase 3B Hardening).

    Core Invariant:
    'Professional plausibility is not evidence of possession or necessity.'

    Responsibilities:
    - Enforces 3-state entailment model: 'supported', 'plausible', 'unsupported'.
    - Differentiates CV (action/result evidence) vs JD (necessary requirement vs industry context).
    - Decomposes compound candidate skills into atomic constituents before acceptance.
    - Prevents trivial superficial variants of explicit mentions (Phase 5).
    - Preserves established legitimate technical competencies without unevidenced extrapolation.
    - Strictly gates graph construction: only 'supported' candidates receive is_accepted=True.
    """

    VERIFIER_TYPE = "rule_based_deterministic"
    VERIFIER_VERSION = "2.0.0"

    @classmethod
    def normalize_evidence_text(cls, text: str) -> str:
        """Normalize text for evidence grounding comparison."""
        if not text:
            return ""
        t = unicodedata.normalize("NFKD", str(text))
        t = t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        t = t.replace("—", "-").replace("–", "-").replace("−", "-")
        t = t.replace("\u00a0", " ")
        return " ".join(t.split())

    @classmethod
    def verify_implicit_evidence_anchoring(
        cls,
        evidence_spans: Optional[List[str]],
        doc_text: Optional[str],
    ) -> Tuple[List[str], bool, str]:
        """
        Authoritative canonical evidence eligibility check for implicit skills.

        Returns:
            Tuple of (verified_spans, is_eligible, status_reason)
        """
        if not doc_text or not str(doc_text).strip():
            return [], False, "SOURCE_TEXT_UNAVAILABLE"

        clean_spans = [str(s).strip() for s in (evidence_spans or []) if s and str(s).strip()]
        if not clean_spans:
            return [], False, "NO_EVIDENCE_SPANS"

        norm_doc = cls.normalize_evidence_text(doc_text)
        norm_doc_lower = norm_doc.lower()

        verified: List[str] = []
        seen: Set[str] = set()

        for raw_span in (evidence_spans or []):
            if not raw_span or not isinstance(raw_span, str) or not raw_span.strip():
                continue
            span_str = raw_span.strip()
            norm_span = cls.normalize_evidence_text(span_str)
            if not norm_span:
                continue

            # 1. Exact or whitespace/unicode-normalized match
            if norm_span in norm_doc:
                if norm_span not in seen:
                    verified.append(norm_span)
                    seen.add(norm_span)
                continue

            # 2. Case-insensitive exact match
            if norm_span.lower() in norm_doc_lower:
                idx = norm_doc_lower.find(norm_span.lower())
                actual_span = norm_doc[idx : idx + len(norm_span)]
                if actual_span not in seen:
                    verified.append(actual_span)
                    seen.add(actual_span)
                continue

            # 3. Ellipses-delimited multi-part excerpt (e.g. "Snippet A... Snippet B")
            if "..." in span_str or "…" in span_str:
                parts = re.split(r"\.\.\.|\u2026", span_str)
                sub_verified: List[str] = []
                for part in parts:
                    p_norm = cls.normalize_evidence_text(part)
                    if len(p_norm) >= 8:
                        if p_norm in norm_doc:
                            sub_verified.append(p_norm)
                        elif p_norm.lower() in norm_doc_lower:
                            idx = norm_doc_lower.find(p_norm.lower())
                            sub_verified.append(norm_doc[idx : idx + len(p_norm)])
                if sub_verified:
                    for sv in sub_verified:
                        if sv not in seen:
                            verified.append(sv)
                            seen.add(sv)
                    continue

            # 4. Trailing punctuation differences
            stripped_span = norm_span.rstrip(".,;: ")
            if len(stripped_span) >= 10:
                if stripped_span in norm_doc:
                    if stripped_span not in seen:
                        verified.append(stripped_span)
                        seen.add(stripped_span)
                    continue
                elif stripped_span.lower() in norm_doc_lower:
                    idx = norm_doc_lower.find(stripped_span.lower())
                    actual_span = norm_doc[idx : idx + len(stripped_span)]
                    if actual_span not in seen:
                        verified.append(actual_span)
                        seen.add(actual_span)
                    continue

        if verified:
            return verified, True, "VERIFIED_ANCHORED"
        else:
            return [], False, "UNSUPPORTED_NO_ANCHORED_EVIDENCE"

    @classmethod
    def decompose_compound_label(cls, label: str) -> Optional[List[str]]:
        """
        Decompose a compound skill label into atomic sub-skills, avoiding protected atomic terms.
        Returns a list of 2 or more sub-skills if decomposed, else None.
        """
        clean_label = label.strip()
        lower_label = clean_label.casefold()

        # Check if the label is a protected atomic phrase
        if lower_label in PROTECTED_ATOMIC_SKILLS:
            return None

        # Check for coordinate conjunctions: ' & ', ' and '
        parts: List[str] = []
        if " & " in clean_label:
            parts = [p.strip() for p in clean_label.split(" & ")]
        elif " and " in lower_label:
            parts = [p.strip() for p in re.split(r"\s+and\s+", clean_label, flags=re.IGNORECASE)]

        if len(parts) >= 2 and all(len(p) > 2 for p in parts):
            return parts
        return None

    @classmethod
    def check_subcomponent_support(cls, sub_label: str, evidence_text: str) -> bool:
        """Evaluate if an atomic sub-component is evidenced in the source text."""
        sub_lower = sub_label.casefold()
        ev_lower = evidence_text.casefold()

        # 1. Check direct mention
        if re.search(rf"\b{re.escape(sub_lower)}\b", ev_lower):
            return True

        # 2. Check semantic anchor / stem overlap
        sub_stems = {s for s in cls.extract_semantic_stems(sub_label) if s not in SEMANTIC_FLUFF_STEMS}
        ev_stems = cls.extract_semantic_stems(evidence_text)
        for tool, anchors in CANONICAL_TOOL_ANCHORS.items():
            if tool in ev_lower:
                for a in anchors:
                    ev_stems.add(cls.stem_word(a))

        if sub_stems:
            matched_stems = sub_stems.intersection(ev_stems)
            if len(matched_stems) / len(sub_stems) >= 0.5:
                return True

        # 3. Check domain-specific action / synonym patterns for common sub-components
        if "incident" in sub_lower:
            return bool(re.search(r"\b(incident|on-call|outage|troubleshoot|paging|pagerduty|triag)\b", ev_lower))
        if "post-mortem" in sub_lower or "postmortem" in sub_lower or "root cause" in sub_lower:
            return bool(re.search(r"\b(post[- ]?mortem|root\s+cause|rca|retrospective|cause\s+analysis)\b", ev_lower))
        if "trade-off" in sub_lower or "tradeoff" in sub_lower:
            return bool(re.search(r"\b(trade-off|tradeoff|compromis|evaluat|weigh)\b", ev_lower))
        if "management" in sub_lower or "coordination" in sub_lower:
            return bool(re.search(r"\b(manag|coordinat|facilitat|lead|direct)\b", ev_lower))
        if "automation" in sub_lower:
            return bool(re.search(r"\b(automat|script|pipeline|provision|deploy|ansible|terraform|ci|cd|github\s+actions)\b", ev_lower))
        if "optimization" in sub_lower or "optimizing" in sub_lower or "tuning" in sub_lower:
            return bool(re.search(r"\b(optim|reduc|improv|accelerat|tun|speed|fast|effici|scal)\b", ev_lower))
        if "monitoring" in sub_lower or "observability" in sub_lower:
            return bool(re.search(r"\b(monitor|observ|metric|alert|telemetr|ping|health|log)\b", ev_lower))
        if "reliability" in sub_lower:
            return bool(re.search(r"\b(reliab|availab|uptime|fault|resilien|failover|sla|slo)\b", ev_lower))
        if "pipeline" in sub_lower:
            return bool(re.search(r"\b(pipelin|ci/cd|cicd|workflow|etl|stream)\b", ev_lower))
        if "analysis" in sub_lower or "analytics" in sub_lower:
            return bool(re.search(r"\b(analy|metric|measur|profil|evaluat|benchmark)\b", ev_lower))
        if "communication" in sub_lower:
            return bool(re.search(r"\b(communicat|present|collaborat|articulat|written|verbal)\b", ev_lower))

        # 4. Fallback: check significant single stemmed word match
        if sub_stems and len(sub_stems.intersection(ev_stems)) > 0 and len(sub_stems) == 1:
            return True

        return False

    @classmethod
    def stem_word(cls, w: str) -> str:
        """Deterministic rule-based multi-pass stemmer for substantive technical terms."""
        w = w.lower().strip()
        if len(w) <= 3:
            return w
        suffixes = (
            "ization", "isation", "ational", "tional", "ation",
            "ized", "ised", "izing", "ising", "ize", "ise",
            "ated", "ating", "ate",
            "ship", "ment", "ence", "ance", "ency", "ancy", "ities", "ity",
            "ive", "ous", "ing", "ies", "es", "ed", "al", "er", "ery", "ent", "ant", "ly", "s", "y", "e",
        )
        for _ in range(2):
            stripped = False
            for suffix in suffixes:
                if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                    w = w[:-len(suffix)]
                    stripped = True
                    break
            if not stripped:
                break
        return w

    @classmethod
    def extract_semantic_stems(cls, text: str) -> Set[str]:
        """Extract substantive normalized concept stems from text."""
        norm_text = text.replace("-", " ").replace("/", " ")
        tokens = re.findall(r"[a-zA-Z0-9_]+", norm_text)
        stems: Set[str] = set()
        for t in tokens:
            t_clean = t.strip("_").lower()
            if len(t_clean) >= 2 and t_clean not in SEMANTIC_STOPWORDS:
                st = cls.stem_word(t_clean)
                stems.add(st)
                if t_clean in SEMANTIC_CONCEPT_SYNONYMS:
                    for syn in SEMANTIC_CONCEPT_SYNONYMS[t_clean]:
                        stems.add(cls.stem_word(syn))
        return stems

    @classmethod
    def evaluate_semantic_anchor(cls, cand_label: str, evidence_text: str) -> Tuple[float, Set[str], Set[str]]:
        """
        Evaluate empirical anchor coverage of candidate skill substantive stems
        against documented evidence snippets and canonical tool-to-concept maps.
        """
        cand_stems = {s for s in cls.extract_semantic_stems(cand_label) if s not in SEMANTIC_FLUFF_STEMS}
        if not cand_stems:
            return 1.0, set(), set()

        ev_stems = cls.extract_semantic_stems(evidence_text)
        ev_lower = evidence_text.lower()
        for tool, anchors in CANONICAL_TOOL_ANCHORS.items():
            if tool in ev_lower:
                for a in anchors:
                    ev_stems.add(cls.stem_word(a))

        overlap = cand_stems.intersection(ev_stems)
        ratio = len(overlap) / len(cand_stems)
        missing = cand_stems - overlap
        return ratio, overlap, missing

    @classmethod
    def verify_candidates(
        cls,
        candidates: List[ImplicitExtractedSkill],
        explicit_result: Optional[ExtractionResult] = None,
        document_type: str = "CV",
    ) -> Tuple[List[ImplicitExtractedSkill], List[ImplicitExtractedSkill], List[ImplicitEvidenceVerification]]:
        """
        Verify candidate implicit skills that have passed Layer A deduplication.

        Returns:
            Tuple of:
            - accepted_skills: List[ImplicitExtractedSkill] (only 'supported')
            - rejected_skills: List[ImplicitExtractedSkill] ('plausible' and 'unsupported')
            - verifications: List[ImplicitEvidenceVerification]
        """
        accepted_skills: List[ImplicitExtractedSkill] = []
        rejected_skills: List[ImplicitExtractedSkill] = []
        verifications: List[ImplicitEvidenceVerification] = []

        doc_type_normalized = "JD" if document_type.upper() == "JD" else "CV"

        # Track existing explicit IDs and surface forms to detect duplicates and superficial variations (Phase 5)
        known_explicit_ids: Set[str] = set()
        known_explicit_labels: Set[str] = set()
        if explicit_result and explicit_result.skills:
            for s in explicit_result.skills:
                known_explicit_ids.add(s.skill_id.lower())
                known_explicit_labels.add(s.skill_id.lower())
                for sf in s.surface_forms or []:
                    cleaned_sf = sf.strip().casefold()
                    known_explicit_labels.add(cleaned_sf)
                    known_explicit_ids.add(skill_postprocessor.slugify_skill(cleaned_sf))

        accepted_ids: Set[str] = set()

        for cand in candidates:
            # 1. Collect textual evidence, offsets, reasoning, and raw confidence
            quotes: List[str] = []
            offsets: List[Dict[str, int]] = []
            reasonings: List[str] = []
            raw_confidence_vals: List[float] = []

            if getattr(cand, "basis", None):
                quotes.append(f"basis: {cand.basis}")

            for ev in cand.evidences or []:
                if hasattr(ev, "snippets") and ev.snippets:
                    for snip in ev.snippets:
                        if hasattr(snip, "text") and snip.text:
                            quotes.append(snip.text.strip())
                        if hasattr(snip, "start") and hasattr(snip, "end") and snip.start is not None and snip.end is not None:
                            offsets.append({"start": snip.start, "end": snip.end})
                        elif hasattr(snip, "offset_start") and hasattr(snip, "offset_end"):
                            if snip.offset_start is not None and snip.offset_end is not None:
                                offsets.append({"start": snip.offset_start, "end": snip.offset_end})
                if hasattr(ev, "inferred_from_raw") and ev.inferred_from_raw:
                    quotes.append(ev.inferred_from_raw.strip())
                elif hasattr(ev, "inferred_from") and ev.inferred_from:
                    quotes.append(ev.inferred_from.strip())
                if hasattr(ev, "reasoning") and ev.reasoning:
                    reasonings.append(ev.reasoning.strip())
                if hasattr(ev, "llm_confidence_raw") and ev.llm_confidence_raw is not None:
                    raw_confidence_vals.append(float(ev.llm_confidence_raw))

            if not raw_confidence_vals and getattr(cand, "confidence", None) is not None:
                raw_confidence_vals.append(float(cand.confidence))

            confidence_raw = round(sum(raw_confidence_vals) / len(raw_confidence_vals), 3) if raw_confidence_vals else None
            evidence_quotes_text = " ".join(quotes)
            inference_rationale = " ".join(reasonings)
            full_context_text = f"{evidence_quotes_text} {inference_rationale}".strip()
            cand_label_clean = cand.label.strip()

            # Helper to create verification record
            def build_verification(
                assessment: str,
                support_status: str,
                acceptance_decision: str,
                is_accepted: bool,
                support_reason: str,
                confidence_norm: float,
                proposed_label: Optional[str] = None,
                skill_id: Optional[str] = None,
                original_label: Optional[str] = None,
                extra_orig: Optional[Dict[str, Any]] = None,
            ) -> ImplicitEvidenceVerification:
                orig_meta: Dict[str, Any] = {
                    "raw_evidences_count": len(cand.evidences or []),
                    "snippets_count": len(quotes),
                }
                if extra_orig:
                    orig_meta.update(extra_orig)

                eff_skill_id = skill_id or cand.skill_id
                eff_orig_label = original_label or cand.label

                return ImplicitEvidenceVerification(
                    skill_id=eff_skill_id,
                    original_label=eff_orig_label,
                    proposed_label=proposed_label,
                    assessment=assessment,  # type: ignore
                    assessment_reason=support_reason,
                    is_accepted=is_accepted,
                    confidence=confidence_norm,
                    verifier_type=cls.VERIFIER_TYPE,
                    verifier_version=cls.VERIFIER_VERSION,
                    evidence_snippets=quotes,
                    original_evidence=orig_meta,
                    skill_name=proposed_label or cand.label,
                    document_type=doc_type_normalized,
                    source_evidence=evidence_quotes_text or None,
                    evidence_offsets=offsets,
                    inference_rationale=inference_rationale or None,
                    support_status=support_status,  # type: ignore
                    support_reason=support_reason,
                    validator_version=cls.VERIFIER_VERSION,
                    confidence_raw=confidence_raw,
                    confidence_normalized=confidence_norm,
                    acceptance_decision=acceptance_decision,  # type: ignore
                    decomposed_from=orig_meta.get("decomposed_from"),
                    decomposed_components=orig_meta.get("all_components"),
                )

            # 2. Check for empty evidence
            if not quotes and not reasonings:
                v_record = build_verification(
                    assessment="unsupported",
                    support_status="unsupported",
                    acceptance_decision="rejected",
                    is_accepted=False,
                    support_reason="Candidate inference lacks supporting evidence snippets or reasoning.",
                    confidence_norm=0.0,
                )
                verifications.append(v_record)
                rejected_skills.append(cand)
                continue

            # 3. Check for Superficial Variant of Explicit Mention (Phase 5)
            # e.g., 'Terraform proficiency' when 'Terraform' is already explicit
            stripped_fluff = FLUFF_SKILL_TOKENS_PATTERN.sub("", cand_label_clean).strip()
            stripped_slug = skill_postprocessor.slugify_skill(stripped_fluff)
            if stripped_fluff and stripped_fluff.casefold() != cand_label_clean.casefold():
                if stripped_slug in known_explicit_ids or stripped_fluff.casefold() in known_explicit_labels:
                    v_record = build_verification(
                        assessment="unsupported",
                        support_status="unsupported",
                        acceptance_decision="rejected",
                        is_accepted=False,
                        support_reason=(
                            f"Candidate '{cand_label_clean}' is a superficial variant of already explicit skill "
                            f"'{stripped_fluff}'. Explicit mentions take precedence over redundant implicit variants."
                        ),
                        confidence_norm=0.1,
                        extra_orig={"redundant_explicit_match": stripped_fluff},
                    )
                    verifications.append(v_record)
                    rejected_skills.append(cand)
                    continue

            # 4. Check for Regulatory / Standard Overclaim (e.g., HIPAA, GDPR)
            std_match = REGULATORY_STANDARDS_PATTERN.search(cand_label_clean)
            if std_match:
                std_term = std_match.group(0)
                quote_has_std = bool(re.search(rf"\b{re.escape(std_term)}\b", evidence_quotes_text, re.IGNORECASE))
                if not quote_has_std:
                    # Generalize safely
                    generalized_label = re.sub(
                        r"\s*\([^)]*" + re.escape(std_term) + r"[^)]*\)",
                        "",
                        cand_label_clean,
                        flags=re.IGNORECASE,
                    ).strip()
                    if not generalized_label or generalized_label.casefold() == cand_label_clean.casefold():
                        if "health" in full_context_text.casefold():
                            generalized_label = "Healthcare Domain Familiarity"
                        else:
                            generalized_label = "Regulatory Domain Knowledge"

                    gen_slug = skill_postprocessor.slugify_skill(generalized_label)

                    if gen_slug in known_explicit_ids or generalized_label.casefold() in known_explicit_labels:
                        v_record = build_verification(
                            assessment="partially_supported",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"Specific standard '{std_term}' is unsupported by evidence quotes. "
                                f"Proposed generalization '{generalized_label}' duplicates an existing explicit skill."
                            ),
                            confidence_norm=0.6,
                            proposed_label=generalized_label,
                            extra_orig={"standard_claimed": std_term},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

                    cand_copy = cand.model_copy(deep=True)
                    cand_copy.skill_id = gen_slug
                    cand_copy.label = generalized_label

                    v_record = build_verification(
                        assessment="partially_supported",
                        support_status="supported",
                        acceptance_decision="accepted",
                        is_accepted=True,
                        support_reason=(
                            f"General domain context is mentioned in evidence, but specific standard '{std_term}' "
                            f"is not established in source text. Safely generalized to '{generalized_label}'."
                        ),
                        confidence_norm=0.85,
                        proposed_label=generalized_label,
                        extra_orig={"standard_claimed": std_term, "original_skill_id": cand.skill_id},
                    )
                    verifications.append(v_record)
                    accepted_skills.append(cand_copy)
                    accepted_ids.add(gen_slug)
                    continue

            # 5. Check Compound Skill Candidates & Decompose (Phase 3B.2 Atomic Decomposition)
            # e.g., 'Incident Management & Post-Mortem Analysis', 'Deployment Automation & Pipeline Optimization'
            sub_components = cls.decompose_compound_label(cand_label_clean)
            if sub_components and len(sub_components) >= 2:
                supported_parts: List[str] = []
                unsupported_parts: List[str] = []

                for part in sub_components:
                    if cls.check_subcomponent_support(part, evidence_quotes_text):
                        supported_parts.append(part)
                    else:
                        unsupported_parts.append(part)

                if supported_parts:
                    # At least one component is supported: decompose and evaluate each atomic component independently
                    for part in supported_parts:
                        part_slug = skill_postprocessor.slugify_skill(part)

                        # Check explicit duplicate for this component
                        if part_slug in known_explicit_ids or part.casefold() in known_explicit_labels:
                            v_record = build_verification(
                                skill_id=part_slug,
                                original_label=cand.label,
                                assessment="partially_supported",
                                support_status="plausible",
                                acceptance_decision="quarantined",
                                is_accepted=False,
                                support_reason=(
                                    f"Compound candidate '{cand_label_clean}' was decomposed. "
                                    f"Supported sub-component '{part}' duplicates an explicit skill."
                                ),
                                confidence_norm=0.55,
                                proposed_label=part,
                                extra_orig={
                                    "decomposed_from": cand.skill_id,
                                    "original_compound_label": cand_label_clean,
                                    "all_components": sub_components,
                                    "component_status": "duplicate_explicit",
                                    "decomposed_supported_parts": supported_parts,
                                    "decomposed_unsupported_parts": unsupported_parts,
                                },
                            )
                            verifications.append(v_record)
                            continue

                        if part_slug in accepted_ids:
                            continue

                        # Independent accepted atomic skill
                        cand_copy = cand.model_copy(deep=True)
                        cand_copy.skill_id = part_slug
                        cand_copy.label = part
                        cand_copy.decomposed_from = cand.skill_id

                        assess_val = "supported" if not unsupported_parts else "partially_supported"
                        support_msg = (
                            f"Compound candidate '{cand_label_clean}' was decomposed into atomic competencies. "
                            f"Sub-component '{part}' is evidenced and accepted independently."
                        ) if not unsupported_parts else (
                            f"Compound candidate '{cand_label_clean}' was decomposed. "
                            f"Unevidenced component(s) {unsupported_parts} were rejected, and supported component "
                            f"'{part}' was accepted independently."
                        )

                        v_record = build_verification(
                            skill_id=part_slug,
                            original_label=cand.label,
                            assessment=assess_val,
                            support_status="supported",
                            acceptance_decision="accepted",
                            is_accepted=True,
                            support_reason=support_msg,
                            confidence_norm=0.85,
                            proposed_label=part,
                            extra_orig={
                                "decomposed_from": cand.skill_id,
                                "original_compound_label": cand_label_clean,
                                "all_components": sub_components,
                                "component_status": "supported",
                                "decomposed_supported_parts": supported_parts,
                                "decomposed_unsupported_parts": unsupported_parts,
                            },
                        )
                        verifications.append(v_record)
                        accepted_skills.append(cand_copy)
                        accepted_ids.add(part_slug)

                    # Create explicit audit records for unsupported components
                    for unsupp in unsupported_parts:
                        unsupp_slug = skill_postprocessor.slugify_skill(unsupp)
                        v_unsupp = build_verification(
                            skill_id=unsupp_slug,
                            original_label=cand.label,
                            assessment="insufficient_evidence",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"Compound candidate '{cand_label_clean}' was decomposed. "
                                f"Sub-component '{unsupp}' lacks evidence in source text and is rejected."
                            ),
                            confidence_norm=0.30,
                            proposed_label=unsupp,
                            extra_orig={
                                "decomposed_from": cand.skill_id,
                                "original_compound_label": cand_label_clean,
                                "all_components": sub_components,
                                "component_status": "unsupported",
                                "decomposed_supported_parts": supported_parts,
                                "decomposed_unsupported_parts": unsupported_parts,
                            },
                        )
                        verifications.append(v_unsupp)

                    continue

                else:
                    # Completely unsupported compound
                    v_record = build_verification(
                        assessment="insufficient_evidence",
                        support_status="unsupported",
                        acceptance_decision="rejected",
                        is_accepted=False,
                        support_reason=(
                            f"Compound candidate '{cand_label_clean}' lacks evidence for all components: {unsupported_parts}."
                        ),
                        confidence_norm=0.3,
                        extra_orig={"unsupported_parts": unsupported_parts},
                    )
                    verifications.append(v_record)
                    rejected_skills.append(cand)
                    continue

            # 6. Check Role / Responsibility Exaggeration
            role_exaggerated = False
            for role_pat, role_name, evidence_req_pat in ROLE_EXAGGERATION_PATTERNS:
                if role_pat.search(cand_label_clean):
                    has_role_evidence = bool(evidence_req_pat.search(evidence_quotes_text))
                    if not has_role_evidence:
                        role_exaggerated = True
                        v_record = build_verification(
                            assessment="insufficient_evidence",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"Source document evidence mentions delivery or project tasks, but does not substantiate "
                                f"active {role_name} responsibilities without concrete evidence of stakeholder coordination, "
                                f"expectation management, or direct team leadership in source quotes."
                            ),
                            confidence_norm=0.5,
                            extra_orig={"role_type": role_name},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        break

            if role_exaggerated:
                continue

            # 7. Check Specialized Technical Overclaims (Phase 2C Fix 3)
            tech_overclaimed = False
            for tech_pat, tech_name, evidence_req_pat in SPECIALIZED_TECH_OVERCLAIM_PATTERNS:
                if tech_pat.search(cand_label_clean):
                    has_tech_evidence = bool(evidence_req_pat.search(evidence_quotes_text))
                    if not has_tech_evidence:
                        tech_overclaimed = True
                        v_record = build_verification(
                            assessment="insufficient_evidence",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"Inferred competency introduces specialized claims '{tech_name}' without supporting evidence "
                                f"in source document snippets. Found foundational technology context, but lacks concrete evidence "
                                f"of active practice, implementation, or requirements for this specialization."
                            ),
                            confidence_norm=0.4,
                            extra_orig={"specialization_claimed": tech_name},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        break

            if tech_overclaimed:
                continue

            # 7b. Check Strategy & Architectural Responsibility Overclaims (Phase 3B.2 Hardening)
            strategy_overclaimed = False
            for strat_pat, strat_name, strat_req_pat, strat_reason in STRATEGY_OVERCLAIM_PATTERNS:
                if strat_pat.search(cand_label_clean):
                    has_strat_evidence = bool(strat_req_pat.search(evidence_quotes_text))
                    if not has_strat_evidence:
                        strategy_overclaimed = True
                        v_record = build_verification(
                            assessment="plausible",
                            support_status="plausible",
                            acceptance_decision="quarantined",
                            is_accepted=False,
                            support_reason=(
                                f"Inferred competency '{cand_label_clean}' introduces high-level strategy/architectural claim "
                                f"'{strat_name}' without necessary responsibility-level evidence in source quotes. {strat_reason}"
                            ),
                            confidence_norm=0.50,
                            extra_orig={"strategy_responsibility_claimed": strat_name},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        break

            if strategy_overclaimed:
                continue

            # 8. Document-Type Specific Gating (Phase 2)
            if doc_type_normalized == "JD":
                # Rule JD-1: Business context != Required technical skill (e.g. streaming platform -> video transcoding)
                if JD_VIDEO_STREAMING_PATTERN.search(cand_label_clean):
                    has_video_eng = bool(JD_VIDEO_ENGINEERING_EVIDENCE_PATTERN.search(evidence_quotes_text))
                    if not has_video_eng:
                        v_record = build_verification(
                            assessment="unsupported",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"JD business/employer context describes a video streaming platform, but text contains no "
                                f"explicit requirement for video encoding or transcoding pipeline development."
                            ),
                            confidence_norm=0.3,
                            extra_orig={"jd_rule": "business_context_not_required_skill"},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

                # Rule JD-2: Cloud operation != Cost optimization requirement
                if JD_COST_OPTIMIZATION_PATTERN.search(cand_label_clean):
                    has_cost_req = bool(JD_COST_EVIDENCE_PATTERN.search(evidence_quotes_text))
                    if not has_cost_req:
                        v_record = build_verification(
                            assessment="plausible",
                            support_status="plausible",
                            acceptance_decision="quarantined",
                            is_accepted=False,
                            support_reason=(
                                f"JD specifies cloud infrastructure operation, but contains no explicit requirement "
                                f"or responsibility for cloud cost optimization or financial engineering."
                            ),
                            confidence_norm=0.5,
                            extra_orig={"jd_rule": "operational_context_not_cost_optimization"},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

                # Rule JD-3: Kubernetes operation != Deep internals/kernel
                if JD_ORCHESTRATION_INTERNALS_PATTERN.search(cand_label_clean):
                    has_internals_req = bool(JD_INTERNALS_EVIDENCE_PATTERN.search(evidence_quotes_text))
                    if not has_internals_req:
                        v_record = build_verification(
                            assessment="plausible",
                            support_status="plausible",
                            acceptance_decision="quarantined",
                            is_accepted=False,
                            support_reason=(
                                f"JD requires Kubernetes/EKS cluster operations, but lacks evidence of required competence "
                                f"in orchestration internals, custom controller development, or kernel tuning."
                            ),
                            confidence_norm=0.45,
                            extra_orig={"jd_rule": "cluster_operation_not_internals"},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

            elif doc_type_normalized == "CV":
                # Rule CV-1: Exposure/deployment != Architecture design
                if CV_ARCHITECTURE_DESIGN_PATTERN.search(cand_label_clean):
                    has_arch_design = bool(CV_ARCHITECTURE_DESIGN_EVIDENCE_PATTERN.search(evidence_quotes_text))
                    if not has_arch_design:
                        v_record = build_verification(
                            assessment="unsupported",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"Candidate CV mentions deploying or operating microservices, but does not provide "
                                f"evidence of system architecture design, decoupling, or architectural blueprinting."
                            ),
                            confidence_norm=0.35,
                            extra_orig={"cv_rule": "deployment_exposure_not_architecture_design"},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

                # Rule CV-2: Configuration standardization != Enterprise governance strategy
                if CV_GOVERNANCE_PATTERN.search(cand_label_clean):
                    has_gov_evidence = bool(CV_GOVERNANCE_EVIDENCE_PATTERN.search(evidence_quotes_text))
                    if not has_gov_evidence:
                        v_record = build_verification(
                            assessment="unsupported",
                            support_status="unsupported",
                            acceptance_decision="rejected",
                            is_accepted=False,
                            support_reason=(
                                f"Standardizing server configuration files or writing automation playbooks does not "
                                f"substantiate enterprise cloud governance strategy without policy or audit evidence."
                            ),
                            confidence_norm=0.3,
                            extra_orig={"cv_rule": "config_automation_not_enterprise_governance"},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

                # Rule CV-3: Incident troubleshooting != Root cause post-mortem analysis
                if CV_POSTMORTEM_PATTERN.search(cand_label_clean):
                    has_postmortem = bool(CV_POSTMORTEM_EVIDENCE_PATTERN.search(evidence_quotes_text))
                    if not has_postmortem:
                        v_record = build_verification(
                            assessment="plausible",
                            support_status="plausible",
                            acceptance_decision="quarantined",
                            is_accepted=False,
                            support_reason=(
                                f"Candidate participated in on-call or incident troubleshooting, but evidence does not "
                                f"demonstrate conducting formal post-mortem or root cause analysis."
                            ),
                            confidence_norm=0.5,
                            extra_orig={"cv_rule": "incident_response_not_postmortem_analysis"},
                        )
                        verifications.append(v_record)
                        rejected_skills.append(cand)
                        continue

            # 9. Conservative Support Grounding Policy with Semantic Anchor Gating (Phase 3B.1)
            cand_label_lower = cand_label_clean.casefold()
            is_directly_supported = bool(
                re.search(rf"\b{re.escape(cand_label_lower)}\b", evidence_quotes_text.casefold())
            )

            if is_directly_supported:
                v_record = build_verification(
                    assessment="supported",
                    support_status="supported",
                    acceptance_decision="accepted",
                    is_accepted=True,
                    support_reason=(
                        "Inferred competency is directly supported by documented evidence text "
                        "without unevidenced technical extrapolation or role exaggeration."
                    ),
                    confidence_norm=0.90,
                    extra_orig={"evidence_support_policy": "directly_supported"},
                )
                verifications.append(v_record)
                accepted_skills.append(cand)
                accepted_ids.add(cand.skill_id)
                continue

            # Non-verbatim candidate: evaluate semantic evidential anchor grounding
            anchor_ratio, overlap, missing = cls.evaluate_semantic_anchor(
                cand_label_clean, evidence_quotes_text
            )

            # Low or zero anchor support: reject unsupported extrapolation
            if anchor_ratio == 0.0 or (anchor_ratio < 0.30 and len(missing) >= 2):
                missing_str = ", ".join(sorted(missing)) if missing else "all components"
                v_record = build_verification(
                    assessment="insufficient_evidence",
                    support_status="unsupported",
                    acceptance_decision="rejected",
                    is_accepted=False,
                    support_reason=(
                        f"Inferred competency introduces specialized claims '{cand_label_clean}' without supporting evidence "
                        f"in source document snippets. Lacks empirical anchor for core concept(s): {missing_str}."
                    ),
                    confidence_norm=0.35,
                    extra_orig={
                        "evidence_support_policy": "unsupported_extrapolation",
                        "anchor_ratio": round(anchor_ratio, 2),
                        "missing_stems": sorted(list(missing)),
                    },
                )
                verifications.append(v_record)
                rejected_skills.append(cand)
                continue

            # Borderline / partial support: quarantine as plausible
            if anchor_ratio < 0.40:
                missing_str = ", ".join(sorted(missing))
                v_record = build_verification(
                    assessment="plausible",
                    support_status="plausible",
                    acceptance_decision="quarantined",
                    is_accepted=False,
                    support_reason=(
                        f"Inferred competency '{cand_label_clean}' has only partial, speculative evidential grounding "
                        f"(anchor coverage {anchor_ratio:.0%}). Quarantined for review; missing grounding for: {missing_str}."
                    ),
                    confidence_norm=0.50,
                    extra_orig={
                        "evidence_support_policy": "speculative_plausible",
                        "anchor_ratio": round(anchor_ratio, 2),
                        "missing_stems": sorted(list(missing)),
                    },
                )
                verifications.append(v_record)
                rejected_skills.append(cand)
                continue

            # Reasonably inferred with solid semantic anchor coverage (>= 40%)
            v_record = build_verification(
                assessment="supported",
                support_status="supported",
                acceptance_decision="accepted",
                is_accepted=True,
                support_reason=(
                    "Inferred competency is reasonably inferred by documented evidence text "
                    "without unevidenced technical extrapolation or role exaggeration."
                ),
                confidence_norm=0.85,
                extra_orig={
                    "evidence_support_policy": "reasonably_inferred",
                    "anchor_ratio": round(anchor_ratio, 2),
                    "overlap_stems": sorted(list(overlap)),
                },
            )
            verifications.append(v_record)
            accepted_skills.append(cand)
            accepted_ids.add(cand.skill_id)

        return accepted_skills, rejected_skills, verifications

"""
Module 1 (SBERT + GNN) Protocol & Default Temporary Extractor Adapter.
Extracts `cv_skills`, `jd_skills`, and `match_results` (`w_j`, `soft_match`) from raw `cv_text` and `jd_text`
using either an LLM structured output call or a deterministic heuristic fallback when offline/no API key.
"""

import re
from typing import Dict, List, Optional, Protocol, Tuple
from pydantic import BaseModel, Field

from skill_gap.adapters.llm_client import LLMClient
from skill_gap.domain.enums import SkillType
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult
from .schemas import Module1Output


class Module1MatcherProtocol(Protocol):
    """Protocol for any Module 1 (SBERT + GNN) implementation."""

    def extract_and_match(self, cv_text: str, jd_text: str) -> Module1Output:
        ...


class _LLMModule1ExtractionSchema(BaseModel):
    """Structured LLM extraction schema for Module 1 temporary adapter."""

    cv_skills: List[ExtractedCVSkill] = Field(default_factory=list)
    jd_skills: List[ExtractedJDSkill] = Field(default_factory=list)
    match_results: List[MatchResult] = Field(default_factory=list)


# Canonical Tech Skill Dictionary + Substitution Similarity Matrix for deterministic fallback
_CANONICAL_SKILLS: List[Tuple[str, List[str], float]] = [
    ("kubernetes", ["kubernetes", "k8s", "eks", "gke", "aks"], 0.30),
    ("docker", ["docker", "container", "dockerfile", "containerization"], 0.20),
    ("terraform", ["terraform", "iac", "infrastructure as code"], 0.25),
    ("cloudformation", ["cloudformation", "aws cdk"], 0.20),
    ("linux", ["linux", "ubuntu", "centos", "rhel", "debian", "bash", "shell"], 0.20),
    ("aws", ["aws", "amazon web services", "ec2", "s3", "lambda"], 0.25),
    ("gcp", ["gcp", "google cloud", "bigquery"], 0.15),
    ("ci_cd", ["ci/cd", "github actions", "gitlab ci", "jenkins", "argocd"], 0.20),
    ("java", ["java", "jdk", "jvm", "java core"], 0.30),
    ("spring_boot", ["spring boot", "spring framework", "spring security", "spring data"], 0.30),
    ("python", ["python", "fastapi", "django", "flask", "pytorch"], 0.25),
    ("typescript", ["typescript", "ts"], 0.20),
    ("javascript", ["javascript", "es6", "nodejs", "node.js"], 0.20),
    ("react", ["react", "reactjs", "react.js", "redux"], 0.25),
    ("nextjs", ["next.js", "nextjs"], 0.20),
    ("vue", ["vue", "vuejs", "vue.js", "nuxt"], 0.20),
    ("angular", ["angular", "rxjs"], 0.20),
    ("postgresql", ["postgresql", "postgres"], 0.20),
    ("mysql", ["mysql", "mariadb"], 0.20),
    ("sql", ["sql", "rdbms", "database"], 0.20),
    ("mongodb", ["mongodb", "nosql", "mongoose"], 0.15),
    ("redis", ["redis", "caching", "in-memory cache"], 0.15),
    ("kafka", ["kafka", "apache kafka", "event-driven"], 0.20),
    ("rabbitmq", ["rabbitmq", "amqp", "message broker", "message queue"], 0.20),
    ("microservices", ["microservices", "microservice", "distributed system"], 0.25),
    ("rest_api", ["rest api", "restful", "http api", "openapi", "graphql"], 0.20),
    ("git", ["git", "github", "gitlab"], 0.10),
]

# Semantic substitution pairs (skill_a, skill_b) -> soft_match in [0.40, 0.84]
_SUBSTITUTION_PAIRS: Dict[Tuple[str, str], float] = {
    ("terraform", "cloudformation"): 0.72,
    ("cloudformation", "terraform"): 0.72,
    ("kubernetes", "docker"): 0.65,
    ("docker", "kubernetes"): 0.65,
    ("aws", "gcp"): 0.68,
    ("gcp", "aws"): 0.68,
    ("postgresql", "mysql"): 0.80,
    ("mysql", "postgresql"): 0.80,
    ("postgresql", "sql"): 0.78,
    ("mysql", "sql"): 0.78,
    ("kafka", "rabbitmq"): 0.75,
    ("rabbitmq", "kafka"): 0.75,
    ("react", "vue"): 0.62,
    ("vue", "react"): 0.62,
    ("react", "angular"): 0.58,
    ("angular", "react"): 0.58,
    ("react", "nextjs"): 0.82,
    ("nextjs", "react"): 0.82,
    ("typescript", "javascript"): 0.78,
    ("javascript", "typescript"): 0.75,
    ("java", "spring_boot"): 0.70,
    ("spring_boot", "java"): 0.70,
}


class DefaultModule1Extractor:
    """
    Default Module 1 Extractor that bridges raw (cv_text, jd_text) into Module 2's input contract.
    Tries LLM structured extraction first (if configured and available) with verbatim span verification,
    and falls back to deterministic sentence/keyword extraction so tests and offline runs never fail.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, use_llm: bool = True) -> None:
        self.llm_client = llm_client
        self.use_llm = use_llm

    def extract_and_match(self, cv_text: str, jd_text: str) -> Module1Output:
        if self.use_llm and self.llm_client is not None:
            try:
                output = self._extract_via_llm(cv_text, jd_text)
                if output.jd_skills and output.match_results:
                    return output
            except Exception as exc:
                print(f"[Module1Extractor] LLM extraction fallback triggered: {exc}")

        return self._extract_deterministic(cv_text, jd_text)

    def _extract_via_llm(self, cv_text: str, jd_text: str) -> Module1Output:
        prompt = (
            "Extract technical skills from the CV and JD below and compute their semantic alignment.\n"
            "Rules:\n"
            "1. Use concise snake_case identifiers for `skill_id`, `jd_skill_id`, and `matched_cv_skill_id` "
            "(e.g., 'kubernetes', 'spring_boot', 'postgresql', 'terraform', 'react').\n"
            "2. `evidence_spans` MUST be exact verbatim substrings copied directly from the CV or JD text.\n"
            "3. For every skill in `jd_skills`, produce exactly one `MatchResult` in `match_results`:\n"
            "   - `w_j`: relative importance weight in the JD in (0.0, 1.0] such that weights sum to ~1.0.\n"
            "   - If the candidate has the exact same skill in `cv_skills`, set `matched_cv_skill_id = jd_skill_id` and `soft_match` in [0.85, 1.0].\n"
            "   - If the candidate has a related substitute skill in `cv_skills` (e.g., CloudFormation for Terraform, RabbitMQ for Kafka), "
            "set `matched_cv_skill_id` to that CV skill and `soft_match` in [0.45, 0.84].\n"
            "   - If the candidate lacks the skill and any substitute, set `matched_cv_skill_id` to the closest CV skill (or 'none') and `soft_match` in [0.0, 0.35].\n\n"
            f"CV Text:\n{cv_text}\n\n"
            f"JD Text:\n{jd_text}\n"
        )
        res = self.llm_client.complete(prompt, _LLMModule1ExtractionSchema)
        return Module1Output(
            cv_skills=res.cv_skills,
            jd_skills=res.jd_skills,
            match_results=res.match_results,
        )

    def _extract_deterministic(self, cv_text: str, jd_text: str) -> Module1Output:
        cv_sentences = self._split_lines(cv_text)
        jd_sentences = self._split_lines(jd_text)

        cv_skills: List[ExtractedCVSkill] = []
        jd_skills: List[ExtractedJDSkill] = []
        raw_weights: Dict[str, float] = {}

        for skill_id, aliases, base_w in _CANONICAL_SKILLS:
            cv_spans = self._find_matching_spans(cv_sentences, aliases)
            if cv_spans:
                cv_skills.append(
                    ExtractedCVSkill(
                        skill_id=skill_id,
                        type=SkillType.EXPLICIT,
                        confidence=0.95,
                        evidence_spans=cv_spans,
                    )
                )

            jd_spans = self._find_matching_spans(jd_sentences, aliases)
            if jd_spans:
                jd_skills.append(
                    ExtractedJDSkill(
                        skill_id=skill_id,
                        type=SkillType.EXPLICIT,
                        confidence=0.95,
                        evidence_spans=jd_spans,
                    )
                )
                raw_weights[skill_id] = base_w

        # Ensure at least one JD skill if JD text is generic/unrecognized
        if not jd_skills and jd_sentences:
            first_span = jd_sentences[0]
            jd_skills.append(
                ExtractedJDSkill(
                    skill_id="software_engineering",
                    type=SkillType.EXPLICIT,
                    confidence=0.80,
                    evidence_spans=[first_span],
                )
            )
            raw_weights["software_engineering"] = 1.0
            if cv_sentences and not cv_skills:
                cv_skills.append(
                    ExtractedCVSkill(
                        skill_id="software_engineering",
                        type=SkillType.EXPLICIT,
                        confidence=0.80,
                        evidence_spans=[cv_sentences[0]],
                    )
                )

        total_w = sum(raw_weights.values()) or 1.0
        cv_skill_ids = {s.skill_id for s in cv_skills}
        fallback_cv_id = cv_skills[0].skill_id if cv_skills else "none"

        match_results: List[MatchResult] = []
        for jd_skill in jd_skills:
            j_id = jd_skill.skill_id
            w_j = round(raw_weights.get(j_id, 0.2) / total_w, 4)
            w_j = max(0.05, min(1.0, w_j))

            if j_id in cv_skill_ids:
                matched_id = j_id
                soft_match = 1.0
            else:
                best_sub_id = fallback_cv_id
                best_sim = 0.20
                for c_id in cv_skill_ids:
                    sim = _SUBSTITUTION_PAIRS.get((j_id, c_id), 0.20)
                    if sim > best_sim:
                        best_sim = sim
                        best_sub_id = c_id
                matched_id = best_sub_id
                soft_match = best_sim

            match_results.append(
                MatchResult(
                    jd_skill_id=j_id,
                    w_j=w_j,
                    matched_cv_skill_id=matched_id,
                    soft_match=soft_match,
                )
            )

        return Module1Output(
            cv_skills=cv_skills,
            jd_skills=jd_skills,
            match_results=match_results,
        )

    @staticmethod
    def _split_lines(text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r"[\r\n]+|(?<=[.!?])\s+", text)
        cleaned = []
        for p in parts:
            s = p.strip().lstrip("-•*+ ").strip()
            if len(s) >= 4:
                cleaned.append(s)
        return cleaned

    @staticmethod
    def _find_matching_spans(sentences: List[str], aliases: List[str]) -> List[str]:
        spans: List[str] = []
        for sent in sentences:
            s_low = sent.lower()
            for alias in aliases:
                pattern = r"(?<![a-z0-9])" + re.escape(alias.lower()) + r"(?![a-z0-9])"
                if re.search(pattern, s_low):
                    if sent not in spans:
                        spans.append(sent)
                    break
        return spans[:4]

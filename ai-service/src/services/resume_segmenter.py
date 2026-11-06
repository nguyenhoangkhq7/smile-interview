import re
from typing import List, Optional, Tuple
from pydantic import BaseModel
from src.domain.models import JobBlock, SpanMapping, SegmenterOutput, ExtractedCVSkill, UNASSIGNED_JOB_ID
from src.adapters.config import AppConfig
from src.adapters.llm_client import LLMClient

PRESENT_TOKENS = {
    "present", "current", "now", "nay", "hien tai", "hiện tại",
    "till date", "to date", "den nay", "đến nay", "null", "none"
}


class JobBlockExtraction(BaseModel):
    job_blocks: List[JobBlock]


class SpanMappingExtraction(BaseModel):
    span_mappings: List[SpanMapping]


class ResumeSegmenter:
    """
    Service responsible for parsing a CV text into distinct JobBlocks and mapping
    extracted evidence spans to their corresponding JobBlocks.
    Uses Lightweight Temporal & Year-Grounding Sanity Checks + Substring Fast-Path Mapping.
    """

    def __init__(self, llm_client: LLMClient, config: Optional[AppConfig] = None):
        self.llm_client = llm_client
        self.config = config or AppConfig()

    @staticmethod
    def _normalize_iso_month(date_val: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """Normalize an LLM-extracted date token into ISO YYYY-MM (or None for ongoing)."""
        if not date_val or not str(date_val).strip():
            return None, None
        s = str(date_val).strip().lower()
        if s in PRESENT_TOKENS:
            return None, None
        # Standard YYYY-MM
        m = re.match(r"^(\d{4})-(0?[1-9]|1[0-2])$", s)
        if m:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}", None
        # Year-only YYYY -> YYYY-01
        m_yr = re.match(r"^(\d{4})$", s)
        if m_yr:
            return f"{int(m_yr.group(1)):04d}-01", None
        return None, f"invalid_iso_date:{date_val}"

    def _validate_temporal_and_year_grounding(
        self,
        jb: JobBlock,
        cv_text: str,
        ref_date_iso: str,
    ) -> List[str]:
        """
        Lightweight Temporal & Year-Grounding Sanity Check (0ms):
        1. Normalizes `start_date` and `end_date` to ISO `YYYY-MM`.
        2. Verifies `start_date <= end_date` and `start_date <= ref_date`.
        3. Anti-Hallucination Year Grounding: If `cv_text` contains 4-digit years, verifies
           that the extracted year (`YYYY`) actually exists in `cv_text`.
        """
        block_flags: List[str] = []
        ref_ym = ref_date_iso[:7] if ref_date_iso and len(ref_date_iso) >= 7 else "2024-06"

        iso_s, err_s = self._normalize_iso_month(jb.start_date)
        iso_e, err_e = self._normalize_iso_month(jb.end_date)

        if err_s:
            block_flags.append(err_s)
        if err_e:
            block_flags.append(err_e)

        jb.start_date = iso_s
        jb.end_date = iso_e

        if iso_s and iso_s > ref_ym:
            block_flags.append(f"start_after_ref_date:{iso_s}>{ref_ym}")
        if iso_e and iso_e > ref_ym:
            block_flags.append(f"end_after_ref_date:{iso_e}>{ref_ym}")
        if iso_s and iso_e and iso_s > iso_e:
            block_flags.append(f"start_after_end:{iso_s}>{iso_e}")

        # Anti-Hallucination Year Grounding against cv_text
        cv_years = set(re.findall(r"\b(19\d{2}|20\d{2})\b", cv_text or ""))
        if cv_years:
            if iso_s and iso_s[:4] not in cv_years:
                block_flags.append(f"hallucinated_year:{iso_s[:4]}_not_in_cv")
            if iso_e and iso_e[:4] not in cv_years:
                block_flags.append(f"hallucinated_year:{iso_e[:4]}_not_in_cv")

        return block_flags

    def segment(self, cv_text: str, cv_skills: List[ExtractedCVSkill]) -> SegmenterOutput:
        """
        Segments a CV into JobBlocks and maps skills' evidence spans to the job blocks.
        """
        flags: List[str] = []
        degraded: bool = False
        ref_date = self.config.get_reference_date()

        # --- Step 1: Extract Job Blocks with Retry / Degradation ---
        extraction_prompt = f"""
You are an expert technical recruiter. Analyze the following CV text and extract all job experiences into discrete job blocks.
For each job block, provide:
- job_id: A unique string identifier (e.g., job_1, job_2)
- title: The job title/role
- seniority_level: Estimate the level (Intern, Junior, Mid, Senior, Lead, Unknown) based on title and responsibilities
- start_date: Normalized ISO format YYYY-MM (if only a year like '2019' is given, use '2019-01')
- end_date: Normalized ISO format YYYY-MM (or null if ongoing / 'present' / 'hiện tại' / 'nay')
- raw_text: The text snippet for this job block

CV Text:
{cv_text}
"""
        try:
            extracted_jobs = self.llm_client.complete(extraction_prompt, JobBlockExtraction)
        except Exception as e:
            return SegmenterOutput(
                job_blocks=[],
                span_mappings=[],
                degraded=True,
                flags=[f"llm_job_extraction_failed:{str(e)}"],
            )

        # --- Lightweight Temporal & Year-Grounding Sanity Check ---
        seen_job_ids = set()
        validated_blocks: List[JobBlock] = []

        for jb in extracted_jobs.job_blocks:
            if jb.job_id in seen_job_ids:
                flags.append(f"duplicate_job_id:{jb.job_id}")
                degraded = True
                jb.job_id = f"{jb.job_id}_{len(seen_job_ids) + 1}"
            seen_job_ids.add(jb.job_id)

            block_flags = self._validate_temporal_and_year_grounding(jb, cv_text, ref_date)
            if block_flags:
                flags.extend([f"job_{jb.job_id}:{bf}" for bf in block_flags])
                degraded = True

            validated_blocks.append(jb)

        # --- Gather unique spans to map ---
        all_spans = []
        seen_spans = set()
        for skill in cv_skills:
            for span in skill.evidence_spans:
                if span not in seen_spans:
                    seen_spans.add(span)
                    all_spans.append(span)

        spans_list = all_spans

        if not spans_list:
            return SegmenterOutput(
                job_blocks=validated_blocks,
                span_mappings=[],
                degraded=degraded,
                flags=flags,
            )

        # Fast-Path A: If CV has 0 job blocks, all spans are deterministically UNASSIGNED (0 LLM calls)
        if not validated_blocks:
            return SegmenterOutput(
                job_blocks=[],
                span_mappings=[SpanMapping(span=span, job_id=UNASSIGNED_JOB_ID) for span in spans_list],
                degraded=degraded,
                flags=flags,
            )

        # Fast-Path B: Deterministic exact-substring attribution against each JobBlock's raw_text
        deterministic_map = {}
        unresolved_spans: List[str] = []

        def _norm_ws(s: str) -> str:
            return " ".join(s.strip().lower().split())

        block_corpora = [
            (
                jb.job_id,
                _norm_ws(f"{jb.title or ''} {jb.raw_quote or ''} {jb.raw_text or ''}"),
            )
            for jb in validated_blocks
        ]

        for span in spans_list:
            s_norm = _norm_ws(span)
            if not s_norm:
                deterministic_map[span] = SpanMapping(span=span, job_id=UNASSIGNED_JOB_ID)
                continue
            matched_job_ids = [
                jid for jid, corpus in block_corpora if corpus and s_norm in corpus
            ]
            if len(matched_job_ids) == 1:
                deterministic_map[span] = SpanMapping(span=span, job_id=matched_job_ids[0])
            else:
                unresolved_spans.append(span)

        # If 100% of spans matched uniquely via deterministic substring check, skip Step 1b LLM call!
        if not unresolved_spans:
            return SegmenterOutput(
                job_blocks=validated_blocks,
                span_mappings=[deterministic_map[s] for s in spans_list],
                degraded=degraded,
                flags=flags,
            )

        # --- Step 2: Map Only Unresolved Spans via LLM ---
        jobs_context = "\n".join([
            f"[{jb.job_id}] {jb.title} ({jb.start_date} - {jb.end_date}):\n{jb.raw_text}"
            for jb in validated_blocks
        ])
        spans_context = "\n".join([f"- {span}" for span in unresolved_spans])

        mapping_prompt = f"""
You have a list of extracted job blocks and a list of evidence spans (skill descriptions) found in the CV.
Your task is to map each evidence span to the appropriate job_id where it belongs.

Job Blocks:
{jobs_context}

Evidence Spans to map:
{spans_context}

For each evidence span, determine which job_id it belongs to.
If a span does not belong to any specific job block (e.g., it is from a general 'Skills' section), assign it the job_id "{UNASSIGNED_JOB_ID}".
Return the mapping for ALL provided spans exactly.
"""
        try:
            mapped_spans = self.llm_client.complete(mapping_prompt, SpanMappingExtraction)
            llm_map = {m.span: m for m in mapped_spans.span_mappings}
            mappings: List[SpanMapping] = []
            for s in spans_list:
                if s in deterministic_map:
                    mappings.append(deterministic_map[s])
                elif s in llm_map:
                    mappings.append(llm_map[s])
                else:
                    mappings.append(SpanMapping(span=s, job_id=UNASSIGNED_JOB_ID))
        except Exception as e:
            flags.append(f"llm_span_mapping_failed:{str(e)}")
            degraded = True
            mappings = [
                deterministic_map.get(span, SpanMapping(span=span, job_id=UNASSIGNED_JOB_ID))
                for span in spans_list
            ]

        return SegmenterOutput(
            job_blocks=validated_blocks,
            span_mappings=mappings,
            degraded=degraded,
            flags=flags,
        )

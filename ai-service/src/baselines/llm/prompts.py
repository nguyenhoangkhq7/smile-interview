import os
from typing import List, Optional

from src.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


def load_rubric(rubric_path: Optional[str] = None) -> str:
    """
    Loads the 1.0 - 5.0 proficiency evaluation rubric from disk.
    Defaults to config/rubric.md.
    """
    if not rubric_path:
        # Search relative to current file or working directory
        candidates = [
            os.path.join("config", "rubric.md"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "rubric.md"),
        ]
        for c in candidates:
            if os.path.exists(c):
                rubric_path = c
                break

    if rubric_path and os.path.exists(rubric_path):
        with open(rubric_path, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback minimal rubric string if file cannot be read
    return (
        "Proficiency Rubric (1.0 - 5.0 Scale):\n"
        "- 1.0: Basic Awareness / Beginner familiarity (intern/introductory).\n"
        "- 2.0: Working Knowledge / Supervised application (junior execution).\n"
        "- 3.0: Solid Practical Experience / Independent execution (mid-level).\n"
        "- 4.0: Advanced Expertise / Deep troubleshooting & optimization (senior).\n"
        "- 5.0: Lead / Master / Architectural authority (principal/lead architect)."
    )


def build_augmented_prompt(
    cv_text: str,
    jd_text: str,
    cv_skills: List[ExtractedCVSkill],
    jd_skills: List[ExtractedJDSkill],
    match_results: List[MatchResult],
    rubric_text: Optional[str] = None,
) -> str:
    """
    Builds the Chain-of-Thought evaluation prompt for LLMAugmentedBaseline.
    Includes Module 1 structured representations (w_j, soft_match, extracted evidence spans).
    """
    rubric = rubric_text or load_rubric()

    match_map = {m.jd_skill_id: m for m in match_results}
    cv_skill_map = {s.skill_id: s for s in cv_skills}

    skills_context_lines = []
    for s in jd_skills:
        match = match_map.get(s.skill_id)
        w_j_str = f"{match.w_j:.3f}" if match else "N/A"
        soft_match_str = f"{match.soft_match:.3f}" if match else "N/A"
        matched_cv_id = match.matched_cv_skill_id if match else "None"

        matched_cv_skill = cv_skill_map.get(matched_cv_id)
        cv_evidence = (
            "\n    ".join(matched_cv_skill.evidence_spans)
            if matched_cv_skill and matched_cv_skill.evidence_spans
            else "No explicit spans extracted by Module 1"
        )
        jd_evidence = "\n    ".join(s.evidence_spans) if s.evidence_spans else "No spans"

        skills_context_lines.append(
            f"Skill Requirement: '{s.skill_id}'\n"
            f"  - JD Importance Weight (w_j from GNN): {w_j_str}\n"
            f"  - Best Matched CV Skill: '{matched_cv_id}' (Semantic soft_match from SBERT: {soft_match_str})\n"
            f"  - JD Requirement Spans:\n    {jd_evidence}\n"
            f"  - Module 1 Candidate Evidence Spans:\n    {cv_evidence}"
        )

    skills_context = "\n\n".join(skills_context_lines)

    return f"""You are an elite technical recruiter and assessment auditor evaluating a candidate's CV against a Job Description (JD).
Your mission is to perform a rigorous, objective skill-gap analysis for EACH required skill.

=== EVALUATION RUBRIC (1.0 - 5.0 Scale) ===
{rubric}

=== CHAIN-OF-THOUGHT INSTRUCTIONS ===
For EACH skill listed below, you MUST follow this strict step-by-step reasoning in the "reasoning" field before committing to numbers:
Step (a) Locate Evidence: Search the CV text and evidence spans for direct or transferable experience. Quote the verbatim sentence(s) in "evidence_quote". If none exists, state clearly "No evidence found" and set "evidence_quote" to null.
Step (b) Assess Duration & Autonomy: Evaluate the real project tenure and whether the candidate worked under guidance (supervised) or led systems independently (autonomous).
Step (c) Estimate Candidate Proficiency (P_CV): Assign a score on the 1.0 to 5.0 scale according to the rubric.
Step (d) Estimate Required Proficiency (P_JD): Analyze the JD requirement description to determine the required mastery level (1.0 to 5.0).
Step (e) Determine Gap & Urgency:
    - semantic_alignment: MATCH (direct skill match), PARTIAL (substitute/transferable skill present), or MISSING (no viable evidence).
    - gap_magnitude: Normalized deficit score between 0.0 (fully qualified) and 1.0 (completely missing or severely underqualified).
    - priority: Interview urgency rating between 0.0 (no interview focus needed) and 1.0 (highest priority topic to interrogate in the technical interview).
Step (f) Objectivity Rule: Do NOT invent, assume, or extrapolate unmentioned achievements.

=== RAW CV TEXT ===
{cv_text}

=== RAW JD TEXT ===
{jd_text}

=== EXTRACTED MODULE 1 SIGNALS ===
{skills_context}

Output strictly valid JSON matching the LLMZeroShotResponse schema. Make sure every skill listed above has a corresponding entry in "skills".
"""


def build_text_only_prompt(
    cv_text: str,
    jd_text: str,
    jd_skills: List[ExtractedJDSkill],
    rubric_text: Optional[str] = None,
) -> str:
    """
    Builds the Chain-of-Thought evaluation prompt for LLMTextOnlyBaseline.
    Strictly text-only: does NOT contain Module 1 signals (soft_match, w_j, or cv_skills extractions).
    """
    rubric = rubric_text or load_rubric()

    skills_lines = [f"- {s.skill_id}" for s in jd_skills]
    skills_context = "\n".join(skills_lines)

    return f"""You are an elite technical recruiter and assessment auditor evaluating a candidate's raw CV against a raw Job Description (JD).
Your mission is to perform a rigorous, objective skill-gap analysis for EACH specified skill requirement.

=== EVALUATION RUBRIC (1.0 - 5.0 Scale) ===
{rubric}

=== CHAIN-OF-THOUGHT INSTRUCTIONS ===
For EACH skill listed below, you MUST follow this strict step-by-step reasoning in the "reasoning" field before committing to numbers:
Step (a) Locate Evidence: Search the raw CV text for direct or transferable experience. Quote the verbatim sentence(s) in "evidence_quote". If none exists, state clearly "No evidence found" and set "evidence_quote" to null.
Step (b) Assess Duration & Autonomy: Evaluate the real project tenure and whether the candidate worked under guidance (supervised) or led systems independently (autonomous).
Step (c) Estimate Candidate Proficiency (P_CV): Assign a score on the 1.0 to 5.0 scale according to the rubric.
Step (d) Estimate Required Proficiency (P_JD): Analyze the raw JD description to determine the required mastery level (1.0 to 5.0).
Step (e) Determine Gap & Urgency:
    - semantic_alignment: MATCH (direct skill match), PARTIAL (substitute/transferable skill present), or MISSING (no viable evidence).
    - gap_magnitude: Normalized deficit score between 0.0 (fully qualified) and 1.0 (completely missing or severely underqualified).
    - priority: Interview urgency rating between 0.0 (no interview focus needed) and 1.0 (highest priority topic to interrogate in the technical interview).
Step (f) Objectivity Rule: Do NOT invent, assume, or extrapolate unmentioned achievements.

=== RAW CV TEXT ===
{cv_text}

=== RAW JD TEXT ===
{jd_text}

=== REQUIRED SKILLS TO ASSESS ===
{skills_context}

Output strictly valid JSON matching the LLMZeroShotResponse schema. Make sure every skill listed above has a corresponding entry in "skills".
"""

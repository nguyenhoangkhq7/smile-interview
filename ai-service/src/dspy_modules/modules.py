"""
Declarative DSPy Modules wrapping Module 2 Signatures with ChainOfThought.
"""

import dspy
from src.dspy_modules.signatures import (
    JobBlockExtractionSignature,
    SpanMappingSignature,
    JDRequirementSignature,
    SpanRichnessSignature,
)


class DSPyJobBlockExtractorModule(dspy.Module):
    """DSPy Module for Step 1a: Extracting JobBlocks from raw CV text."""

    def __init__(self) -> None:
        super().__init__()
        self.extract = dspy.ChainOfThought(JobBlockExtractionSignature)

    def forward(self, cv_text: str) -> dspy.Prediction:
        return self.extract(cv_text=cv_text)


class DSPySpanMapperModule(dspy.Module):
    """DSPy Module for Step 1b: Mapping skill evidence spans to JobBlock IDs."""

    def __init__(self) -> None:
        super().__init__()
        self.map_spans = dspy.ChainOfThought(SpanMappingSignature)

    def forward(self, jobs_context: str, spans_context: str) -> dspy.Prediction:
        return self.map_spans(jobs_context=jobs_context, spans_context=spans_context)


class DSPyJDRequirementParserModule(dspy.Module):
    """DSPy Module for Step 2: Parsing JD required proficiency levels (P_JD)."""

    def __init__(self) -> None:
        super().__init__()
        self.parse_jd = dspy.ChainOfThought(JDRequirementSignature)

    def forward(self, jd_text: str, skills_context: str) -> dspy.Prediction:
        return self.parse_jd(jd_text=jd_text, skills_context=skills_context)


class DSPySpanRichnessAnalyzerModule(dspy.Module):
    """DSPy Module for Step 3: Classifying CV evidence spans into RICH_CONTEXT, LIST_ONLY, or AMBIGUOUS."""

    def __init__(self) -> None:
        super().__init__()
        self.analyze = dspy.ChainOfThought(SpanRichnessSignature)

    def forward(self, skill_id: str, spans_text: str) -> dspy.Prediction:
        return self.analyze(skill_id=skill_id, spans_text=spans_text)

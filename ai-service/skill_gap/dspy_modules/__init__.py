"""
DSPy declarative modules, signatures, dataset, metrics, and teleprompter compiler for Module 2 (skill_gap).
"""

from skill_gap.dspy_modules.signatures import (
    JobBlockExtractionSignature,
    SpanMappingSignature,
    JDRequirementSignature,
    SpanRichnessSignature,
)
from skill_gap.dspy_modules.modules import (
    DSPyJobBlockExtractorModule,
    DSPySpanMapperModule,
    DSPyJDRequirementParserModule,
    DSPySpanRichnessAnalyzerModule,
)

__all__ = [
    "JobBlockExtractionSignature",
    "SpanMappingSignature",
    "JDRequirementSignature",
    "SpanRichnessSignature",
    "DSPyJobBlockExtractorModule",
    "DSPySpanMapperModule",
    "DSPyJDRequirementParserModule",
    "DSPySpanRichnessAnalyzerModule",
]

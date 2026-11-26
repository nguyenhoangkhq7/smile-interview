"""DSPy modules for explicit skill extraction."""

import dspy

from matching_cv.dspy_modules.signatures import ExplicitSkillExtractionSignature


class DSPyExplicitSkillExtractorModule(dspy.Module):
    """Extract explicit competencies using an optimizable DSPy predictor."""

    def __init__(self) -> None:
        super().__init__()
        self.extract = dspy.Predict(ExplicitSkillExtractionSignature)

    def forward(self, document_type: str, document_text: str) -> dspy.Prediction:
        return self.extract(document_type=document_type, document_text=document_text)

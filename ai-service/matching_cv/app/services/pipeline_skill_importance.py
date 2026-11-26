"""Optional JD skill-importance stage for the analyze pipeline."""
import logging
from typing import Any, Callable, Dict, Optional, Protocol

from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse

logger = logging.getLogger(__name__)


class SkillImportanceEvaluator(Protocol):
    """Interface implemented by the production JD skill-importance evaluator."""

    def evaluate_jd_importance(
        self,
        *,
        jd_text: str,
        explicit_skills: list[dict[str, Any]],
        implicit_skills: list[dict[str, Any]],
        jd_id: str,
        force_enable: bool,
    ) -> Any: ...


class PipelineSkillImportanceStage:
    """Runs the optional importance estimator without failing the main analyze request."""

    def __init__(
        self,
        evaluator_provider: Callable[[], SkillImportanceEvaluator],
        enabled_by_default: bool,
    ) -> None:
        self._evaluator_provider = evaluator_provider
        self._evaluator: Optional[SkillImportanceEvaluator] = None
        self._enabled_by_default = enabled_by_default

    def evaluate(
        self,
        *,
        enabled: Optional[bool],
        unified_response: UnifiedExtractFileResponse,
        jd_text: str,
        fallback_jd_text: Optional[str],
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        is_enabled = self._enabled_by_default if enabled is None else enabled
        jd_document = unified_response.jd
        if not is_enabled or jd_document is None:
            return None

        try:
            explicit_skills = self._to_payloads(
                jd_document.explicit.skills if jd_document.explicit else []
            )
            implicit_skills = self._to_payloads(
                jd_document.implicit.skills if jd_document.implicit else []
            )
            if self._evaluator is None:
                self._evaluator = self._evaluator_provider()
            result = self._evaluator.evaluate_jd_importance(
                jd_text=jd_text or fallback_jd_text or "",
                explicit_skills=explicit_skills,
                implicit_skills=implicit_skills,
                jd_id=run_id,
                force_enable=True,
            )
            return result.model_dump()
        except Exception as error:
            logger.warning(
                f"[{run_id}] Skill importance estimation failed non-fatally: {error}"
            )
            return None

    @staticmethod
    def _to_payloads(skills: list[Any]) -> list[dict[str, Any]]:
        return [
            skill.model_dump() if hasattr(skill, "model_dump") else skill
            for skill in skills
        ]

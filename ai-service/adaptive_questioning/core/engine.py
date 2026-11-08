"""
LLM Execution Engine for Adaptive Questioning Pipeline V2.2 powered by DSPy (Khattab et al., 2023).
Implements declarative `dspy.Module` chains (`DSPyQuestionGeneratorModule` and `DSPyReflectiveJudgeModule`)
for Step 2A and Step 2B, alongside a deterministic `MockLLMEngine` for offline unit testing.
"""

from abc import ABC, abstractmethod
from collections import deque
import json
import os
from pathlib import Path
import re
from typing import Deque, List, Optional, Union

# Prevent LiteLLM from blocking on remote GitHub cost map fetches on Windows
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import dspy

from adaptive_questioning.config import MAX_SUB_SLOTS
from adaptive_questioning.core.math_utils import normalize_simplex
from adaptive_questioning.core.prompts import (
    Step2AAbductiveQuestionSignature,
    Step2BReflectivePBAJudgeSignature,
    build_step2a_layers,
    build_step2b_layers,
)
from adaptive_questioning.schemas.api_models import (
    ProposedSubSlot,
    Step2AQuestionOutput,
    Step2BJudgeOutput,
)
from adaptive_questioning.schemas.state import (
    ContextAnchor,
    MetamorphicTag,
    SkillBeliefState,
    TurnLog,
)


# ---------------------------------------------------------------------------
# Declarative DSPy Modules (Khattab et al., 2023)
# ---------------------------------------------------------------------------

class DSPyQuestionGeneratorModule(dspy.Module):
    """
    DSPy Module executing Step 2A: Abductive Chain-of-Thought (C -> A) & 3-Layer Question Generation.
    """

    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.ChainOfThought(Step2AAbductiveQuestionSignature)

    def forward(
        self,
        reference_layer_context: str,
        main_layer_directives: str,
    ) -> dspy.Prediction:
        return self.generate(
            reference_layer_context=reference_layer_context,
            main_layer_directives=main_layer_directives,
        )


class DSPyReflectiveJudgeModule(dspy.Module):
    """
    DSPy Module executing Step 2B: Reflective Two-Step Metamorphic PBA LLM-as-a-Judge.
    """

    def __init__(self) -> None:
        super().__init__()
        self.evaluate = dspy.ChainOfThought(Step2BReflectivePBAJudgeSignature)

    def forward(
        self,
        reference_layer_rubric: str,
        question_and_slot: str,
        candidate_response: str,
    ) -> dspy.Prediction:
        return self.evaluate(
            reference_layer_rubric=reference_layer_rubric,
            question_and_slot=question_and_slot,
            candidate_response=candidate_response,
        )


class BaseLLMEngine(ABC):
    """Abstract interface for Pipeline V2.2 LLM operations."""

    @abstractmethod
    def generate_question(
        self,
        skill: SkillBeliefState,
        context_anchors: List[ContextAnchor],
        turn_history: List[TurnLog],
        next_local_turn_k: int,
    ) -> Step2AQuestionOutput:
        """Execute Step 2A: Abductive CoT & 3-Layer Adaptive Question Generation."""

    @abstractmethod
    def evaluate_response(
        self,
        skill: SkillBeliefState,
        question: str,
        target_slot_id: str,
        candidate_response: str,
    ) -> Step2BJudgeOutput:
        """Execute Step 2B: Reflective Two-Step Metamorphic PBA Judge."""


class MockLLMEngine(BaseLLMEngine):
    """
    Deterministic Mock LLM Engine for offline unit testing and reproducible simulations.
    Supports both scripted response queues and rule-based deterministic evaluation.
    """

    def __init__(
        self,
        scripted_questions: Optional[List[Step2AQuestionOutput]] = None,
        scripted_judgments: Optional[List[Step2BJudgeOutput]] = None,
    ) -> None:
        self.question_queue: Deque[Step2AQuestionOutput] = deque(scripted_questions or [])
        self.judgment_queue: Deque[Step2BJudgeOutput] = deque(scripted_judgments or [])
        self.dspy_question_module = DSPyQuestionGeneratorModule()
        self.dspy_judge_module = DSPyReflectiveJudgeModule()

    def generate_question(
        self,
        skill: SkillBeliefState,
        context_anchors: List[ContextAnchor],
        turn_history: List[TurnLog],
        next_local_turn_k: int,
    ) -> Step2AQuestionOutput:
        if self.question_queue:
            return self.question_queue.popleft()

        anchor_bridge = ""
        if context_anchors:
            latest_anchor = context_anchors[-1]
            if latest_anchor.consolidated_summary:
                anchor_bridge = (
                    f"Tiếp nối phần trao đổi vừa rồi về '{latest_anchor.jd_skill_id}' "
                    f"({latest_anchor.consolidated_summary}), "
                )
            else:
                anchor_bridge = (
                    f"Từ kinh nghiệm làm việc với '{latest_anchor.jd_skill_id}' "
                    f"tại vị trí {latest_anchor.context_job or 'hiện tại'}, "
                )

        if next_local_turn_k == 1:
            evidence_preview = (
                skill.cv_evidence_spans[0]
                if skill.cv_evidence_spans
                else "chưa nêu chi tiết kỹ thuật"
            )
            surprising_fact = (
                f"C_0: Trong CV tại '{skill.context_job or 'N/A'}', kỹ năng '{skill.jd_skill_id}' "
                f"chỉ đạt s_cv={skill.candidate_proficiency:.1f} ('{evidence_preview}') trong khi JD yêu cầu "
                f"r_target={skill.required_proficiency:.1f}."
            )
            hypothesis = (
                f"A_0: Ứng viên có thể đã vận hành '{skill.jd_skill_id}' ở tầng sâu hơn trong thực tế "
                "nhưng chỉ ghi tóm tắt ngắn gọn trong CV, hoặc chỉ mới dùng các thao tác cơ bản."
            )
            target_slot_id = f"{skill.jd_skill_id}:primary"
            question = (
                f"{anchor_bridge}khi vận hành {skill.jd_skill_id} ở mức độ yêu cầu {skill.required_proficiency:.1f}/5.0, "
                f"bạn hãy mô tả cụ thể các bước chẩn đoán (troubleshooting) và đánh đổi kiến trúc mà bạn đã trực tiếp "
                f"thực hiện khi xử lý một sự cố thực tế?"
            )
            return Step2AQuestionOutput(
                surprising_fact_C=surprising_fact,
                hypothesis_A=hypothesis,
                new_sub_slot=None,
                target_slot_id=target_slot_id,
                question=question,
            )

        # Follow-up turns k in {2, 3}
        last_turn = next(
            (t for t in reversed(turn_history) if t.skill_id == skill.jd_skill_id),
            None,
        )
        prev_insight = (
            last_turn.reflective_insight
            if last_turn and last_turn.reflective_insight
            else "Câu trả lời trước chưa làm rõ cơ chế nội tại ở mức production."
        )
        surprising_fact = (
            f"C_{next_local_turn_k - 1}: Từ câu trả lời trước về '{skill.jd_skill_id}', {prev_insight}"
        )
        hypothesis = (
            f"A_{next_local_turn_k - 1}: Cần kiểm chứng thêm cơ chế xử lý lỗi biên (edge-case recovery) "
            f"và tối ưu hiệu năng của '{skill.jd_skill_id}' để phân biệt giữa mức Med (3.0) và High (4.5)."
        )

        new_sub_slot: Optional[ProposedSubSlot] = None
        if len(skill.active_sub_slots) < MAX_SUB_SLOTS:
            sub_idx = len(skill.active_sub_slots) + 1
            slot_name = f"{skill.jd_skill_id}_probing_aspect_{sub_idx}"
            new_sub_slot = ProposedSubSlot(
                slot_name=slot_name,
                description=(
                    f"Kiểm chứng quy trình xử lý sự cố chuyên sâu và đánh đổi kiến trúc #{sub_idx} "
                    f"cho kỹ năng {skill.jd_skill_id} ở ngưỡng {skill.required_proficiency:.1f}."
                ),
            )
            target_slot_id = f"{skill.jd_skill_id}:sub_{sub_idx}"
        else:
            target_slot_id = (
                skill.active_sub_slots[-1].slot_id
                if skill.active_sub_slots
                else f"{skill.jd_skill_id}:primary"
            )

        question = (
            f"Đi sâu hơn vào tình huống vừa nêu của {skill.jd_skill_id}: nếu hệ thống gặp hiện tượng nghẽn tài nguyên "
            f"hoặc lỗi phân tán ở tầng dưới, bạn đã kiểm tra những thông số kỹ thuật nào và quyết định xử lý ra sao?"
        )
        return Step2AQuestionOutput(
            surprising_fact_C=surprising_fact,
            hypothesis_A=hypothesis,
            new_sub_slot=new_sub_slot,
            target_slot_id=target_slot_id,
            question=question,
        )

    def evaluate_response(
        self,
        skill: SkillBeliefState,
        question: str,
        target_slot_id: str,
        candidate_response: str,
    ) -> Step2BJudgeOutput:
        if self.judgment_queue:
            return self.judgment_queue.popleft()

        text = (candidate_response or "").strip()
        lower = text.lower()

        # 1. Explicit tag override or verbatim CV repetition / buzzword-only (INVARIANT)
        cv_spans_lower = [s.strip().lower() for s in skill.cv_evidence_spans if s.strip()]
        is_verbatim_cv = any(lower == span for span in cv_spans_lower)
        if (
            "[invariant]" in lower
            or is_verbatim_cv
            or "buzzword" in lower
            or "tôi rất giỏi" in lower
            or "lạc đề" in lower
            or len(text) < 15
        ):
            return Step2BJudgeOutput(
                extracted_slot_value=None,
                reflective_insight=(
                    f"Ứng viên chỉ nêu từ khóa chung chung hoặc lặp lại nội dung CV mà không đưa ra được "
                    f"bằng chứng kỹ thuật thực tế nào đối chiếu với các mức Rubric [1.5, 3.0, 4.5]."
                ),
                metamorphic_tag=MetamorphicTag.INVARIANT,
                raw_posterior_probs=normalize_simplex(skill.current_belief),
                consolidated_summary=(
                    f"Ứng viên chưa cung cấp thêm bằng chứng thực tế ngoài CV cho kỹ năng {skill.jd_skill_id}."
                ),
            )

        # 2. Explicit admission of lacking skill -> DECISIVE_SHIFT toward Low (1.5)
        if (
            "[decisive_low]" in lower
            or "không biết" in lower
            or "chưa từng làm" in lower
            or "tôi chưa có kinh nghiệm" in lower
            or "em chưa làm thực tế" in lower
        ):
            return Step2BJudgeOutput(
                extracted_slot_value="Ứng viên xác nhận chưa có kinh nghiệm thực chiến với kỹ năng này.",
                reflective_insight=(
                    f"Ứng viên thừa nhận trực tiếp việc thiếu kinh nghiệm thực tế với {skill.jd_skill_id}, "
                    f"tương ứng rõ ràng với tâm cụm Rubric Low (c = 1.5)."
                ),
                metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
                raw_posterior_probs=[0.98, 0.015, 0.005],
                consolidated_summary=(
                    f"Xác minh ứng viên chỉ ở mức cơ bản/nhập môn (Low) với {skill.jd_skill_id}."
                ),
            )

        # 3. Deep production mastery -> DECISIVE_SHIFT toward High (4.5)
        high_mastery_keywords = [
            "[decisive_high]",
            "[decisive]",
            "kernel",
            "cgroup",
            "ebpf",
            "systemd",
            "journalctl",
            "strace",
            "tcpdump",
            "sysctl",
            "oom-killer",
            "statefile",
            "etcd",
            "raft",
            "zero-downtime",
            "root cause",
        ]
        if any(kw in lower for kw in high_mastery_keywords):
            return Step2BJudgeOutput(
                extracted_slot_value=text[:200],
                reflective_insight=(
                    f"Ứng viên phân tích sắc bén quy trình chẩn đoán sự cố production và cơ chế nội tại của "
                    f"{skill.jd_skill_id}, đạt mức làm chủ chuyên sâu tại tâm cụm Rubric High (c = 4.5, s_jd = {skill.required_proficiency:.1f})."
                ),
                metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
                raw_posterior_probs=[0.005, 0.015, 0.98],
                consolidated_summary=(
                    f"Ứng viên chứng minh năng lực làm chủ chuyên sâu (High) với {skill.jd_skill_id} qua xử lý sự cố production."
                ),
            )

        # 4. External constraint / Context Invalidation -> MINOR_SHIFT
        minor_keywords = [
            "[minor]",
            "phân quyền",
            "giới hạn quyền",
            "team hạ tầng quản lý",
            "bị khóa quyền",
            "chỉ có quyền read-only",
        ]
        if any(kw in lower for kw in minor_keywords):
            return Step2BJudgeOutput(
                extracted_slot_value=text[:200],
                reflective_insight=(
                    f"Ứng viên có hiểu biết gián tiếp về {skill.jd_skill_id} nhưng bị giới hạn phạm vi can thiệp "
                    f"do phân quyền tổ chức (Context Invalidation), tiệm cận mức Rubric Med (c = 3.0)."
                ),
                metamorphic_tag=MetamorphicTag.MINOR_SHIFT,
                raw_posterior_probs=[0.15, 0.70, 0.15],
                consolidated_summary=(
                    f"Ứng viên nắm quy trình {skill.jd_skill_id} ở mức trung bình (Med) trong phạm vi phân quyền cho phép."
                ),
            )

        # 5. Default practical example -> MODERATE_SHIFT
        return Step2BJudgeOutput(
            extracted_slot_value=text[:200],
            reflective_insight=(
                f"Ứng viên nêu được ví dụ vận hành thực tế hợp lệ với {skill.jd_skill_id} ở mức Rubric Med-High "
                f"(c = 3.0 - 4.5), nhưng phạm vi độ sâu ở mức vừa phải."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.05, 0.30, 0.65],
            consolidated_summary=(
                f"Ứng viên có kinh nghiệm thực hành tốt với {skill.jd_skill_id} qua các tác vụ vận hành thực tế."
            ),
        )


class OpenAILLMEngine(BaseLLMEngine):
    """
    Production LLM Engine executing Declarative DSPy Modules (`DSPyQuestionGeneratorModule`
    and `DSPyReflectiveJudgeModule`) with `dspy.LM` via OpenRouter or OpenAI.
    Raises errors directly without silent mock fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        compiled_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        openrouter_key = api_key or os.environ.get("OPENROUTER_API_KEY")

        self.api_key = openrouter_key or None
        self.base_url = base_url or "https://openrouter.ai/api/v1"
        self.model = model or os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.7-flash")
        dspy_model_name = (
            self.model
            if self.model.startswith("openrouter/")
            else f"openrouter/{self.model}"
        )

        self.dspy_question_module = DSPyQuestionGeneratorModule()
        self.dspy_judge_module = DSPyReflectiveJudgeModule()

        # Auto-load compiled teleprompter artifacts if available
        comp_dir = (
            Path(compiled_dir)
            if compiled_dir
            else (Path(__file__).resolve().parent.parent / "compiled_modules")
        )
        q_compiled = comp_dir / "question_generator.json"
        j_compiled = comp_dir / "reflective_judge.json"
        if q_compiled.exists():
            try:
                self.dspy_question_module.load(str(q_compiled))
            except Exception:
                pass
        if j_compiled.exists():
            try:
                self.dspy_judge_module.load(str(j_compiled))
            except Exception:
                pass

        self.dspy_lm: Optional[dspy.LM] = None
        if self.api_key:
            lm_kwargs = {
                "api_key": self.api_key,
                "temperature": 0.0,
                "cache": False,
                "engine": "litellm",
                "timeout": 60,
                "num_retries": 3,
                "extra_body": {"reasoning": {"effort": "none"}},
            }
            if self.base_url:
                lm_kwargs["api_base"] = self.base_url
            self.dspy_lm = dspy.LM(dspy_model_name, **lm_kwargs)

    @property
    def is_compiled(self) -> bool:
        """Check if DSPy modules have loaded teleprompter demonstrations."""
        try:
            q_state = self.dspy_question_module.dump_state()
            q_demos = q_state.get("generate.predict", {}).get("demos", [])
            return len(q_demos) > 0
        except Exception:
            return False

    def _ensure_configured(self) -> None:
        if not self.api_key or self.dspy_lm is None:
            raise RuntimeError(
                "Missing LLM API Key. Please configure OPENROUTER_API_KEY in your .env file."
            )

    def generate_question(
        self,
        skill: SkillBeliefState,
        context_anchors: List[ContextAnchor],
        turn_history: List[TurnLog],
        next_local_turn_k: int,
    ) -> Step2AQuestionOutput:
        self._ensure_configured()
        assert self.dspy_lm is not None

        ref_layer, main_layer = build_step2a_layers(
            skill=skill,
            context_anchors=context_anchors,
            turn_history=turn_history,
            next_local_turn_k=next_local_turn_k,
        )

        with dspy.context(lm=self.dspy_lm):
            pred = self.dspy_question_module(
                reference_layer_context=ref_layer,
                main_layer_directives=main_layer,
            )

        sub_slot_val = getattr(pred, "new_sub_slot", None)
        if isinstance(sub_slot_val, dict):
            sub_slot_val = ProposedSubSlot.model_validate(sub_slot_val)

        output = Step2AQuestionOutput(
            surprising_fact_C=str(pred.surprising_fact_C),
            hypothesis_A=str(pred.hypothesis_A),
            new_sub_slot=sub_slot_val,
            target_slot_id=str(pred.target_slot_id),
            question=str(pred.question),
        )

        if next_local_turn_k == 1 or len(skill.active_sub_slots) >= MAX_SUB_SLOTS:
            output.new_sub_slot = None
        return output

    def evaluate_response(
        self,
        skill: SkillBeliefState,
        question: str,
        target_slot_id: str,
        candidate_response: str,
    ) -> Step2BJudgeOutput:
        self._ensure_configured()
        assert self.dspy_lm is not None

        ref_rubric, question_and_slot = build_step2b_layers(
            skill=skill,
            question=question,
            target_slot_id=target_slot_id,
        )

        with dspy.context(lm=self.dspy_lm):
            pred = self.dspy_judge_module(
                reference_layer_rubric=ref_rubric,
                question_and_slot=question_and_slot,
                candidate_response=candidate_response,
            )

        tag_val = pred.metamorphic_tag
        if not isinstance(tag_val, MetamorphicTag):
            tag_val = MetamorphicTag(str(tag_val).strip())

        raw_probs = getattr(pred, "raw_posterior_probs", [0.3333, 0.3333, 0.3334])
        if isinstance(raw_probs, str):
            try:
                raw_probs = json.loads(raw_probs)
            except Exception:
                extracted = re.findall(r"\d+\.?\d*", raw_probs)
                raw_probs = [float(x) for x in extracted[:3]]
        if not isinstance(raw_probs, (list, tuple)) or len(raw_probs) != 3:
            raw_probs = [0.3333, 0.3333, 0.3334]

        return Step2BJudgeOutput(
            extracted_slot_value=getattr(pred, "extracted_slot_value", None),
            reflective_insight=str(pred.reflective_insight),
            metamorphic_tag=tag_val,
            raw_posterior_probs=normalize_simplex(list(raw_probs)),
            consolidated_summary=str(pred.consolidated_summary),
        )

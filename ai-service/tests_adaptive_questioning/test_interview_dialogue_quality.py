"""Replay a fixed Vietnamese interview case through the production response workflow."""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from adaptive_questioning.evidence.models import Action
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from test_evidence_workflow import answer, setup, skill, start


@pytest.mark.parametrize("live", [
    False,
    pytest.param(True, marks=pytest.mark.skipif(os.getenv("RUN_INTERVIEW_DIALOGUE_EVAL") != "1",
                                                reason="Opt-in model evaluation")),
])
@pytest.mark.parametrize(("response", "expected"), [
    ("Dạ, em chưa biết ạ.", Action.EASIER),
    ("Em sẽ thử ở gần ngưỡng miễn phí.", Action.CLARIFY),
    ("Em thử đúng 500.000 đồng. Nếu hệ thống vẫn tính phí thì điều kiện ở mốc này bị sai.", None),
])
def test_shipping_threshold_dialogue(setup, response, expected, live):
    provider, engine, _ = setup
    initial = start(engine, [skill("kiểm thử")]).snapshot
    turn = initial.pending_turn
    objective = initial.objectives[turn.objective_id].objective
    objective.claim = "Kiểm thử quy tắc miễn phí vận chuyển ở giá trị biên."
    criterion = objective.criteria[0]
    criterion.description = "Chọn ca kiểm thử phát hiện việc loại nhầm giá trị đúng ngưỡng."
    criterion.expected_evidence = criterion.at_target = "Chọn đơn đúng 500.000 đồng và mong đợi miễn phí."
    criterion.below_target = "Cho rằng đơn đúng ngưỡng vẫn chịu phí."
    criterion.above_target = "Phân biệt lỗi loại nhầm ngưỡng với lỗi làm tròn tiền."
    turn.question.text = ("Đơn từ 500.000 đồng được miễn phí vận chuyển. "
                          "Bạn chọn ca kiểm thử nào để phát hiện hệ thống loại nhầm đơn đúng ngưỡng?")
    turn.question.evidence_scope = "shipping-threshold"

    if live:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        engine.provider = DSPyAssessmentProvider()
    elif expected == Action.CLARIFY:
        provider.observation, provider.performance = "UNCLEAR", "UNDETERMINED"
    result = answer(engine, initial, response)
    next_turn = result.public.pending_turn
    print(response, result.public.turns[-1].feedback, next_turn.question if next_turn else "(kết thúc)", sep="\n")
    if expected is None:
        assert next_turn is None
    else:
        assert result.snapshot.pending_turn.action == expected
        if expected == Action.CLARIFY:
            assert result.snapshot.pending_turn.question.evidence_scope == turn.question.evidence_scope
        else:
            assert result.snapshot.pending_turn.question_depth < turn.question_depth

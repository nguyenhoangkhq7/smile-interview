"""Large CV/JD profiles must not require one oversized model response."""
import json
from threading import Barrier, Lock

import pytest

from adaptive_questioning.evidence.models import Blueprint
from adaptive_questioning.evidence.planning import BlueprintBuilder, requirements_for
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from test_evidence_workflow import ScriptedProvider, skill


def test_large_profile_prepares_all_requirements_in_bounded_parallel_calls():
    class RecordingProvider(ScriptedProvider):
        def __init__(self):
            super().__init__()
            self.calls = []
            self.lock = Lock()
            self.first_wave = Barrier(3)

        def blueprint(self, context):
            with self.lock:
                self.calls.append(json.loads(context)["requirements"])
                first_wave = len(self.calls) <= 3
            if first_wave:
                self.first_wave.wait(timeout=5)
            return super().blueprint(context)

    skills = [skill(f"skill-{index}") for index in range(36)]
    provider = RecordingProvider()
    result = BlueprintBuilder(provider).build(skills)
    expected = requirements_for(skills)
    assert [objective.requirement_id for objective in result.objectives] == list(expected)
    assert len({objective.objective_id for objective in result.objectives}) == 36
    assert max(len(call) for call in provider.calls) <= 4
    assert sum(len(call) for call in provider.calls) == len(expected)
    assert {objective.skill_id for objective in result.objectives} == {item.jd_skill_id for item in skills}


def test_batch_cannot_swap_coverage_with_another_batch():
    class WrongCoverageProvider(ScriptedProvider):
        def blueprint(self, context):
            result = super().blueprint(context)
            result.objectives[0].requirement_id = "another-batch:inferred"
            return Blueprint(objectives=result.objectives)

    with pytest.raises(ValueError, match="every requirement exactly once"):
        BlueprintBuilder(WrongCoverageProvider()).build([skill(f"skill-{index}") for index in range(8)])


def test_failed_batch_does_not_return_a_partial_blueprint():
    class FailingProvider(ScriptedProvider):
        def blueprint(self, context):
            if "skill-5" in context:
                raise TimeoutError("Model did not finish this batch")
            return super().blueprint(context)

    with pytest.raises(TimeoutError):
        BlueprintBuilder(FailingProvider()).build([skill(f"skill-{index}") for index in range(8)])


def test_disabled_optional_extension_cannot_block_interview_preparation():
    class ExtensionProvider(ScriptedProvider):
        def blueprint(self, context):
            result = super().blueprint(context)
            for objective in result.objectives:
                objective.target_depth = 1
                objective.extension_depth = 2
            return result

    result = BlueprintBuilder(ExtensionProvider()).build([skill()])
    assert result.objectives[0].target_depth == 2
    assert result.objectives[0].extension_depth is None
    assert result.objectives[0].extension_criterion_ids == []
    with pytest.raises(ValueError, match="Extension depth"):
        BlueprintBuilder(ExtensionProvider(), InterviewPolicy(allow_extension_probes=True)).build([skill()])

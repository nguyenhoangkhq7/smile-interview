"""Large CV/JD profiles must not require one oversized model response."""
import json
from threading import Barrier, Lock

import dspy
import pytest

from adaptive_questioning.evidence.planning import BlueprintBuilder, requirements_for
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.provider import BlueprintSignature, DSPyAssessmentProvider
from test_evidence_workflow import ScriptedProvider, skill


def test_dspy_blueprint_draft_omits_fields_owned_by_the_builder():
    description = "Optimize SQL queries"
    skills = [skill(job_tasks=[{
        "task_id": "optimize", "description": description, "required_level": 3,
        "requirement_kind": "OPTIONAL", "level_basis": "EXPLICIT", "evidence_spans": [description],
    }])]
    requirements = requirements_for(skills)
    draft = ScriptedProvider().blueprint(json.dumps({"requirements": requirements})).model_dump(mode="json")
    lm = dspy.utils.DummyLM([{"blueprint": draft}])
    lm.adapter = dspy.JSONAdapter()
    provider = DSPyAssessmentProvider(lm=lm)
    objective = BlueprintBuilder(provider).build(skills).objectives[0]

    schema = BlueprintSignature.output_fields["blueprint"].annotation.model_json_schema()
    assert {"objective_id", "claim", "inferred", "requirement_kind",
            "jd_evidence_spans", "extension_criterion_ids", "rubric_version"}.isdisjoint(
        schema["$defs"]["ObjectiveDraft"]["properties"]
    )
    assert "required_proficiency" not in objective.model_dump()
    assert "rationale" not in schema["$defs"]["SuitableMode"]["properties"]
    assert "criterion_id" not in schema["$defs"]["CriterionDraft"]["properties"]
    assert objective.claim == description
    assert objective.requirement_kind == "OPTIONAL"
    assert {"inferred", "extension_criterion_ids", "rubric_version"}.isdisjoint(objective.model_dump())
    assert objective.jd_evidence_spans == [description]
    assert objective.criteria[0].criterion_id == f"{objective.objective_id}:c1"


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
    assert all("requirement_id" not in requirement and "has_task" not in requirement
               for call in provider.calls for requirement in call.values())
    assert {objective.skill_id for objective in result.objectives} == {item.jd_skill_id for item in skills}


def test_batch_cannot_swap_coverage_with_another_batch():
    class WrongCoverageProvider(ScriptedProvider):
        def blueprint(self, context):
            result = super().blueprint(context)
            result.objectives[0].requirement_id = "another-batch:inferred"
            return result

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

    result = BlueprintBuilder(ExtensionProvider(), InterviewPolicy(allow_extension_probes=False)).build([skill()])
    assert result.objectives[0].target_depth == 2
    assert result.objectives[0].extension_depth is None
    assert "extension_criterion_ids" not in result.objectives[0].model_dump()
    with pytest.raises(ValueError, match="Extension depth"):
        BlueprintBuilder(ExtensionProvider(), InterviewPolicy(allow_extension_probes=True)).build([skill()])

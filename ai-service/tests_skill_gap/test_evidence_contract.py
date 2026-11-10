from unittest.mock import Mock

import pytest

from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, JDParserOutput, JDRequirement, JobTask, SpanMapping
from skill_gap.domain.enums import SkillType
from skill_gap.services.jd_requirement_parser import JDRequirementParser
from skill_gap.services.proficiency_estimator import ProficiencyEstimator, SpanAnalysisList


@pytest.mark.parametrize("quote", ["", "Invented SQL responsibility"])
def test_ungrounded_task_marks_c2_degraded(quote):
    llm = Mock()
    llm.complete.return_value = JDParserOutput(requirements=[JDRequirement(
        jd_skill_id="sql", required_level=4, reasoning="task complexity",
        tasks=[JobTask(description="Optimize SQL", required_level=4, evidence_spans=[quote])],
    )])
    skill = ExtractedJDSkill(skill_id="sql", type=SkillType.EXPLICIT, confidence=1, evidence_spans=["Optimize SQL"])
    result = JDRequirementParser(llm).parse("Optimize SQL", [skill])
    assert result.degraded
    assert result.requirements[0].tasks == []


def test_grounded_optional_task_retains_required_depth_and_stable_id():
    llm = Mock()
    llm.complete.return_value = JDParserOutput(requirements=[JDRequirement(
        jd_skill_id="sql", required_level=4, reasoning="advanced optimization",
        tasks=[JobTask(description="Optimize SQL", required_level=4,
                       evidence_spans=["Advanced SQL optimization is a plus"], requirement_kind="OPTIONAL")],
    )])
    text = "Advanced SQL optimization is a plus"
    skill = ExtractedJDSkill(skill_id="sql", type=SkillType.EXPLICIT, confidence=1, evidence_spans=[text])
    parser = JDRequirementParser(llm)
    first, second = parser.parse(text, [skill]), parser.parse(text, [skill])
    assert not first.degraded
    assert first.requirements[0].tasks[0].required_level == 4
    assert first.requirements[0].tasks[0].task_id == second.requirements[0].tasks[0].task_id


def test_missing_richness_results_are_tracked_as_degraded():
    llm = Mock()
    llm.complete.return_value = SpanAnalysisList(analyses=[])
    estimator = ProficiencyEstimator(llm)
    skill = ExtractedCVSkill(skill_id="sql", type=SkillType.EXPLICIT, confidence=1, evidence_spans=["Applied SQL in project"])
    values = estimator.estimate_batch([skill], [SpanMapping(span=skill.evidence_spans[0], job_id="job")], [])
    assert values[0].degraded
    assert "richness_analysis_fallback" in values[0].flags


def test_runtime_jd_demos_ground_tasks_and_preserve_optional_complexity():
    import json
    from pathlib import Path
    path = Path(__file__).parents[1] / "skill_gap/compiled_modules/jd_parser.json"
    demos = json.loads(path.read_text(encoding="utf-8"))["parse_jd.predict"]["demos"]
    tasks = [(task, demo["jd_text"]) for demo in demos for req in demo["requirements"] for task in req["tasks"]]
    assert tasks
    assert all(quote and quote in jd for task, jd in tasks for quote in task["evidence_spans"])
    assert any(task["requirement_kind"] == "OPTIONAL" and task["required_level"] == 4 for task, _ in tasks)

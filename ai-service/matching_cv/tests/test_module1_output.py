from types import SimpleNamespace

import pytest

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult, ExtractionStats
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services.standardized_output_builder import (
    Module1OutputError,
    PublicOutputContext,
    build_module1_output,
)


def document(side, evidence_by_skill):
    skills = [
        ExtractedSkill(skill_id=skill, evidences=[
            Evidence(surface_form=skill, sentence=sentence, kind="skill")
        ])
        for skill, sentence in evidence_by_skill.items()
    ]
    count = len(skills)
    return DocumentUnifiedResult(
        document_type=side,
        raw_text="\n".join(evidence_by_skill.values()),
        explicit=ExtractionResult(
            skills=skills,
            stats=ExtractionStats(
                total_mentions=count, unique_skills=count,
                unresolved_evidences=count, unresolved_mentions=count,
            ),
        ),
    )


@pytest.fixture
def context():
    cv = document("CV", {"postgresql": "I optimized postgresql queries."})
    jd = document("JD", {"postgresql": "Optimize postgresql queries.", "kafka": "Operate kafka."})
    nodes = {
        "shared": SimpleNamespace(
            node_id="shared", cv_canonical_id="postgresql", jd_canonical_id="postgresql",
            cv_occurrence_ids=[], jd_occurrence_ids=[], cosine_similarity_if_shared=0.93,
            merge_decision=SimpleNamespace(merge_reason="same_canonical_id"),
        ),
        "unmatched": SimpleNamespace(
            node_id="unmatched", cv_canonical_id=None, jd_canonical_id="kafka",
            cv_occurrence_ids=[], jd_occurrence_ids=[],
        ),
    }
    return PublicOutputContext(
        cv_text=cv.raw_text,
        jd_text=jd.raw_text,
        unified_response=UnifiedExtractFileResponse(run_id="test", status="completed", cv=cv, jd=jd),
        graph_data=SimpleNamespace(skill_nodes=nodes, diagnostics={}),
        skill_importance_output={"records": [
            {"skill_id": "postgresql", "weight": 0.91},
            {"skill_id": "kafka", "weight": 0.63},
        ]},
    )


def test_module1_output_preserves_evidence_and_retains_unmatched_jd_skills(context):
    output = build_module1_output(context)

    assert output.matcher_source == "MATCHING_CV"
    assert output.cv_skills[0].evidence_spans == ["I optimized postgresql queries."]
    assert output.cv_skills[0].confidence == 0.0
    assert [skill.skill_id for skill in output.jd_skills] == ["postgresql", "kafka"]
    assert [match.model_dump() for match in output.match_results] == [
        dict(jd_skill_id="postgresql", matched_cv_skill_id="postgresql", soft_match=0.93, w_j=0.91),
        dict(jd_skill_id="kafka", matched_cv_skill_id="none", soft_match=0.0, w_j=0.63),
    ]


def test_module1_output_rejects_missing_weight(context):
    context.skill_importance_output["records"].pop()

    with pytest.raises(Module1OutputError, match="Missing JD skill importance for kafka"):
        build_module1_output(context)


def test_module1_keeps_display_name_separate_from_cached_ascii_id(context):
    skill = context.unified_response.jd.explicit.skills[0]
    skill.surface_forms = ['Phát triển AI Coding Agent']
    skill.evidences[0].surface_form = skill.surface_forms[0]
    skill.evidences[0].sentence = 'Yêu cầu Phát triển AI Coding Agent.'
    context.unified_response.jd.raw_text = skill.evidences[0].sentence + '\nOperate kafka.'
    context.jd_text = context.unified_response.jd.raw_text
    context.skill_importance_output['records'][0]['skill_name'] = 'ph t tri n ai coding agent'
    output = build_module1_output(context)
    assert output.jd_skills[0].skill_id == 'postgresql'
    assert output.jd_skills[0].skill_name == 'Phát triển AI Coding Agent'
    assert output.jd_skills[0].evidence_spans == ['Yêu cầu Phát triển AI Coding Agent.']

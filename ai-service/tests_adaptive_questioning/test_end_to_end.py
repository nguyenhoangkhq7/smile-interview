"""
End-to-End integration and simulation tests for Stage 4:
Verifies FastAPI REST endpoints (/start -> /respond -> /report/{session_id}),
multi-turn belief updates (DECISIVE_SHIFT, MODERATE_SHIFT, INVARIANT),
probing sub-slot creation and Garbage Collection (GC), 1-line memory consolidation,
and Phase 4 Auditable HITL Report generation.
"""

import json
import math
from pathlib import Path

import dspy
from fastapi.testclient import TestClient
from langgraph.graph.state import CompiledStateGraph
import pytest

from adaptive_questioning.config import DELTA_BOUNDS
from adaptive_questioning.core.engine import (
    DSPyQuestionGeneratorModule,
    DSPyReflectiveJudgeModule,
    MockLLMEngine,
)
from adaptive_questioning.core.prompts import (
    Step2AAbductiveQuestionSignature,
    Step2BReflectivePBAJudgeSignature,
)
from adaptive_questioning.main import create_app


MOCK_JSON_PATH = Path(__file__).parent / "mock_skill_gap_output.json"


@pytest.fixture
def mock_skill_gaps():
    with open(MOCK_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def client():
    app = create_app(engine=MockLLMEngine())
    return TestClient(app)


class TestEndToEndInterviewSimulation:
    """Full multi-turn API simulation test."""

    def test_full_interview_lifecycle_start_respond_and_report(
        self, client: TestClient, mock_skill_gaps
    ):
        # -------------------------------------------------------------------
        # 1. Start Interview (POST /api/v1/interview/start)
        # -------------------------------------------------------------------
        start_resp = client.post("/api/v1/interview/start", json=mock_skill_gaps)
        assert start_resp.status_code == 200
        start_data = start_resp.json()

        session_id = start_data["session_id"]
        assert start_data["turn"] == 1
        # Highest priority skill is 'terraform' (priority 0.24 > linux 0.09, while kubernetes is NONE)
        assert start_data["active_skill_id"] == "terraform"
        assert start_data["is_finished"] is False
        assert len(start_data["initial_belief"]) == 3
        assert math.isclose(sum(start_data["initial_belief"]), 1.0, abs_tol=1e-3)
        assert max(start_data["initial_belief"]) < 0.75
        assert start_data["abductive_reasoning"]["surprising_fact_C"]
        assert start_data["abductive_reasoning"]["hypothesis_A"]
        assert "kubernetes" in start_data["question"]  # Bridged from Context Anchor A_ctx!

        # -------------------------------------------------------------------
        # 2. Turn 1 Response on 'terraform': MODERATE_SHIFT (k=1)
        #    Does NOT finish 'terraform' because Turn-1 gate requires DECISIVE_SHIFT + P>=0.75
        # -------------------------------------------------------------------
        r1 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": session_id,
                "candidate_response": (
                    "[MODERATE] Tôi đã viết các module Terraform cơ bản để dựng VPC, EC2 "
                    "và chia biến môi trường dev/staging cho dự án nội bộ."
                ),
            },
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["turn"] == 1
        assert d1["evaluated_skill_id"] == "terraform"
        assert d1["metamorphic_tag"] == "MODERATE_SHIFT"
        assert d1["tv_delta"] <= DELTA_BOUNDS["MODERATE_SHIFT"] + 1e-4
        assert d1["skill_verified"] is False
        # Still on 'terraform' for local turn k=2 (with a newly created probing sub-slot)
        assert d1["active_skill_id"] == "terraform"
        assert d1["next_question"] is not None
        assert d1["completion_rate"] == 0.0
        assert d1["is_finished"] is False

        # Verify that 1 active sub-slot was created for 'terraform' at k=2
        internal_state = client.app.state.session_store[session_id]
        assert len(internal_state.skills["terraform"].active_sub_slots) == 1

        # -------------------------------------------------------------------
        # 3. Turn 2 Response on 'terraform': INVARIANT (k=2)
        #    Verbatim/buzzword answer -> TV_delta == 0.0, does NOT trigger convergence!
        # -------------------------------------------------------------------
        r2 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": session_id,
                "candidate_response": "[INVARIANT] Tôi rất giỏi buzzword IaC cloud native.",
            },
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["turn"] == 2
        assert d2["evaluated_skill_id"] == "terraform"
        assert d2["metamorphic_tag"] == "INVARIANT"
        assert d2["tv_delta"] == 0.0
        assert d2["previous_belief"] == d2["updated_belief"]
        assert d2["skill_verified"] is False
        # Advances to local turn k=3 on 'terraform'
        assert d2["active_skill_id"] == "terraform"
        assert d2["next_question"] is not None

        # -------------------------------------------------------------------
        # 4. Turn 3 Response on 'terraform': DECISIVE_SHIFT (k=3)
        #    Completes 'terraform', triggers Sub-slot GC + 1-Line Consolidation into A_ctx,
        #    and transitions to next skill 'linux' (k=1)!
        # -------------------------------------------------------------------
        r3 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": session_id,
                "candidate_response": (
                    "[DECISIVE] Khi quản lý statefile trên S3 + DynamoDB bị lock do CI/CD crash, "
                    "tôi đã kiểm tra LockID, đối chiếu state serial, dùng terraform force-unlock "
                    "an toàn và tách state monolith thành micro-stacks để đạt zero-downtime."
                ),
            },
        )
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["turn"] == 3
        assert d3["evaluated_skill_id"] == "terraform"
        assert d3["metamorphic_tag"] == "DECISIVE_SHIFT"
        assert d3["tv_delta"] <= DELTA_BOUNDS["DECISIVE_SHIFT"] + 1e-4
        assert d3["skill_verified"] is True
        assert d3["completion_rate"] == 0.5  # 1 of 2 primary skills verified

        # Verify Sub-slot Garbage Collection purged active_sub_slots on 'terraform'
        assert len(internal_state.skills["terraform"].active_sub_slots) == 0
        assert len(internal_state.skills["terraform"].archived_sub_slots) >= 1

        # Next active skill is 'linux', and next_question bridges from 'terraform' consolidated memory
        assert d3["active_skill_id"] == "linux"
        assert d3["next_question"] is not None
        assert "terraform" in d3["next_question"].lower()
        assert d3["is_finished"] is False

        # -------------------------------------------------------------------
        # 5. Turn 4 Response on 'linux': DECISIVE_SHIFT at k=1 -> Verifies & Terminates Session
        # -------------------------------------------------------------------
        # First boost or test decisive convergence: on k=1, if we answer with DECISIVE_SHIFT,
        # let's check if it either verifies at k=1 (if max P_t >= 0.75) or continues to k=2.
        # Note: For linux (s_cv=2.2), B_0 = [0.4705, 0.3886, 0.1409].
        # After 1 DECISIVE_SHIFT (+0.45 toward High), P_1(High) = 0.1409 + 0.45 = 0.5909 (< 0.75).
        # After a 2nd DECISIVE_SHIFT at k=2, P_2(High) > 0.75 -> VERIFIED!
        r4 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": session_id,
                "candidate_response": (
                    "[DECISIVE] Tôi đã trực tiếp dùng strace, tcpdump, ebpf và phân tích kernel "
                    "cgroup oom-killer qua journalctl để xử lý sự cố nghẽn I/O trên hệ thống production."
                ),
            },
        )
        assert r4.status_code == 200
        d4 = r4.json()
        assert d4["evaluated_skill_id"] == "linux"
        assert d4["metamorphic_tag"] == "DECISIVE_SHIFT"
        assert d4["skill_verified"] is False  # P_1(High) ~ 0.59 < 0.75, so asks 1 follow-up at k=2
        assert d4["active_skill_id"] == "linux"

        r5 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": session_id,
                "candidate_response": (
                    "[DECISIVE] Để xử lý triệt để, tôi tinh chỉnh sysctl vm.overcommit_memory, "
                    "thiết lập systemd slice cgroup v2 memory.high/memory.max và giám sát qua Prometheus node_exporter."
                ),
            },
        )
        assert r5.status_code == 200
        d5 = r5.json()
        assert d5["turn"] == 5
        assert d5["evaluated_skill_id"] == "linux"
        assert d5["metamorphic_tag"] == "DECISIVE_SHIFT"
        assert d5["skill_verified"] is True
        assert d5["completion_rate"] == 1.0
        assert d5["is_finished"] is True
        assert d5["active_skill_id"] is None
        assert d5["next_question"] is None

        # -------------------------------------------------------------------
        # 6. Fetch Auditable HITL Report (GET /api/v1/interview/report/{session_id})
        # -------------------------------------------------------------------
        rep_resp = client.get(f"/api/v1/interview/report/{session_id}")
        assert rep_resp.status_code == 200
        report = rep_resp.json()

        assert report["session_id"] == session_id
        assert report["is_finished"] is True
        assert report["total_turns"] == 5
        assert report["total_initial_primary_skills"] == 2
        assert report["verified_primary_skills"] == 2
        assert report["completion_rate"] == 1.0
        assert len(report["evaluated_skills"]) == 2
        assert len(report["turn_audit_trail"]) == 5

        # Check evaluated skill metrics for 'linux'
        linux_report = next(
            item for item in report["evaluated_skills"] if item["jd_skill_id"] == "linux"
        )
        assert linux_report["initial_cv_proficiency"] == 2.2
        assert linux_report["verified_proficiency"] > 3.8  # Converged to High!
        assert linux_report["map_rubric_level"] == "High"
        assert linux_report["is_verified"] is True
        assert len(linux_report["belief_trajectory"]) == 3  # B_0, B_1, B_2

        # Check consolidated context anchors (1 initial 'kubernetes' + 2 verified skills)
        assert len(report["consolidated_context_anchors"]) == 3
        assert "`terraform`" in report["markdown_summary"]
        assert "`linux`" in report["markdown_summary"]
        assert "|---" in report["markdown_summary"]

    def test_turn1_decisive_low_immediate_convergence_and_wrapper_payload(
        self, client: TestClient, mock_skill_gaps
    ):
        """
        Verify that when a candidate explicitly admits lacking a skill at k=1 ([DECISIVE_LOW]),
        P_1(Low) jumps from ~0.45 to ~0.90 (>= 0.75) with DECISIVE_SHIFT, triggering
        Condition 1 immediate Turn-1 convergence!
        """
        start_resp = client.post(
            "/api/v1/interview/start",
            json={"skills": mock_skill_gaps},
        )
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        # Candidate admits lacking Terraform on k=1
        r1 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": session_id,
                "candidate_response": "[DECISIVE_LOW] Thực sự em chưa từng làm Terraform trong thực tế.",
            },
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["evaluated_skill_id"] == "terraform"
        assert d1["metamorphic_tag"] == "DECISIVE_SHIFT"
        assert d1["updated_belief"][0] >= 0.75  # P_1(Low) >= 0.75
        assert d1["skill_verified"] is True  # Immediately verified at k=1!
        assert d1["active_skill_id"] == "linux"
        assert d1["completion_rate"] == 0.5
        assert d1["is_finished"] is False

    def test_error_handling_404_and_finished_session_400(
        self, client: TestClient, mock_skill_gaps
    ):
        # 404 on unknown session
        resp_404 = client.get("/api/v1/interview/report/non-existent-session")
        assert resp_404.status_code == 404

        # Start session with D=0 (only NONE strategy skills)
        only_none = [mock_skill_gaps[0]]
        start_resp = client.post("/api/v1/interview/start", json=only_none)
        assert start_resp.status_code == 200
        s_data = start_resp.json()
        assert s_data["is_finished"] is True
        assert s_data["question"] is None

        # Responding to an already-finished session returns 400
        resp_400 = client.post(
            "/api/v1/interview/respond",
            json={
                "session_id": s_data["session_id"],
                "candidate_response": "Any answer",
            },
        )
        assert resp_400.status_code == 400

    def test_langgraph_and_dspy_direct_integration(self, client: TestClient):
        """
        Verify that workflow uses a compiled LangGraph StateGraph (CompiledStateGraph)
        and that Step 2A / Step 2B signatures & modules inherit directly from dspy.Signature & dspy.Module.
        """
        workflow = client.app.state.workflow
        assert isinstance(workflow.graph, CompiledStateGraph)
        node_names = set(workflow.graph.nodes.keys())
        assert "step2b_reflective_judge" in node_names
        assert "phase3_convergence_router" in node_names
        assert "step2a_question_generator" in node_names

        assert issubclass(Step2AAbductiveQuestionSignature, dspy.Signature)
        assert issubclass(Step2BReflectivePBAJudgeSignature, dspy.Signature)
        assert isinstance(workflow.engine.dspy_question_module, dspy.Module)
        assert isinstance(workflow.engine.dspy_judge_module, dspy.Module)
        assert isinstance(workflow.engine.dspy_question_module, DSPyQuestionGeneratorModule)
        assert isinstance(workflow.engine.dspy_judge_module, DSPyReflectiveJudgeModule)



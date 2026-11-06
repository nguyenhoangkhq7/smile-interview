"""
Unit tests for Stage 2: Phase 1 Initialization, Dual-Anchor Convergence Router,
Turn-1 Gate, Local Skill Completion Conditions (1, 2, 3), 1-Line Memory Consolidation,
Sub-slot Garbage Collection, and 80% Global Termination Rule.
"""

import pytest

from adaptive_questioning.core.router import (
    check_global_termination,
    check_local_skill_completion,
    compute_completion_rate,
    consolidate_and_garbage_collect,
    initialize_session_state,
)
from adaptive_questioning.schemas.skill_gap_input import QuestionStrategyType, SkillGapInput
from adaptive_questioning.schemas.state import MetamorphicTag, SubSlot


def _sample_skill_inputs():
    return [
        SkillGapInput(
            jd_skill_id="kubernetes",
            matched_cv_skill_id="kubernetes",
            semantic_alignment="MATCH",
            is_substituted=False,
            required_proficiency=4.0,
            candidate_proficiency=4.5,
            gap_magnitude=0.0,
            priority=0.0,
            suggested_strategy=QuestionStrategyType.NONE,
            cv_evidence_spans=[],
            context_job="DevOps Lead (03/2024 - Hiện tại)",
        ),
        SkillGapInput(
            jd_skill_id="linux",
            matched_cv_skill_id="linux",
            semantic_alignment="MATCH",
            is_substituted=False,
            required_proficiency=4.0,
            candidate_proficiency=2.2,
            gap_magnitude=0.45,
            priority=0.09,
            suggested_strategy=QuestionStrategyType.PROBE_DEPTH,
            cv_evidence_spans=["Hỗ trợ quản trị server Linux cơ bản."],
            context_job="Junior Sysadmin (01/2017 - 05/2019)",
        ),
        SkillGapInput(
            jd_skill_id="terraform",
            matched_cv_skill_id="cloudformation",
            semantic_alignment="PARTIAL",
            is_substituted=True,
            required_proficiency=4.0,
            candidate_proficiency=2.5,
            gap_magnitude=0.38,
            priority=0.25,
            suggested_strategy=QuestionStrategyType.COMPARE_SUBSTITUTE,
            cv_evidence_spans=["Triển khai hạ tầng AWS bằng CloudFormation."],
            context_job="Cloud Engineer (06/2021 - 02/2024)",
        ),
    ]


class TestPhase1Initialization:
    """Verify Primary Queue filtering, sorting, Context Anchor preservation, and D=0 edge case."""

    def test_primary_queue_sorting_and_context_anchors(self):
        state = initialize_session_state(_sample_skill_inputs(), session_id="test-init")
        assert state.total_initial_d == 2
        assert state.d_verified == 0
        # Sorted by priority descending: terraform (0.25) -> linux (0.09)
        assert state.primary_queue == ["terraform", "linux"]
        assert state.active_skill_id == "terraform"
        assert not state.is_finished
        # Context Anchor preserved for kubernetes (strategy == NONE)
        assert len(state.context_anchors) == 1
        assert state.context_anchors[0].jd_skill_id == "kubernetes"
        assert state.context_anchors[0].source == "INITIAL_NONE"

    def test_zero_primary_skills_edge_case(self):
        only_none = [_sample_skill_inputs()[0]]
        state = initialize_session_state(only_none, session_id="test-d0")
        assert state.total_initial_d == 0
        assert state.primary_queue == []
        assert state.active_skill_id is None
        assert state.is_finished is True
        assert state.termination_reason == "NO_PRIMARY_SKILLS_TO_PROBE"
        assert compute_completion_rate(state) == 1.0


class TestLocalSkillCompletionConditions:
    """Verify Turn-1 Gate and Conditions 1, 2, and 3 for Local Skill Completion."""

    def test_turn1_gate_blocks_non_decisive_shift_even_with_high_prob(self):
        """At k = 1, MODERATE_SHIFT must NOT trigger Condition 1 even if max P_t >= 0.75."""
        verified, reason = check_local_skill_completion(
            local_turn_k=1,
            tag=MetamorphicTag.MODERATE_SHIFT,
            p_t=[0.05, 0.15, 0.80],
            tv_delta=0.25,
            active_sub_slots=[],
        )
        assert verified is False
        assert reason is None

    def test_turn1_gate_allows_decisive_shift_when_prob_ge_075(self):
        """At k = 1, DECISIVE_SHIFT with max P_t >= 0.75 triggers Condition 1."""
        verified, reason = check_local_skill_completion(
            local_turn_k=1,
            tag=MetamorphicTag.DECISIVE_SHIFT,
            p_t=[0.05, 0.15, 0.80],
            tv_delta=0.45,
            active_sub_slots=[],
        )
        assert verified is True
        assert reason == "CONDITION_1_TURN1_DECISIVE_CONVERGENCE"

    def test_turn2_blocks_invariant_even_when_tv_delta_is_zero(self):
        """At k >= 2, INVARIANT has TV_delta = 0.0 <= 0.03, but must NOT trigger convergence!"""
        verified, reason = check_local_skill_completion(
            local_turn_k=2,
            tag=MetamorphicTag.INVARIANT,
            p_t=[0.30, 0.50, 0.20],
            tv_delta=0.0,
            active_sub_slots=[],
        )
        assert verified is False
        assert reason is None

    def test_turn2_converges_on_small_tv_delta_for_non_invariant(self):
        """At k >= 2, MINOR_SHIFT with TV_delta <= 0.03 triggers Condition 1."""
        verified, reason = check_local_skill_completion(
            local_turn_k=2,
            tag=MetamorphicTag.MINOR_SHIFT,
            p_t=[0.20, 0.55, 0.25],
            tv_delta=0.02,
            active_sub_slots=[],
        )
        assert verified is True
        assert reason == "CONDITION_1_BELIEF_CONVERGENCE"

    def test_condition2_sub_slots_saturated(self):
        """Condition 2 triggers when both 2 probing sub-slots are created and filled."""
        sub_slots = [
            SubSlot(
                slot_id="linux:sub_1",
                slot_name="systemd_debugging",
                description="Probe systemd",
                value="Used journalctl -xe",
                filled=True,
            ),
            SubSlot(
                slot_id="linux:sub_2",
                slot_name="cgroup_limits",
                description="Probe cgroups",
                value="Configured memory.max",
                filled=True,
            ),
        ]
        verified, reason = check_local_skill_completion(
            local_turn_k=2,
            tag=MetamorphicTag.MODERATE_SHIFT,
            p_t=[0.20, 0.50, 0.30],
            tv_delta=0.15,
            active_sub_slots=sub_slots,
        )
        assert verified is True
        assert reason == "CONDITION_2_SUB_SLOTS_SATURATED"

    def test_condition3_local_turn_cap_k_max_3(self):
        """Condition 3 triggers when local_turn_k reaches k_max = 3 even if belief hasn't converged."""
        verified, reason = check_local_skill_completion(
            local_turn_k=3,
            tag=MetamorphicTag.INVARIANT,
            p_t=[0.35, 0.45, 0.20],
            tv_delta=0.0,
            active_sub_slots=[],
        )
        assert verified is True
        assert reason == "CONDITION_3_LOCAL_TURN_CAP"


class TestConsolidationGarbageCollectionAndGlobalStop:
    """Verify 1-Line Memory Consolidation, Sub-slot GC, and 80% Global Stop."""

    def test_consolidation_and_sub_slot_gc(self):
        state = initialize_session_state(_sample_skill_inputs())
        terraform_skill = state.skills["terraform"]
        terraform_skill.active_sub_slots.append(
            SubSlot(
                slot_id="terraform:sub_1",
                slot_name="state_locking",
                description="DynamoDB state lock",
                value="Configured S3 + DynamoDB lock",
                filled=True,
            )
        )

        consolidate_and_garbage_collect(
            session=state,
            skill=terraform_skill,
            consolidated_summary="Ứng viên nắm vững cơ chế quản lý state trong Terraform.",
            verification_reason="CONDITION_1_BELIEF_CONVERGENCE",
        )

        # Active sub-slots purged by GC, archived sub-slots preserved for Phase 4 report
        assert len(terraform_skill.active_sub_slots) == 0
        assert len(terraform_skill.archived_sub_slots) == 1
        assert terraform_skill.is_verified is True

        # 1-Line summary appended to A_ctx
        assert len(state.context_anchors) == 2
        assert state.context_anchors[-1].jd_skill_id == "terraform"
        assert state.context_anchors[-1].source == "VERIFIED_CONSOLIDATION"
        assert "state trong Terraform" in state.context_anchors[-1].consolidated_summary

        # Queue popped and pointer advanced to linux
        assert state.d_verified == 1
        assert state.primary_queue == ["linux"]
        assert state.active_skill_id == "linux"

    def test_global_80_percent_termination_rule(self):
        """When 4 out of 5 primary skills are verified (4/5 = 0.80), session terminates immediately."""
        five_skills = [
            SkillGapInput(
                jd_skill_id=f"skill_{i}",
                matched_cv_skill_id=f"skill_{i}",
                required_proficiency=4.0,
                candidate_proficiency=2.0,
                gap_magnitude=0.5,
                priority=0.5 - i * 0.05,
                suggested_strategy=QuestionStrategyType.PROBE_DEPTH,
            )
            for i in range(5)
        ]
        state = initialize_session_state(five_skills)
        assert state.total_initial_d == 5

        # Verify first 4 skills
        for i in range(4):
            sid = f"skill_{i}"
            consolidate_and_garbage_collect(state, state.skills[sid], f"Verified {sid}")

        assert state.d_verified == 4
        assert compute_completion_rate(state) == 0.80
        # 5th skill is still in primary_queue, but 4/5 >= 0.80 triggers global stop!
        assert state.primary_queue == ["skill_4"]
        terminated, reason = check_global_termination(state)
        assert terminated is True
        assert reason == "GLOBAL_COMPLETION_THRESHOLD_80_PERCENT"
        assert state.is_finished is True
        assert state.active_skill_id is None

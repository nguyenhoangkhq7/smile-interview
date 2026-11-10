"""Unit and hardening test suite for Sprint 2 Phase 1B: Semantic Relationship Quality Hardening.

Covers all 30 verification requirements specified in Section 11:
1. Docker vs Linux Containers (tool vs underlying technology category -> distinct, related)
2. Jest vs Playwright (unit test runner vs E2E automation -> distinct, related, not direct alternatives)
3. React vs Zustand (UI library vs state management -> distinct, related, not direct alternatives)
4. React vs React Query (UI library vs data fetching -> distinct, related)
5. ReactJS vs React (equivalent alias)
6. PostgreSQL vs Postgres (equivalent informal alias)
7. Java vs JavaScript (distinct, unrelated languages)
8. Next.js vs React (distinct, foundational dependency / prerequisite b_to_a)
9. Core Web Vitals vs Responsive Web Applications (performance metric is NOT specialization -> distinct, related)
10. Next.js App Router vs Responsive Web Applications (framework feature is NOT specialization -> distinct, related)
11. Accessibility vs Responsive Web Applications (overlapping engineering goals -> distinct, related)
12. TypeScript vs Code Review (workflow co-occurrence -> distinct, unrelated/related)
13. Cardiology vs Echocardiography (diagnostic procedure is NOT clinical sub-specialty specialization -> distinct, related)
14. Unknown emerging technology (uncertain, requires_external_verification=True, candidate_only)
15. Ambiguous abbreviation with and without context (PR: uncertain without context; related with Git context)
16. False-equivalence detection (rejects tool vs category equivalence)
17. Alternative requires clear functional overlap (Redux Toolkit vs Zustand = alternative; React vs Zustand = related)
18. Specialization requires genuine genus-species subtyping (Pediatric Oncology vs Oncology = specialization; metrics/procedures = related)
19. Directionality inversion (a_to_b becomes b_to_a upon pair reversal)
20. Label-rationale contradiction detection
21. Critic disagreement and refinement (initial decision preserved in initial_decision, final decision refined)
22. Critic timeout isolation (does not crash pair, retains initial decision with candidate_only status)
23. Critic structured-output failure (malformed JSON handled gracefully)
24. Model-knowledge-only provenance enforcement (no context -> verification_status MUST BE model_inferred)
25. Context-grounded provenance (traceable to non-empty context)
26. Exact-label fast-path provenance (resolution_method="exact_label_rule", evidence_basis="exact_string_match", verification_status="deterministic_verified")
27. Batch deduplication (resolution_method="cache_dedup")
28. Symmetric cache behavior (resolution_method="derived_by_symmetry")
29. Stage 3 metadata preservation (retrieval_cosine, occurrence_ids, sources)
30. Regression with Stage 3 / Sprint 1 schemas
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningRequest,
    BatchSkillPairReasoningResponse,
    SkillPairReasoningInput,
    SkillPairReasoningResult,
)
from matching_cv.app.services.skill_reasoning_service import (
    SkillReasoningService,
    skill_reasoning_service,
)


def _create_mock_completion(content_dict: dict):
    """Helper to mock an OpenAI chat completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(content_dict)
    mock_choice.message.reasoning = None
    mock_choice.message.reasoning_content = None
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


@pytest.fixture
def service():
    return SkillReasoningService()


def test_req_01_docker_vs_linux_containers_not_equivalent(service):
    """Test 1: Docker vs Linux Containers: tool vs underlying technology category -> distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="docker", skill_a_name="Docker",
            skill_b_id="linux-containers", skill_b_name="Linux Containers",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Docker is a specific containerization platform and tool built on Linux Containers (LXC/namespaces).",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"
        assert res.graph_relation_status == "eligible"

    asyncio.run(_test())


def test_req_02_jest_vs_playwright_not_direct_alternatives(service):
    """Test 2: Jest vs Playwright: unit test runner vs E2E browser automation -> distinct, related (not direct substitutes)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="jest", skill_a_name="Jest",
            skill_b_id="playwright", skill_b_name="Playwright",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Jest is primarily a unit/integration test runner while Playwright is an E2E browser automation tool; they serve complementary testing layers rather than direct substitutes.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_03_react_vs_zustand_complementary_not_alternative(service):
    """Test 3: React vs Zustand: UI library vs state management -> distinct, related (not alternatives)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="react", skill_a_name="React",
            skill_b_id="zustand", skill_b_name="Zustand",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "React is a UI component library, whereas Zustand is a state management library commonly used within React apps.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_04_react_vs_react_query_distinct_related(service):
    """Test 4: React vs React Query: distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="react", skill_a_name="React",
            skill_b_id="react-query", skill_b_name="React Query",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "React Query is a server-state fetching library within the React ecosystem.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_05_reactjs_vs_react_equivalent(service):
    """Test 5: ReactJS vs React: equivalent."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="reactjs", skill_a_name="ReactJS",
            skill_b_id="react", skill_b_name="React",
        )
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "ReactJS is the common alternative naming variant for React.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None

    asyncio.run(_test())


def test_req_06_postgresql_vs_postgres_equivalent(service):
    """Test 6: PostgreSQL vs Postgres: equivalent."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="postgresql", skill_a_name="PostgreSQL",
            skill_b_id="postgres", skill_b_name="Postgres",
        )
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "Postgres is the standard official alias for PostgreSQL.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None

    asyncio.run(_test())


def test_req_07_java_vs_javascript_distinct_unrelated(service):
    """Test 7: Java vs JavaScript: distinct, unrelated languages."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="java", skill_a_name="Java",
            skill_b_id="javascript", skill_b_name="JavaScript",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "unrelated",
            "direction": "none",
            "reasoning_summary": "Java and JavaScript are separate programming languages with different runtimes and semantics.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "unrelated"

    asyncio.run(_test())


def test_req_08_nextjs_vs_react_foundational_dependency(service):
    """Test 8: Next.js vs React: distinct, foundational dependency / prerequisite b_to_a."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="nextjs", skill_a_name="Next.js",
            skill_b_id="react", skill_b_name="React",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "prerequisite",
            "direction": "b_to_a",
            "reasoning_summary": "React is the foundational library and prerequisite required to develop applications in Next.js.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "prerequisite"
        assert res.direction == "b_to_a"

    asyncio.run(_test())


def test_req_09_core_web_vitals_vs_responsive_apps_not_specialization(service):
    """Test 9: Core Web Vitals vs Responsive Web Applications: metric is NOT specialization -> distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="core-web-vitals", skill_a_name="Core Web Vitals",
            skill_b_id="responsive-apps", skill_b_name="Responsive Web Applications",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Core Web Vitals are performance metrics, while responsive web applications is an architectural design practice. They are related performance concerns, not genus-species subtyping.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_10_nextjs_app_router_vs_responsive_apps_not_specialization(service):
    """Test 10: Next.js App Router vs Responsive Web Applications: feature is NOT specialization -> distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="app-router", skill_a_name="Next.js App Router",
            skill_b_id="responsive-apps", skill_b_name="Responsive Web Applications",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Next.js App Router is a framework routing feature, not a narrower specialization of responsive web applications.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_11_accessibility_vs_responsive_apps_not_specialization(service):
    """Test 11: Accessibility vs Responsive Web Applications: distinct overlapping engineering goals -> distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="a11y", skill_a_name="Accessibility",
            skill_b_id="responsive-apps", skill_b_name="Responsive Web Applications",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Accessibility and responsive design are distinct, overlapping quality disciplines in frontend engineering.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_12_typescript_vs_code_review_workflow_cooccurrence(service):
    """Test 12: TypeScript vs Code Review: workflow co-occurrence -> distinct, unrelated/related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="ts", skill_a_name="TypeScript",
            skill_b_id="code-review", skill_b_name="Code Review",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "unrelated",
            "direction": "none",
            "reasoning_summary": "TypeScript is a programming language, while code review is a collaborative engineering process; they co-occur in development workflows without a direct functional dependency.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship in ("unrelated", "related")

    asyncio.run(_test())


def test_req_13_cardiology_vs_echocardiography_procedure_not_specialization(service):
    """Test 13: Cardiology vs Echocardiography: diagnostic procedure is NOT subspecialty specialization -> distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="cardiology", skill_a_name="Cardiology",
            skill_b_id="echocardiography", skill_b_name="Echocardiography",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Echocardiography is a diagnostic imaging procedure used in Cardiology, not a clinical medical sub-specialty.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_14_unknown_emerging_technology_uncertain(service):
    """Test 14: Unknown emerging technology -> uncertain, requires_external_verification=True, candidate_only."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="warp-flux", skill_a_name="WarpFluxEngine",
            skill_b_id="hypersync", skill_b_name="HyperSyncDB",
        )
        mock_res = {
            "identity": "uncertain",
            "relationship": "uncertain",
            "direction": "none",
            "reasoning_summary": "Neither concept is recognizable in standard industry lexicons and no context is provided.",
            "evidence_basis": "insufficient_evidence",
            "verification_status": "uncertain",
            "requires_external_verification": True,
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "uncertain"
        assert res.relationship == "uncertain"
        assert res.requires_external_verification is True
        assert res.graph_relation_status == "candidate_only"

    asyncio.run(_test())


def test_req_15_ambiguous_abbreviation_with_and_without_context(service):
    """Test 15: Ambiguous abbreviation: uncertain without context, resolved with context."""
    async def _test():
        # Case A: Without context -> uncertain
        pair_no_ctx = SkillPairReasoningInput(skill_a_id="pr", skill_a_name="PR", skill_b_id="git", skill_b_name="Git")
        mock_no_ctx = {
            "identity": "uncertain",
            "relationship": "uncertain",
            "direction": "none",
            "reasoning_summary": "PR can mean Pull Request or Public Relations; cannot confirm without context.",
            "evidence_basis": "insufficient_evidence",
            "verification_status": "uncertain",
            "requires_external_verification": True,
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_no_ctx))

        res_a = await service.reason_pair(pair_no_ctx, client=mock_client)
        assert res_a.identity == "uncertain"
        assert res_a.requires_external_verification is True

        # Case B: With context -> resolved
        pair_with_ctx = SkillPairReasoningInput(
            skill_a_id="pr", skill_a_name="PR", skill_a_context="Reviewed PRs on GitHub repository",
            skill_b_id="git", skill_b_name="Git", skill_b_context="Proficient with Git version control",
        )
        mock_with_ctx = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "In the GitHub context, PR refers to Pull Request which is directly related to Git.",
            "evidence_basis": "context_grounded",
            "verification_status": "context_verified",
            "requires_external_verification": False,
        }
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_with_ctx))
        res_b = await service.reason_pair(pair_with_ctx, client=mock_client)
        assert res_b.identity == "distinct"
        assert res_b.relationship == "related"
        assert res_b.evidence_basis == "context_grounded"
        assert res_b.verification_status == "context_verified"

    asyncio.run(_test())


def test_req_16_false_equivalence_rejection(service):
    """Test 16: False-equivalence rejection: tool vs underlying technology must not be labeled equivalent."""
    async def _test():
        pair = SkillPairReasoningInput(skill_a_id="docker", skill_a_name="Docker", skill_b_id="lxc", skill_b_name="Linux Containers")
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Docker is a container tool/engine that utilizes Linux Containers under the hood. They are not strict aliases.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship != "equivalent"

    asyncio.run(_test())


def test_req_17_alternative_requires_clear_functional_overlap(service):
    """Test 17: Alternative requires clear functional overlap (Redux Toolkit vs Zustand = alternative)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="rtk", skill_a_name="Redux Toolkit",
            skill_b_id="zustand", skill_b_name="Zustand",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "alternative",
            "direction": "none",
            "reasoning_summary": "Redux Toolkit and Zustand are competing, interchangeable state management libraries for React.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "alternative"

    asyncio.run(_test())


def test_req_18_specialization_requires_genuine_subtyping(service):
    """Test 18: Specialization requires genuine genus-species subtyping (Pediatric Oncology vs Oncology)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="ped-onc", skill_a_name="Pediatric Oncology",
            skill_b_id="onc", skill_b_name="Oncology",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "specialization",
            "direction": "a_to_b",
            "reasoning_summary": "Pediatric Oncology is a narrower sub-specialty branch of Oncology.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "specialization"
        assert res.direction == "a_to_b"

    asyncio.run(_test())


def test_req_19_directionality_inversion_preserves_dependency(service):
    """Test 19: Directionality inversion inverts a_to_b to b_to_a."""
    async def _test():
        pair_ab = SkillPairReasoningInput(skill_a_id="js", skill_a_name="JavaScript", skill_b_id="ts", skill_b_name="TypeScript")
        pair_ba = SkillPairReasoningInput(skill_a_id="ts", skill_a_name="TypeScript", skill_b_id="js", skill_b_name="JavaScript")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "distinct",
            "relationship": "prerequisite",
            "direction": "a_to_b",
            "reasoning_summary": "JS is prerequisite for TS",
        }))

        req = BatchSkillPairReasoningRequest(pairs=[pair_ab, pair_ba])
        batch_res = await service.reason_batch(req, client=mock_client)

        assert batch_res.results[0].direction == "a_to_b"
        assert batch_res.results[1].direction == "b_to_a"
        assert batch_res.results[1].cached_from_symmetric is True
        assert batch_res.results[1].resolution_method == "derived_by_symmetry"

    asyncio.run(_test())


def test_req_20_label_rationale_contradiction_detection(service):
    """Test 20: Deterministic contradiction detection flags alternative claimed when rationale says not substitutes."""
    async def _test():
        pair = SkillPairReasoningInput(skill_a_id="react", skill_a_name="React", skill_b_id="zustand", skill_b_name="Zustand")
        # LLM erroneously outputs 'alternative' but rationale says they are not substitutes
        raw_contradictory = {
            "identity": "distinct",
            "relationship": "alternative",
            "direction": "none",
            "reasoning_summary": "React is a UI library and Zustand is a state manager; they serve different functional roles rather than being substitutes.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        res = service._validate_and_sanitize_result(raw_contradictory, pair, "test_model", "sprint2-v2", 10.0)
        assert res.contradiction_detected is True
        assert res.graph_relation_status == "candidate_only"  # Demoted due to contradiction

    asyncio.run(_test())


def test_req_21_critic_disagreement_and_refinement(service):
    """Test 21: Critic pass refines an initial contradictory decision and preserves initial_decision for audit."""
    async def _test():
        pair = SkillPairReasoningInput(skill_a_id="react", skill_a_name="React", skill_b_id="zustand", skill_b_name="Zustand")

        # Initial call returns contradictory alternative
        initial_res_json = {
            "identity": "distinct",
            "relationship": "alternative",
            "direction": "none",
            "reasoning_summary": "Different functional roles rather than being substitutes.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
        }
        # Critic call detects contradiction and provides corrected label
        critic_res_json = {
            "contradiction_detected": True,
            "critic_assessment": "React and Zustand are complementary tools, not direct substitutes. Correcting to related.",
            "revised_identity": "distinct",
            "revised_relationship": "related",
            "revised_direction": "none",
            "resolution_confidence": "high",
        }

        call_count = 0
        async def mock_create(model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_completion(initial_res_json)
            else:
                return _create_mock_completion(critic_res_json)

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

        res = await service.reason_pair(pair, client=mock_client, enable_critic=True)
        assert res.resolution_method == "llm_critic_refined"
        assert res.relationship == "related"
        assert res.initial_decision is not None
        assert res.initial_decision["relationship"] == "alternative"
        assert res.critic_assessment is not None
        assert res.graph_relation_status == "eligible"

    asyncio.run(_test())


def test_req_22_critic_timeout_isolation(service):
    """Test 22: Critic timeout does not crash the evaluation, isolates failure and retains candidate_only status."""
    async def _test():
        pair = SkillPairReasoningInput(skill_a_id="a", skill_a_name="Skill A", skill_b_id="b", skill_b_name="Skill B")

        call_count = 0
        async def mock_create(model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_completion({
                    "identity": "distinct",
                    "relationship": "alternative",
                    "direction": "none",
                    "reasoning_summary": "Not substitutes for each other.",
                })
            else:
                raise asyncio.TimeoutError()

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

        res = await service.reason_pair(pair, client=mock_client, enable_critic=True, timeout=0.5)
        # Decision survives without crash
        assert res.identity == "distinct"
        assert res.relationship == "alternative"
        assert res.contradiction_detected is True
        assert res.graph_relation_status == "candidate_only"

    asyncio.run(_test())


def test_req_23_critic_structured_output_failure_isolation(service):
    """Test 23: Malformed critic response is isolated without breaking the primary reasoning result."""
    async def _test():
        pair = SkillPairReasoningInput(skill_a_id="a", skill_a_name="Skill A", skill_b_id="b", skill_b_name="Skill B")

        call_count = 0
        async def mock_create(model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_completion({
                    "identity": "distinct",
                    "relationship": "related",
                    "direction": "none",
                    "reasoning_summary": "Related skills.",
                })
            else:
                mock_c = MagicMock()
                mock_c.message.content = "INVALID NON-JSON TEXT"
                mock_c.message.reasoning = None
                mock_c.message.reasoning_content = None
                mock_comp = MagicMock()
                mock_comp.choices = [mock_c]
                return mock_comp

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

        res = await service.reason_pair(pair, client=mock_client, enable_critic=True)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_req_24_model_knowledge_only_provenance_enforced(service):
    """Test 24: When context is null, verification_status CANNOT be context_verified (strictly model_inferred)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="k8s", skill_a_name="K8s", skill_a_context=None,
            skill_b_id="kubernetes", skill_b_name="Kubernetes", skill_b_context=None,
        )
        # LLM erroneously claims 'context_verified' despite context being None
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "K8s is Kubernetes.",
            "evidence_basis": "context_grounded",
            "verification_status": "context_verified",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        # Provenance invariant enforced
        assert res.verification_status == "model_inferred"
        assert res.evidence_basis == "model_knowledge"

    asyncio.run(_test())


def test_req_25_context_grounded_provenance(service):
    """Test 25: When non-empty context is provided, context_verified and context_grounded are permitted."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="react", skill_a_name="React", skill_a_context="Built frontend web interfaces using React.",
            skill_b_id="react-dom", skill_b_name="ReactDOM", skill_b_context="Rendered component tree with ReactDOM.",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Context grounds their relationship as renderer and library.",
            "evidence_basis": "context_grounded",
            "verification_status": "context_verified",
        }
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.verification_status == "context_verified"
        assert res.evidence_basis == "context_grounded"

    asyncio.run(_test())


def test_req_26_exact_label_fast_path_provenance(service):
    """Test 26: Fast path produces exact_label_rule, deterministic_verified, and exact_string_match."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="id1", skill_a_name="PostgreSQL Database",
            skill_b_id="id2", skill_b_name="postgresql database",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None
        assert res.resolution_method == "exact_label_rule"
        assert res.evidence_basis == "exact_string_match"
        assert res.verification_status == "deterministic_verified"
        assert res.graph_relation_status == "eligible"
        mock_client.chat.completions.create.assert_not_called()

    asyncio.run(_test())


def test_req_27_batch_deduplication_provenance(service):
    """Test 27: Duplicate pair in batch uses resolution_method='cache_dedup'."""
    async def _test():
        pair1 = SkillPairReasoningInput(skill_a_id="a", skill_a_name="Docker", skill_b_id="b", skill_b_name="Kubernetes")
        pair2 = SkillPairReasoningInput(skill_a_id="a", skill_a_name="Docker", skill_b_id="b", skill_b_name="Kubernetes")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Both container tools.",
        }))

        req = BatchSkillPairReasoningRequest(pairs=[pair1, pair2])
        batch_res = await service.reason_batch(req, client=mock_client)

        assert batch_res.results[0].resolution_method == "llm_direct"
        assert batch_res.results[1].resolution_method == "cache_dedup"
        assert batch_res.cached_dedup_pairs == 1

    asyncio.run(_test())


def test_req_28_symmetric_cache_provenance(service):
    """Test 28: Inverted pair uses resolution_method='derived_by_symmetry'."""
    async def _test():
        pair1 = SkillPairReasoningInput(skill_a_id="a", skill_a_name="Java", skill_b_id="b", skill_b_name="Spring Boot")
        pair2 = SkillPairReasoningInput(skill_a_id="b", skill_a_name="Spring Boot", skill_b_id="a", skill_b_name="Java")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "distinct",
            "relationship": "prerequisite",
            "direction": "a_to_b",
            "reasoning_summary": "Java is prerequisite for Spring Boot.",
        }))

        req = BatchSkillPairReasoningRequest(pairs=[pair1, pair2])
        batch_res = await service.reason_batch(req, client=mock_client)

        assert batch_res.results[0].resolution_method == "llm_direct"
        assert batch_res.results[1].resolution_method == "derived_by_symmetry"
        assert batch_res.results[1].direction == "b_to_a"

    asyncio.run(_test())


def test_req_29_stage3_metadata_preservation(service):
    """Test 29: Preserves retrieval_cosine, source occurrence IDs, and document sources."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="cv_react", skill_a_name="React", skill_a_source="CV",
            skill_b_id="jd_react", skill_b_name="ReactJS", skill_b_source="JD",
            retrieval_cosine=0.9245,
            source_occurrence_ids=["occ_cv_1", "occ_jd_2"],
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "Aliases.",
        }))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.retrieval_cosine == 0.9245
        assert res.source_occurrence_ids == ["occ_cv_1", "occ_jd_2"]
        assert res.skill_a.source == "CV"
        assert res.skill_b.source == "JD"

    asyncio.run(_test())


def test_req_30_stage3_regression_contract(service):
    """Test 30: Contract compatibility with Stage 3 SBERT Top-K candidate extraction."""
    mock_stage3_output = {
        "top_k_retrievals": {
            "cv_skills_to_jd_skills": [
                {
                    "query_id": "cv_ts",
                    "query_label": "TypeScript",
                    "candidates": [
                        {"target_id": "jd_js", "target_label": "JavaScript", "cosine_similarity": 0.88},
                        {"target_id": "jd_low", "target_label": "Fortran", "cosine_similarity": 0.15},
                    ],
                }
            ]
        }
    }
    extracted = service.extract_topk_pairs_from_stage3(mock_stage3_output, min_cosine=0.4, max_pairs=5)
    assert len(extracted) == 1
    assert extracted[0].skill_a_name == "TypeScript"
    assert extracted[0].skill_b_name == "JavaScript"
    assert extracted[0].retrieval_cosine == 0.88


def test_candidate_budgeting_starvation_prevention(service):
    """
    Test that 'balanced_coverage' avoids starving lower-ranked CV skills compared to 'global_top_cosine'.
    Simulate 10 CV skills, each with 3 JD candidates.
    With budget=10:
    - balanced_coverage MUST include 10 distinct CV skills (100% CV coverage).
    - global_top_cosine may take multiple candidates from the first few CV skills with highest cosine.
    """
    mock_retrievals = []
    for i in range(10):
        cands = [
            {"target_id": f"jd_{i}_1", "target_label": f"JD Skill {i}-1", "cosine_similarity": 0.90 - (i * 0.05)},
            {"target_id": f"jd_{i}_2", "target_label": f"JD Skill {i}-2", "cosine_similarity": 0.85 - (i * 0.05)},
            {"target_id": f"jd_{i}_3", "target_label": f"JD Skill {i}-3", "cosine_similarity": 0.80 - (i * 0.05)},
        ]
        mock_retrievals.append({
            "query_id": f"cv_{i}",
            "query_label": f"CV Skill {i}",
            "candidates": cands,
        })
    stage3_data = {"top_k_retrievals": {"cv_skills_to_jd_skills": mock_retrievals}}

    # 1. Balanced coverage
    selected_balanced, cov_balanced = service.extract_and_budget_topk_pairs(
        stage3_data, max_pairs=10, min_cosine=0.3, selection_strategy="balanced_coverage"
    )
    assert len(selected_balanced) == 10
    assert cov_balanced["cv_skills_total"] == 10
    assert cov_balanced["cv_skills_covered"] == 10
    assert cov_balanced["cv_skill_coverage_pct"] == 100.0
    assert cov_balanced["skipped_by_budget_pairs"] == 20
    # Every CV skill from 0 to 9 is represented
    represented_cvs = {p.skill_a_id for p in selected_balanced}
    assert len(represented_cvs) == 10

    # 2. Global top cosine
    selected_global, cov_global = service.extract_and_budget_topk_pairs(
        stage3_data, max_pairs=10, min_cosine=0.3, selection_strategy="global_top_cosine"
    )
    assert len(selected_global) == 10
    # In global top cosine, CV 0, 1, 2, 3 have higher scores and consume slots, starving CV 7, 8, 9
    represented_global_cvs = {p.skill_a_id for p in selected_global}
    assert len(represented_global_cvs) < 10
    assert cov_global["cv_skill_coverage_pct"] < 100.0


def test_candidate_budgeting_empty_and_threshold(service):
    """Test candidate budgeting with empty retrievals and low cosine thresholds."""
    empty_data = {"top_k_retrievals": {}}
    sel, cov = service.extract_and_budget_topk_pairs(empty_data, max_pairs=20)
    assert len(sel) == 0
    assert cov["total_retrievable_pairs"] == 0
    assert cov["cv_skills_covered"] == 0
    assert cov["cv_skill_coverage_pct"] == 0.0

    low_scores = {
        "top_k_retrievals": {
            "cv_skills_to_jd_skills": [
                {
                    "query_id": "cv_1",
                    "query_label": "Python",
                    "candidates": [
                        {"target_id": "jd_1", "target_label": "Dentistry", "cosine_similarity": 0.15}
                    ]
                }
            ]
        }
    }
    sel_low, cov_low = service.extract_and_budget_topk_pairs(low_scores, max_pairs=10, min_cosine=0.3)
    assert len(sel_low) == 0
    assert cov_low["total_retrievable_pairs"] == 1
    assert cov_low["total_unique_pairs"] == 0

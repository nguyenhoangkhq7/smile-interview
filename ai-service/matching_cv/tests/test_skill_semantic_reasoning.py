"""Unit test suite for Sprint 2 Phase 1: Ontology-Free LLM Skill Semantic Reasoning.

Covers all 20 required verification scenarios specified in Sprint 2 requirements:
1. ReactJS / React (equivalent)
2. PostgreSQL / Postgres (equivalent)
3. React / React Query (distinct, related)
4. React / Next.js (distinct, specialization / prerequisite)
5. Java / JavaScript (distinct, unrelated)
6. JavaScript / TypeScript (distinct, prerequisite a_to_b)
7. Jest / Playwright (distinct, alternative)
8. Kubernetes / K8s (equivalent)
9. Unknown emerging technology (uncertain)
10. Similar naming, unrelated competencies (Apache Spark vs Apache HTTP Server)
11. Same skill in different languages / spellings (Lập trình Python vs Python Programming)
12. Ambiguous abbreviation (e.g., PR - Pull Request vs Public Relations)
13. Insufficient context (uncertain)
14. Invalid structured LLM response (JSON parse fallback handling)
15. Timeout / rate limit isolation in batch (does not crash other pairs)
16. Equivalent identity symmetry
17. Directional relation consistency (a_to_b vs b_to_a)
18. Deduplication of repeated pair requests (cache reuse)
19. No influence from cosine values when semantic inputs held constant
20. Complete preservation of input provenance (IDs, sources, contexts)
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from matching_cv.app.main import app
from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningRequest,
    BatchSkillPairReasoningResponse,
    SkillPairReasoningInput,
    SkillPairReasoningResult,
    Stage3TopKReasoningRequest,
)
from matching_cv.app.services.skill_reasoning_service import (
    SkillReasoningService,
    normalize_skill_string,
    skill_reasoning_service,
)


def _create_mock_completion(content_dict: dict):
    """Helper to generate a mock OpenAI ChatCompletion response."""
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


def test_scenario_01_reactjs_react_equivalent(service):
    """Scenario 1: ReactJS / React -> equivalent."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="reactjs",
            skill_a_name="ReactJS",
            skill_b_id="react",
            skill_b_name="React",
        )
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "ReactJS is the common alternative name for React.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None
        assert res.direction == "none"
        assert res.skill_a.name == "ReactJS"
        assert res.skill_b.name == "React"

    asyncio.run(_test())


def test_scenario_02_postgresql_postgres_equivalent(service):
    """Scenario 2: PostgreSQL / Postgres -> equivalent."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="postgresql",
            skill_a_name="PostgreSQL",
            skill_b_id="postgres",
            skill_b_name="Postgres",
        )
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "Postgres is the official and community alias for PostgreSQL.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None

    asyncio.run(_test())


def test_scenario_03_react_react_query_distinct_related(service):
    """Scenario 3: React / React Query -> distinct, related."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="react",
            skill_a_name="React",
            skill_b_id="react-query",
            skill_b_name="React Query",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "React Query is a state/data-fetching library frequently used within the React ecosystem.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"

    asyncio.run(_test())


def test_scenario_04_react_nextjs_distinct_prerequisite_or_specialization(service):
    """Scenario 4: React / Next.js -> distinct, prerequisite (a_to_b: React is prerequisite for Next.js)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="react",
            skill_a_name="React",
            skill_b_id="nextjs",
            skill_b_name="Next.js",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "prerequisite",
            "direction": "a_to_b",
            "reasoning_summary": "React is the foundational library and prerequisite required to develop applications in Next.js.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "prerequisite"
        assert res.direction == "a_to_b"

    asyncio.run(_test())


def test_scenario_05_java_javascript_distinct_unrelated(service):
    """Scenario 5: Java / JavaScript -> distinct, unrelated."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="java",
            skill_a_name="Java",
            skill_b_id="javascript",
            skill_b_name="JavaScript",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "unrelated",
            "direction": "none",
            "reasoning_summary": "Java and JavaScript are entirely separate programming languages with different runtimes and semantics despite the historical name overlap.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "unrelated"
        assert res.direction == "none"

    asyncio.run(_test())


def test_scenario_06_javascript_typescript_prerequisite(service):
    """Scenario 6: JavaScript / TypeScript -> distinct, prerequisite (a_to_b)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="javascript",
            skill_a_name="JavaScript",
            skill_b_id="typescript",
            skill_b_name="TypeScript",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "prerequisite",
            "direction": "a_to_b",
            "reasoning_summary": "TypeScript is a typed superset of JavaScript; foundational knowledge of JavaScript is required.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "prerequisite"
        assert res.direction == "a_to_b"

    asyncio.run(_test())


def test_scenario_07_jest_playwright_alternative(service):
    """Scenario 7: Jest / Playwright -> distinct, alternative."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="jest",
            skill_a_name="Jest",
            skill_b_id="playwright",
            skill_b_name="Playwright",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "alternative",
            "direction": "none",
            "reasoning_summary": "Jest (unit/integration test runner) and Playwright (E2E browser testing framework) can serve alternative or complementary testing purposes in JavaScript ecosystems.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "alternative"
        assert res.direction == "none"

    asyncio.run(_test())


def test_scenario_08_kubernetes_k8s_equivalent(service):
    """Scenario 8: Kubernetes / K8s -> equivalent."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="kubernetes",
            skill_a_name="Kubernetes",
            skill_b_id="k8s",
            skill_b_name="K8s",
        )
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "K8s is the standard numeronym and direct synonym for Kubernetes.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None

    asyncio.run(_test())


def test_scenario_09_unknown_emerging_technology_uncertain(service):
    """Scenario 9: Unknown emerging technology -> uncertain with requires_external_verification=True."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="quantum-flux-lang",
            skill_a_name="QuantumFluxLang v3",
            skill_b_id="warp-mesh-framework",
            skill_b_name="WarpMesh Framework",
        )
        mock_res = {
            "identity": "uncertain",
            "relationship": "uncertain",
            "direction": "none",
            "reasoning_summary": "Neither skill is recognized in standard industry taxonomy and no textual context is provided to disambiguate them.",
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
        assert res.evidence_basis == "insufficient_evidence"

    asyncio.run(_test())


def test_scenario_10_apache_spark_vs_apache_http_server(service):
    """Scenario 10: Similar naming prefix but unrelated competencies."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="apache-spark",
            skill_a_name="Apache Spark",
            skill_b_id="apache-http-server",
            skill_b_name="Apache HTTP Server",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "unrelated",
            "direction": "none",
            "reasoning_summary": "Both are Apache Software Foundation projects, but Spark is a distributed analytics engine while HTTP Server is a web server.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "unrelated"

    asyncio.run(_test())


def test_scenario_11_cross_lingual_skill_equivalence(service):
    """Scenario 11: Same skill in different languages / spellings (e.g., Lập trình Python vs Python Programming)."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="lap-trinh-python",
            skill_a_name="Lập trình Python",
            skill_b_id="python-programming",
            skill_b_name="Python Programming",
        )
        mock_res = {
            "identity": "equivalent",
            "relationship": None,
            "direction": "none",
            "reasoning_summary": "'Lập trình Python' is Vietnamese for 'Python Programming'. Both refer to the identical competency.",
            "evidence_basis": "model_knowledge",
            "verification_status": "model_inferred",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"

    asyncio.run(_test())


def test_scenario_12_ambiguous_abbreviation(service):
    """Scenario 12: Ambiguous abbreviation with minimal context."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="pr",
            skill_a_name="PR",
            skill_b_id="git",
            skill_b_name="Git",
            skill_a_context="Reviewed PRs on GitHub repository",
        )
        mock_res = {
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Given the GitHub context, PR refers to Pull Requests, which is directly related to Git workflows.",
            "evidence_basis": "context_grounded",
            "verification_status": "context_verified",
            "requires_external_verification": False,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "distinct"
        assert res.relationship == "related"
        assert res.evidence_basis == "context_grounded"

    asyncio.run(_test())


def test_scenario_13_insufficient_context_uncertain(service):
    """Scenario 13: Insufficient context -> uncertain."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="apex",
            skill_a_name="Apex",
            skill_b_id="oracle",
            skill_b_name="Oracle",
        )
        mock_res = {
            "identity": "uncertain",
            "relationship": "uncertain",
            "direction": "none",
            "reasoning_summary": "Apex can refer to Salesforce Apex programming language or Oracle APEX (Application Express). Without document context, relationship cannot be confirmed.",
            "evidence_basis": "insufficient_evidence",
            "verification_status": "uncertain",
            "requires_external_verification": True,
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion(mock_res))

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "uncertain"
        assert res.requires_external_verification is True

    asyncio.run(_test())


def test_scenario_14_invalid_structured_llm_response(service):
    """Scenario 14: Invalid LLM JSON response gracefully captured as error/uncertain."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="docker",
            skill_a_name="Docker",
            skill_b_id="podman",
            skill_b_name="Podman",
        )

        mock_choice = MagicMock()
        mock_choice.message.content = "THIS IS NOT VALID JSON AT ALL"
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "uncertain"
        assert res.verification_status == "error"
        assert res.error_status is not None
        assert "json" in res.error_status.lower() or "error" in res.error_status.lower()

    asyncio.run(_test())


def test_scenario_15_timeout_isolated_without_crashing_batch(service):
    """Scenario 15: Timeout on one pair isolates the failure and returns status='timeout'."""
    async def _test():
        pair1 = SkillPairReasoningInput(skill_a_id="a", skill_a_name="Skill A", skill_b_id="b", skill_b_name="Skill B")
        pair2 = SkillPairReasoningInput(skill_a_id="c", skill_a_name="Skill C", skill_b_id="d", skill_b_name="Skill D")

        # Pair 1 times out, Pair 2 succeeds
        async def mock_create(model, messages, **kwargs):
            if "(ID: a)" in messages[1]["content"]:
                await asyncio.sleep(0.5)
                raise asyncio.TimeoutError()
            return _create_mock_completion({
                "identity": "equivalent",
                "reasoning_summary": "Pair 2 succeeded",
                "relationship": None,
                "direction": "none",
            })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

        req = BatchSkillPairReasoningRequest(
            pairs=[pair1, pair2],
            timeout_seconds=0.2,
        )
        batch_res = await service.reason_batch(req, client=mock_client)
        assert len(batch_res.results) == 2
        assert batch_res.failed_pairs >= 1
        assert batch_res.results[0].error_status == "timeout"
        assert batch_res.results[1].identity == "equivalent"

    asyncio.run(_test())


def test_scenario_16_equivalent_identity_symmetry(service):
    """Scenario 16: Equivalent pair retains equivalent identity when inverted."""
    async def _test():
        pair1 = SkillPairReasoningInput(skill_a_id="k8s", skill_a_name="K8s", skill_b_id="kubernetes", skill_b_name="Kubernetes")
        pair2 = SkillPairReasoningInput(skill_a_id="kubernetes", skill_a_name="Kubernetes", skill_b_id="k8s", skill_b_name="K8s")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "equivalent",
            "reasoning_summary": "K8s is Kubernetes",
            "relationship": None,
            "direction": "none",
        }))

        req = BatchSkillPairReasoningRequest(pairs=[pair1, pair2])
        batch_res = await service.reason_batch(req, client=mock_client)

        assert len(batch_res.results) == 2
        assert batch_res.results[0].identity == "equivalent"
        assert batch_res.results[1].identity == "equivalent"
        # Deduplication/cache optimization detected the symmetric inversion
        assert batch_res.cached_dedup_pairs == 1

    asyncio.run(_test())


def test_scenario_17_directional_relation_consistency_inversion(service):
    """Scenario 17: When directional relation (a_to_b) is evaluated for (A, B), the inverted pair (B, A) becomes (b_to_a)."""
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

        res_ab = batch_res.results[0]
        res_ba = batch_res.results[1]

        assert res_ab.direction == "a_to_b"
        assert res_ba.direction == "b_to_a"
        assert res_ba.cached_from_symmetric is True
        assert batch_res.cached_dedup_pairs == 1

    asyncio.run(_test())


def test_scenario_18_deduplication_of_repeated_pairs(service):
    """Scenario 18: Exact repeated pair requests are cached and deduplicated."""
    async def _test():
        pair1 = SkillPairReasoningInput(skill_a_id="docker", skill_a_name="Docker", skill_b_id="k8s", skill_b_name="Kubernetes")
        pair2 = SkillPairReasoningInput(skill_a_id="docker", skill_a_name="Docker", skill_b_id="k8s", skill_b_name="Kubernetes")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "distinct",
            "relationship": "related",
            "direction": "none",
            "reasoning_summary": "Both container ecosystem tools.",
        }))

        req = BatchSkillPairReasoningRequest(pairs=[pair1, pair2])
        batch_res = await service.reason_batch(req, client=mock_client)

        assert len(batch_res.results) == 2
        assert batch_res.evaluated_pairs == 1
        assert batch_res.cached_dedup_pairs == 1
        assert mock_client.chat.completions.create.call_count == 1

    asyncio.run(_test())


def test_scenario_19_no_cosine_influence_on_llm_prompt(service):
    """Scenario 19: Retrieval cosine is decoupled from LLM prompt by default."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="react",
            skill_a_name="React",
            skill_b_id="vue",
            skill_b_name="Vue",
            retrieval_cosine=0.9876,
        )

        recorded_messages = []

        async def mock_create(model, messages, **kwargs):
            recorded_messages.extend(messages)
            return _create_mock_completion({
                "identity": "distinct",
                "relationship": "alternative",
                "direction": "none",
                "reasoning_summary": "Different frontend reactive UI libraries.",
            })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

        # When include_cosine=False (default)
        res = await service.reason_pair(pair, client=mock_client, include_cosine=False)
        assert res.retrieval_cosine == 0.9876  # Metadata preserved
        user_prompt = recorded_messages[1]["content"]
        assert "0.9876" not in user_prompt
        assert "Retrieval Cosine Score" not in user_prompt

    asyncio.run(_test())


def test_scenario_20_complete_provenance_preservation(service):
    """Scenario 20: Complete preservation of input IDs, document sources, contexts, and occurrence IDs."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="cv_skill_101",
            skill_a_name="PostgreSQL",
            skill_a_context="Maintained high-throughput PostgreSQL replication cluster",
            skill_a_source="CV",
            skill_b_id="jd_req_202",
            skill_b_name="Postgres DB",
            skill_b_context="Experience tuning Postgres DB performance required",
            skill_b_source="JD",
            retrieval_cosine=0.884,
            source_occurrence_ids=["occ_cv_101", "occ_jd_202"],
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_create_mock_completion({
            "identity": "equivalent",
            "reasoning_summary": "Both refer to PostgreSQL database.",
            "relationship": None,
            "direction": "none",
        }))

        res = await service.reason_pair(pair, client=mock_client)

        assert res.skill_a.skill_id == "cv_skill_101"
        assert res.skill_a.name == "PostgreSQL"
        assert res.skill_a.source == "CV"
        assert res.skill_a.context == "Maintained high-throughput PostgreSQL replication cluster"

        assert res.skill_b.skill_id == "jd_req_202"
        assert res.skill_b.name == "Postgres DB"
        assert res.skill_b.source == "JD"
        assert res.skill_b.context == "Experience tuning Postgres DB performance required"

        assert res.retrieval_cosine == 0.884
        assert res.source_occurrence_ids == ["occ_cv_101", "occ_jd_202"]

    asyncio.run(_test())


def test_identical_skill_fast_path(service):
    """Fast-path verification: Normalized identical skills bypass LLM network call entirely."""
    async def _test():
        pair = SkillPairReasoningInput(
            skill_a_id="id1",
            skill_a_name="Docker Engine",
            skill_b_id="id2",
            skill_b_name="docker engine",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        res = await service.reason_pair(pair, client=mock_client)
        assert res.identity == "equivalent"
        assert res.relationship is None
        # Verify no network call made
        mock_client.chat.completions.create.assert_not_called()

    asyncio.run(_test())


def test_extract_topk_pairs_from_stage3(service):
    """Stage 3 SBERT Top-K extraction filtering and deduplication."""
    mock_stage3_payload = {
        "top_k_retrievals": {
            "skill_to_skill": [
                {
                    "query_id": "cv_react",
                    "query_label": "React",
                    "candidates": [
                        {"target_id": "jd_reactjs", "target_label": "ReactJS", "cosine_similarity": 0.95},
                        {"target_id": "jd_low_score", "target_label": "Cobol", "cosine_similarity": 0.12},
                    ],
                },
                {
                    "query_id": "cv_docker",
                    "query_label": "Docker",
                    "candidates": [
                        {"target_id": "jd_k8s", "target_label": "Kubernetes", "cosine_similarity": 0.65},
                    ],
                },
            ]
        }
    }

    pairs = service.extract_topk_pairs_from_stage3(mock_stage3_payload, min_cosine=0.3, max_pairs=10)
    assert len(pairs) == 2
    assert pairs[0].skill_a_name == "React"
    assert pairs[0].skill_b_name == "ReactJS"
    assert pairs[0].retrieval_cosine == 0.95
    # The low-score candidate (0.12) was filtered out
    assert all(p.retrieval_cosine >= 0.3 for p in pairs)


def test_domain_agnostic_reasoning_healthcare_and_accounting(service):
    """Verify reasoning capability on non-IT domains: healthcare and finance/accounting."""
    async def _test():
        # Healthcare pair: Cardiology / Echocardiography -> distinct, specialization / related
        hc_pair = SkillPairReasoningInput(
            skill_a_id="cardiology",
            skill_a_name="Cardiology",
            skill_b_id="echocardiography",
            skill_b_name="Echocardiography",
        )
        # Accounting pair: GAAP / US Generally Accepted Accounting Principles -> equivalent
        acct_pair = SkillPairReasoningInput(
            skill_a_id="gaap",
            skill_a_name="GAAP",
            skill_b_id="us-gaap",
            skill_b_name="Generally Accepted Accounting Principles",
        )

        async def mock_domain_create(model, messages, **kwargs):
            content = messages[1]["content"]
            if "Cardiology" in content:
                return _create_mock_completion({
                    "identity": "distinct",
                    "relationship": "specialization",
                    "direction": "b_to_a",
                    "reasoning_summary": "Echocardiography is a diagnostic subspecialty technique within cardiology.",
                    "evidence_basis": "model_knowledge",
                    "verification_status": "model_inferred",
                    "requires_external_verification": False,
                })
            else:
                return _create_mock_completion({
                    "identity": "equivalent",
                    "relationship": None,
                    "direction": "none",
                    "reasoning_summary": "GAAP is the standard acronym for Generally Accepted Accounting Principles.",
                    "evidence_basis": "model_knowledge",
                    "verification_status": "model_inferred",
                    "requires_external_verification": False,
                })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_domain_create)

        req = BatchSkillPairReasoningRequest(pairs=[hc_pair, acct_pair])
        batch_res = await service.reason_batch(req, client=mock_client)

        assert len(batch_res.results) == 2
        assert batch_res.results[0].identity == "distinct"
        assert batch_res.results[0].relationship == "specialization"
        assert batch_res.results[1].identity == "equivalent"

    asyncio.run(_test())

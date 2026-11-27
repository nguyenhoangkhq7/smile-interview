"""Regression tests for grouped alternatives and source-grounded CV deduplication."""

from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse
from matching_cv.app.services.competency_granularity import evaluate_competency_retention
from matching_cv.app.services.requirement_grouping import prepare_pipeline_skills
from matching_cv.app.services.skill_postprocessor import skill_postprocessor


def _doc(side, text, mentions):
    return DocumentUnifiedResult(
        document_type=side, raw_text=text,
        explicit=skill_postprocessor.process_extraction([
            {"mention": name, "kind": kind, "category": category, "sentence": sentence}
            for name, kind, category, sentence in mentions
        ], text=text, document_type=side),
    )


def _tool(name, sentence):
    return name, "skill", "Technology/Tool", sentence


def _pair(cv, cv_mentions, jd, jd_mentions):
    return UnifiedExtractFileResponse(
        run_id="group-regression", status="completed",
        cv=_doc("CV", cv, cv_mentions), jd=_doc("JD", jd, jd_mentions),
    )


def _items(doc):
    return {skill.skill_id: skill for skill in doc.explicit.skills}


def test_backend_groups_alternatives_and_preserves_source_name():
    broker_work = "Built message processing using RabbitMQ."
    cv_certification = "AWS Certified Developer – Associate"
    cv = f"Experience\n{broker_work}\nCertifications\n{cv_certification}"
    brokers = "Experience with at least one message broker (Kafka, RabbitMQ, or similar)."
    certifiers = "AWS or GCP certification."
    jd = f"Requirements\n{brokers}\nNice to have\n{certifiers}"
    original = _pair(cv, [_tool("RabbitMQ", broker_work), (cv_certification, "certification", "Certification", cv_certification)],
                     jd, [_tool("Kafka", brokers), _tool("RabbitMQ", brokers), _tool("AWS", certifiers), _tool("GCP", certifiers)])

    prepared = prepare_pipeline_skills(original, cv, jd)

    assert prepared.jd._requirement_groups == {"message-broker": ("kafka", "rabbitmq"),
                                               "cloud-provider-certification": ("aws", "gcp")}
    assert set(_items(prepared.jd)) == set(prepared.jd._requirement_groups)
    assert _items(prepared.jd)["cloud-provider-certification"].evidences[0].section == "nice_to_have"
    assert _items(prepared.cv)["message-broker"].label == "RabbitMQ"
    assert _items(prepared.cv)["cloud-provider-certification"].label == cv_certification
    assert len(_items(prepared.cv)) == len(_items(original.cv))
    assert "rabbitmq" in _items(original.cv)
    assert prepare_pipeline_skills(prepared, cv, jd).cv.explicit.skills == prepared.cv.explicit.skills


def test_independent_requirement_and_conjunction_remain_separate():
    scripting = "Strong scripting ability in Python or Bash."
    required = "Python is required for maintaining the workflow."
    tools = "Experience with PostgreSQL and MySQL."
    jd = f"Requirements\n• {scripting}\n• {required}\n• {tools}"
    cv = "Skills\nPython"
    original = _pair(cv, [_tool("Python", "Python")], jd, [
        _tool("Python", required), _tool("Bash", scripting), _tool("PostgreSQL", tools), _tool("MySQL", tools),
    ])
    prepared = prepare_pipeline_skills(original, cv, jd)
    assert set(_items(prepared.jd)) == {"scripting-language", "python", "postgresql", "mysql"}
    assert {"python", "scripting-language"} <= _items(prepared.cv).keys()


def test_cloud_provider_use_is_not_a_certification():
    cv = "Experience\nBuilt a service on AWS."
    jd = "Nice to have\nAWS or GCP certification."
    original = _pair(cv, [_tool("AWS", "Built a service on AWS.")], jd, [])
    prepared = prepare_pipeline_skills(original, cv, jd)
    assert "cloud-provider-certification" in _items(prepared.jd)
    assert "cloud-provider-certification" not in _items(prepared.cv)
    assert _items(prepared.cv)["aws"].label == "AWS"


def test_resume_redirect_preserves_generic_match_and_version_evidence():
    work = "Used JUnit 5 to test the service."
    cv = "Experience\n" + work
    jd = "Requirements\nExperience with JUnit."
    original = _pair(cv, [_tool("JUnit 5", work)], jd, [_tool("JUnit", "Experience with JUnit.")])
    prepared = prepare_pipeline_skills(original, cv, jd)
    assert set(_items(prepared.cv)) == {"junit"}
    assert _items(prepared.cv)["junit"].label == "JUnit 5"
    assert _items(prepared.cv)["junit"].evidences[0].sentence == work
    assert all(skill.skill_id != "junit" for skill in prepared.cv._verified_resume_skills)


def test_monolith_context_preserves_architecture_competency():
    migration = "Migrated a module out of the legacy monolith."
    architecture = "Designed monolithic architecture for a small service."
    document = _doc("CV", "Experience\n" + migration + "\n" + architecture, [
        _tool("monolith", migration), _tool("monolithic architecture", architecture),
    ])
    assert "monolith" not in _items(document)
    assert "monolithic-architecture" in _items(document)
    assert not evaluate_competency_retention(label="legacy monolith", side="CV").should_retain


def test_open_options_accept_supported_equivalents_and_singular_payment_evidence():
    migration = "Migrated a legacy payment module to a standalone service."
    broker_work = "Configured NATS for message delivery."
    cv = f"Experience\n• {migration}\n• {broker_work}"
    jd = ("Requirements\nExperience with one message broker (Kafka or similar).\n"
          "Nice to have\nExperience in fintech, payments, or another highly regulated domain.")
    original = _pair(cv, [_tool("NATS", broker_work)], jd, [])
    prepared = prepare_pipeline_skills(original, cv, jd)
    assert _items(prepared.cv)["message-broker"].label == "NATS"
    assert _items(prepared.cv)["regulated-domain-experience"].label == "payment"
    assert prepared.jd._requirement_groups["message-broker"] == ("kafka",)


def test_group_projection_moves_every_alias_of_the_selected_option():
    spark = "Ran Spark over the batch jobs."
    apache_spark = "Maintained the Apache Spark deployment."
    cv = f"Experience\n• {spark}\n• {apache_spark}"
    jd = "Requirements\nBuild Spark or PySpark jobs."
    original = _pair(cv, [_tool("Spark", spark), _tool("Apache Spark", apache_spark)], jd, [])
    prepared = prepare_pipeline_skills(original, cv, jd)
    assert all(skill.skill_id == "spark-processing" for skill in prepared.cv.explicit.skills)
    assert {evidence.sentence for skill in prepared.cv.explicit.skills for evidence in skill.evidences} == {spark, apache_spark}


def test_junit_and_database_indexing_merge_when_citations_have_different_boundaries():
    from matching_cv.app.schemas.implicit_skill_extraction import ImplicitEvidence, ImplicitExtractedSkill
    from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter

    tools = "Testing & tooling: JUnit 5, Mockito, Testcontainers, Maven, Git, Jenkins"
    work = "Used JUnit 5."
    indexing = "Reduced latency through query indexing and Redis caching."
    cv = f"Skills\n• {tools}\nExperience\n• {work}\n• {indexing}"
    req = "Experience with JUnit and indexing."
    jd = f"Requirements\n{req}"
    pair = _pair(cv, [_tool("JUnit 5", tools), _tool("JUnit 5", work), _tool("query indexing", "query indexing and Redis caching.")],
                 jd, [_tool("JUnit", req), _tool("indexing", req)])
    pair.cv.validation.status = "completed"
    pair.cv.validation.accepted_implicit_skills = [ImplicitExtractedSkill(
        skill_id="junit", label="JUnit", evidences=[ImplicitEvidence(inferred_from_raw="JUnit 5, Mockito")],
    )]

    prepared = prepare_pipeline_skills(pair, cv, jd)
    active = ExtractionDataAdapter.extract_active_skills(prepared.cv).active_skills
    assert {item.skill_id for item in active} == {"junit", "indexing"}
    explicit = _items(prepared.cv)
    assert explicit["junit"].label == "JUnit 5"
    assert {item.sentence for item in explicit["junit"].evidences} == {tools, work}
    assert explicit["indexing"].label == "query indexing"
    assert all(item.skill_id not in {"junit-5", "query-indexing"} for item in prepared.cv._verified_resume_skills)
    assert prepare_pipeline_skills(prepared, cv, jd).cv.explicit.skills == prepared.cv.explicit.skills


def test_database_indexing_does_not_absorb_search_indexing_or_query_optimization():
    database = "Improved query indexing for the database."
    search = "Implemented search indexing in Elasticsearch."
    optimize = "Supported query optimization for the catalog."
    cv = f"Experience\n• {database}\n• {search}\n• {optimize}"
    jd = "Requirements\nExperience with indexing."
    pair = _pair(cv, [_tool("indexing", search), _tool("query indexing", database), _tool("query optimization", optimize)],
                 jd, [_tool("indexing", "Experience with indexing.")])
    prepared = prepare_pipeline_skills(pair, cv, jd)
    assert {"indexing", "query-indexing", "query-optimization"} <= _items(prepared.cv).keys()


def test_generic_junit_evidence_does_not_replace_a_required_version():
    cv = "Skills\nJUnit"
    jd = "Requirements\nMust use JUnit 5."
    pair = _pair(cv, [_tool("JUnit", "JUnit")], jd, [_tool("JUnit 5", "Must use JUnit 5.")])
    assert set(_items(prepare_pipeline_skills(pair, cv, jd).cv)) == {"junit"}

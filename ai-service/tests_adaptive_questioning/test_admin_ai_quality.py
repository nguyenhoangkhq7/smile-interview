import json

from app.ai_quality import ReviewInput, ReviewQuestion, review_quality


def test_matching_distinguishes_missing_sources_and_unsupported_quotes():
    result = review_quality(ReviewInput(
        cv="Xây dựng   API bằng JavaScript.",
        skillsJson=json.dumps([
            {"jd_skill_id": "javascript", "semantic_alignment": "MATCH", "cv_evidence_spans": ["Xây dựng API"]},
            {"jd_skill_id": "java", "semantic_alignment": "MATCH", "cv_evidence_spans": ["Java"]},
            {"jd_skill_id": "sql", "semantic_alignment": "MISSING"},
        ]),
        reportJson='{"degraded":true}',
    )).matching

    assert result.total == 3
    assert [(finding.skill, finding.status, finding.code, finding.excerpt) for finding in result.findings] == [
        (None, "REVIEW", "DEGRADED_MATCHING", None),
        ("javascript", "INSUFFICIENT", "SOURCE_MISSING", None),
        ("java", "REVIEW", "QUOTE_NOT_FOUND", "Java"),
        ("java", "INSUFFICIENT", "SOURCE_MISSING", None),
        ("sql", "INSUFFICIENT", "SOURCE_MISSING", None),
    ]


def test_matching_checks_persisted_jd_task_quotes_and_missing_cv_evidence():
    result = review_quality(ReviewInput(
        jd="Vận hành  Kubernetes\ntrên AWS.",
        cv="Đã dùng Docker.",
        skillsJson=json.dumps([
            {"jd_skill_id": "kubernetes", "semantic_alignment": "PARTIAL",
             "job_tasks": [{"evidence_spans": ["Vận hành Kubernetes"]}, {"evidence_spans": ["Azure"]}]},
        ]),
    )).matching

    assert result.total == 1
    assert [(finding.status, finding.code, finding.excerpt) for finding in result.findings] == [
        ("INSUFFICIENT", "QUOTE_MISSING", None),
        ("REVIEW", "QUOTE_NOT_FOUND", "Azure"),
    ]


def test_question_review_reports_missing_code_repetition_and_explicit_quotes():
    result = review_quality(ReviewInput(
        cv="Đã làm việc với Java.",
        jd="Sử dụng SQL.",
        questions=[
            ReviewQuestion(text="Theo CV, bạn ghi “Dùng Kubernetes”. Hãy giải thích đoạn mã sau?", skill="K8s"),
            ReviewQuestion(text="THEO CV, BẠN GHI “DÙNG KUBERNETES”.  HÃY GIẢI THÍCH ĐOẠN MÃ SAU?"),
            ReviewQuestion(text="Theo JD, “Sử dụng SQL”. Bạn sẽ tạo chỉ mục nào? Vì sao?"),
            ReviewQuestion(text="Giả sử hệ thống dùng Kubernetes. Bạn sẽ kiểm tra gì trước?"),
        ],
    )).questions

    assert result.total == 4
    assert {(item.turn, item.code) for item in result.findings} == {
        (1, "MISSING_CODE"), (1, "QUOTE_NOT_FOUND"),
        (2, "MISSING_CODE"), (2, "QUOTE_NOT_FOUND"), (2, "REPEATED_QUESTION"),
        (3, "MULTIPLE_TASKS"),
    }
    assert any(item.turn == 1 and item.skill == "K8s" and item.excerpt == "Dùng Kubernetes" for item in result.findings)


def test_empty_and_old_records_are_reported_as_incomplete():
    result = review_quality(ReviewInput(skillsJson="{", questions=[ReviewQuestion()]))
    assert result.matching.total == 0
    assert result.matching.findings[0].status == "INSUFFICIENT"
    assert result.questions.total == 0
    assert not result.questions.findings

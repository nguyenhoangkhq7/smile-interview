"""Checks for decision boundaries, provenance and partial extraction."""
import unittest
from unittest.mock import AsyncMock

from matching_cv.app.eligibility.models import (
    Education, Experience, GPA, Grade, Observations, Period, Requirements, Study,
)
from matching_cv.app.eligibility.rules import education, experience, grade
from matching_cv.app.eligibility.service import check_eligibility


def role(quote, months=None, **fields):
    return Period(condition_id="C3", type="experience", quote=quote, months=months,
                  relevance="confirmed", scope="role", **fields)


class EligibilityRulesTest(unittest.TestCase):
    def setUp(self):
        self.exp = Experience(type="experience", priority="required", quote="12 months backend",
                              domain="backend", months=12, operator=">=")
        self.gpa = GPA(type="gpa", priority="required", quote="GPA > 3.0/4", operator=">", value=3, scale=4)
        self.study = Education(type="education", priority="required", quote="currently at ABC",
                               school="ABC", status="enrolled")

    def test_gpa_boundary_scale_and_source_numbers(self):
        record = Grade(type="gpa", condition_id="C2", quote="GPA 3,0/4", value=3, scale=4)
        self.assertEqual(grade(self.gpa, [record])[0], "not_met")
        self.assertEqual(grade(self.gpa.model_copy(update={"operator": ">="}), [record])[0], "met")
        for values in ({"scale": None}, {"scale": 10}, {"value": 3.9}):
            self.assertEqual(grade(self.gpa, [record.model_copy(update=values)])[0], "insufficient_evidence")

    def test_education_requires_same_program(self):
        a = Study(type="education", condition_id="C1", quote="ABC 2021", school="ABC", status="graduated")
        b = Study(type="education", condition_id="C1", quote="Current: XYZ", school="XYZ", status="enrolled")
        self.assertEqual(education(self.study, [a, b])[0], "insufficient_evidence")
        self.assertEqual(education(self.study, [b.model_copy(update={"exclusive": True})])[0], "not_met")

    def test_overlaps_and_undated_roles(self):
        roles = [role("first", start="2024-01", end="2024-06"), role("second", start="2024-04", end="2024-09")]
        self.assertEqual(experience(self.exp, roles)[0], "insufficient_evidence")
        self.assertEqual(experience(self.exp, [*roles, role("third", start="2024-10", end="2024-12")])[0], "met")
        self.assertEqual(experience(self.exp, [role("one", 6), role("two", 8)])[0], "insufficient_evidence")
        self.assertEqual(experience(self.exp, [role("one", 6), role("then two", 8, after_quote="one")])[0], "met")

    def test_explicit_total_vs_partial_history(self):
        six = role("6 months", 6)
        self.assertEqual(experience(self.exp, [six])[0], "insufficient_evidence")
        self.assertEqual(experience(self.exp, [six.model_copy(update={"scope": "explicit_domain_total"})])[0], "not_met")


class EligibilityExtractionTest(unittest.IsolatedAsyncioTestCase):
    async def test_discussed_cv_and_jd(self):
        jd = "Only students enrolled at ABC. GPA > 3.0/4. At least 12 months backend."
        cv = "Đang học tại ABC. GPA 2,9/4. Backend 6 tháng. Sau đó phát triển phần mềm 8 tháng."
        conditions = Requirements(conditions=[
            Education(type="education", priority="required", quote="students enrolled at ABC", school="ABC", status="enrolled"),
            GPA(type="gpa", priority="required", quote="GPA > 3.0/4", operator=">", value=3, scale=4),
            Experience(type="experience", priority="required", quote="At least 12 months backend",
                       domain="backend", operator=">=", months=12),
        ])
        observed = Observations(records=[
            Study(type="education", condition_id="C1", quote="Đang học tại ABC", school="ABC", status="enrolled"),
            Grade(type="gpa", condition_id="C2", quote="GPA 2,9/4", value=2.9, scale=4),
            role("Backend 6 tháng", 6),
            role("Sau đó phát triển phần mềm 8 tháng", 8).model_copy(update={"relevance": "unknown"}),
        ])
        report = await check_eligibility(cv, jd, AsyncMock(side_effect=[conditions, observed]))
        self.assertEqual(report.state, "complete")
        self.assertEqual([r.status for r in report.results], ["met", "not_met", "insufficient_evidence"])
        self.assertEqual(report.results[-1].cv_quotes, [r.quote for r in observed.records[2:]])

    async def test_no_conditions_avoids_second_call(self):
        extract = AsyncMock(return_value=Requirements(conditions=[]))
        report = await check_eligibility("cv", "jd", extract)
        self.assertEqual(report.model_dump(), {"state": "complete", "results": []})
        extract.assert_awaited_once()

    async def test_errors_and_unverifiable_quotes(self):
        condition = GPA(type="gpa", quote="GPA > 3/4", priority="required", value=3, scale=4, operator=">")
        conditions = Requirements(conditions=[condition])
        self.assertEqual((await check_eligibility("cv", "jd", AsyncMock(side_effect=TimeoutError))).state, "unavailable")
        for second in (TimeoutError(), Observations(records=[
                Grade(type="gpa", condition_id="C1", quote="GPA 2/4", value=2, scale=4)])):
            report = await check_eligibility("no grade", condition.quote, AsyncMock(side_effect=[conditions, second]))
            self.assertEqual(report.state, "partial")
            self.assertEqual(report.results[0].status, "insufficient_evidence")
            self.assertEqual(report.results[0].cv_quotes, [])

"""Structured extraction and public report contracts."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Operator = Literal[">", ">=", "=", "<=", "<"]
Priority = Literal["required", "preferred", "unspecified"]
Enrollment = Literal["enrolled", "graduated"]
Decision = Literal["met", "not_met", "insufficient_evidence"]
Number = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Months = Annotated[int, Field(ge=0)]
YearMonth = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    quote: str = Field(min_length=1)


class Condition(Source):
    priority: Priority


class Education(Condition):
    type: Literal["education"]
    school: str | None = None
    status: Enrollment | None = None
    degree: str | None = None


class GPA(Condition):
    type: Literal["gpa"]
    operator: Operator | None = None
    value: Number | None = None
    scale: Number | None = None


class Experience(Condition):
    type: Literal["experience"]
    domain: str | None = None
    operator: Operator | None = None
    months: Months | None = None


class Manual(Condition):
    type: Literal["manual"]


Requirement = Annotated[Education | GPA | Experience | Manual, Field(discriminator="type")]


class Requirements(BaseModel):
    conditions: list[Requirement]


class Observation(Source):
    condition_id: str


class Study(Observation):
    type: Literal["education"]
    school: str | None = None
    status: Enrollment | None = None
    degree: str | None = None
    # Only an explicit, exhaustive statement can rule out unlisted studies.
    exclusive: bool = False


class Grade(Observation):
    type: Literal["gpa"]
    value: Number | None = None
    scale: Number | None = None


class Period(Observation):
    type: Literal["experience"]
    relevance: Literal["confirmed", "unknown", "unrelated"]
    scope: Literal["role", "explicit_domain_total"]
    months: Months | None = None
    after_quote: str | None = None
    start: YearMonth | None = None
    end: YearMonth | None = None


Evidence = Annotated[Study | Grade | Period, Field(discriminator="type")]


class Observations(BaseModel):
    records: list[Evidence]


class ConditionResult(BaseModel):
    condition_id: str
    type: Literal["education", "gpa", "experience", "manual"]
    priority: Priority
    jd_quote: str
    cv_quotes: list[str]
    status: Decision
    reason: str


class EligibilityReport(BaseModel):
    state: Literal["complete", "partial", "unavailable"]
    results: list[ConditionResult] = Field(default_factory=list)

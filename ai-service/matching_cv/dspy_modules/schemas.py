"""Typed prediction models for explicit skill extraction."""

from typing import Literal

from pydantic import BaseModel, Field


SkillKind = Literal["skill", "domain", "context", "certification"]


class ExplicitSkillMention(BaseModel):
    """A single verbatim skill or competency mention that should be retained."""

    mention: str = Field(description="Exact substring from the source document")
    kind: SkillKind = Field(description="Skill, domain, context, or certification")
    category: str = Field(description="One of the six supported extraction categories")
    source_sentence: str = Field(description="Verbatim sentence containing the mention")

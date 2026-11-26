"""Typed prediction models for explicit skill extraction."""

import logging
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, GetCoreSchemaHandler, ValidationError, model_validator
from pydantic_core import core_schema

logger = logging.getLogger(__name__)

SkillCategory = Literal[
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Certification",
    "Technical Standard",
]

VALID_CATEGORIES = {
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Certification",
    "Technical Standard",
}

SkillKind = Literal[
    "skill",
    "domain",
    "context",
    "certification",
    "education",
    "industry",
    "experience_years",
    "job_title",
]

NON_SKILL_KINDS = {"education", "industry", "experience_years", "job_title"}


class ExplicitSkillMention(BaseModel):
    """A single verbatim skill or competency mention that should be retained."""

    mention: str = Field(description="Exact substring from the source document")
    kind: SkillKind = Field(
        description=(
            "Entity kind: 'skill', 'domain', 'certification', 'education', "
            "'industry', 'experience_years', or 'job_title' ('context' is legacy only)"
        )
    )
    category: Optional[SkillCategory] = Field(
        default=None,
        description="One of the six supported extraction categories (can be None for non-skill entities)",
    )
    source_sentence: str = Field(description="Verbatim sentence containing the mention")

    @model_validator(mode="before")
    @classmethod
    def normalize_non_skill_category(cls, data: Any) -> Any:
        if isinstance(data, dict):
            kind = data.get("kind")
            category = data.get("category")
            if kind in NON_SKILL_KINDS:
                if category not in VALID_CATEGORIES:
                    data = dict(data)
                    data["category"] = None
        return data

    @model_validator(mode="after")
    def validate_category_for_skills(self) -> "ExplicitSkillMention":
        if self.kind not in NON_SKILL_KINDS and self.category is None:
            raise ValueError(f"category is required when kind is '{self.kind}'")
        return self


def filter_valid_explicit_mentions(value: Any) -> Any:
    """Drop only individual malformed/invalid items rather than failing the entire response."""
    if not isinstance(value, list):
        return value
    valid_items: List[ExplicitSkillMention] = []
    for item in value:
        if isinstance(item, ExplicitSkillMention):
            valid_items.append(item)
            continue
        try:
            valid_items.append(ExplicitSkillMention.model_validate(item))
        except ValidationError as exc:
            logger.warning("Dropping invalid explicit skill mention item %r: %s", item, exc)
    return valid_items


class ExplicitSkillMentionList(list):
    """List of ExplicitSkillMention that drops only individual invalid items on validation."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        list_schema = handler.generate_schema(List[ExplicitSkillMention])
        return core_schema.no_info_before_validator_function(
            filter_valid_explicit_mentions,
            list_schema,
        )



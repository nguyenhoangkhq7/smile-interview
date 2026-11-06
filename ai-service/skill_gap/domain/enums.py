from enum import Enum

class SkillType(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"

class SemanticAlignment(str, Enum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"

class SeniorityLevel(str, Enum):
    INTERN = "Intern"
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"
    UNKNOWN = "Unknown"

class RichnessLabel(str, Enum):
    RICH_CONTEXT = "RICH_CONTEXT"
    LIST_ONLY = "LIST_ONLY"
    AMBIGUOUS = "AMBIGUOUS"

class QuestionStrategy(str, Enum):
    NONE = "NONE"
    COMPARE_SUBSTITUTE = "COMPARE_SUBSTITUTE"
    PROBE_DEPTH = "PROBE_DEPTH"
    LEARNING_AGILITY = "LEARNING_AGILITY"

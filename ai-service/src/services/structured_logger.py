"""
structured_logger.py — Structured audit logger for Skill Gap Detection.
Records granular metrics per skill evaluation for scientific auditability and reproducibility:
- Raw dates returned by LLM
- Parsed ISO dates and diagnostics
- Effective experience months (effective_months)
- Evidence coverage ratio (c_evidence)
- Recency flag
- System validation flags and degraded status
"""
import threading
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class SkillAuditLog(BaseModel):
    skill_id: str
    raw_dates: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    parsed_dates: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    effective_months: float = 0.0
    c_evidence: float = 0.0
    recency_flag: bool = False
    degraded: bool = False
    flags: List[str] = Field(default_factory=list)
    active_params: Dict[str, Any] = Field(default_factory=dict)

class AuditLogger:
    """Thread-safe in-memory collector of structured logs for experimental reproducibility."""
    def __init__(self):
        self._lock = threading.Lock()
        self.records: List[SkillAuditLog] = []

    def record(self, entry: SkillAuditLog):
        with self._lock:
            self.records.append(entry)

    def get_records(self) -> List[SkillAuditLog]:
        with self._lock:
            return list(self.records)

    def clear(self):
        with self._lock:
            self.records.clear()

global_audit_logger = AuditLogger()

from datetime import date

from pydantic import BaseModel

# Recall classification -> severity, per PLAN.md's matching engine scoring.
RECALL_SEVERITY = {
    "Class I": "critical",
    "Class II": "high",
    "Class III": "medium",
}


class ComplianceFlag(BaseModel):
    id: str
    flag_type: str  # "recall" | "import_alert" | "gmp_violation" | "warning_letter"
    severity: str  # "critical" | "high" | "medium" | "low"
    status: str  # "active" | "closed"
    issued_date: str | None
    closed_date: str | None
    description: str
    source_url: str | None
    affected_products: list[str]


class Shortage(BaseModel):
    id: str
    drug_name: str
    generic_name: str
    status: str  # "active" | "resolved"
    reason: str | None
    start_date: str | None
    resolved_date: str | None
    affected_firms: list[str]
    source: str = "openFDA"
    last_checked: date

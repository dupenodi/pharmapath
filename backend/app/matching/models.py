from dataclasses import dataclass, field


@dataclass
class ProcurementRequest:
    drug_name: str
    delivery_state: str
    quantity: int | None = None
    dosage_form: str | None = None
    strength: str | None = None
    delivery_city: str | None = None
    deadline_days: int | None = None
    requirements: list[str] = field(default_factory=list)
    prefer_generic: bool = False
    resolved_drug_ids: list[str] = field(default_factory=list)


@dataclass
class SupplierMatch:
    supplier_id: str
    supplier_name: str
    supplier_type: str  # "distributor" | "manufacturer_direct"
    score: float
    compliance_status: str  # "clean" | "flagged" | "unknown"
    active_flags: list[dict]
    licensed_in_state: bool
    states_licensed: list[str]
    shortage_risk: str  # "none" | "possible" | "confirmed"
    distance_km: float | None
    score_breakdown: dict
    caveats: list[str] = field(default_factory=list)


@dataclass
class AlternativeDrug:
    drug_id: str
    generic_name: str
    brand_name: str | None
    relationship: str  # "therapeutic" | "generic" | "shared_ingredient"


@dataclass
class RiskSummary:
    overall_risk: str  # "low" | "medium" | "high" | "critical"
    shortage_active: bool
    manufacturers_flagged: int
    manufacturers_total: int
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    resolved_drug_id: str | None
    matches: list[SupplierMatch]
    alternatives: list[AlternativeDrug]
    risk_summary: RiskSummary | None
    explanation: str

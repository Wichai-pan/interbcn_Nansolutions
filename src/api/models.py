from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


AllowedStatus = Literal["open", "in_progress", "resolved"]


class AIExplanation(BaseModel):
    summary_en: str = ""
    summary_es: str = ""
    recommendation_en: str = ""
    recommendation_es: str = ""


class Alert(BaseModel):
    alert_id: str
    module: str
    client_id: str
    client_label: str = ""
    client_sub: str = ""
    product_family: str
    priority_level: str
    score: float
    confidence_level: str
    days_since_last_purchase: Optional[int] = None
    province: Optional[str] = None
    segment: Optional[str] = None
    ai_explanation: Optional[AIExplanation] = None
    linked_signals: List[str] = Field(default_factory=list)
    created_at: str
    status: AllowedStatus = "open"
    # Extra fields the dashboard renders (sub_type, evidence, alert_type)
    # are kept on the base model so /api/alerts and /api/top-actions both
    # carry enough payload for the front-end without an extra detail call.
    alert_type: Optional[str] = None
    sub_type: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class AlertDetail(Alert):
    raw: Dict[str, Any] = Field(default_factory=dict)


class OverviewResponse(BaseModel):
    scoring_date: Optional[str] = None
    total_alerts: int
    p1_count: int
    p2_count: int
    clients_at_risk: int
    avg_score: float
    module_breakdown: Dict[str, int]
    priority_breakdown: Dict[str, int]


class ProvinceData(BaseModel):
    province: str
    alert_count: int
    p1_count: int
    top_module: str


class AlertListResponse(BaseModel):
    scoring_date: Optional[str] = None
    total: int
    page: int
    page_size: int
    data: List[Alert]


class StatusUpdate(BaseModel):
    status: AllowedStatus

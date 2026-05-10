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


class AlertDetail(Alert):
    alert_type: Optional[str] = None
    sub_type: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    raw: Dict[str, Any] = Field(default_factory=dict)


class OverviewResponse(BaseModel):
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
    total: int
    page: int
    page_size: int
    data: List[Alert]


class StatusUpdate(BaseModel):
    status: AllowedStatus

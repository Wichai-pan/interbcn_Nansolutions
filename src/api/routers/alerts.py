from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..data_loader import get_alert, get_alerts_df, serialize_records, update_status
from ..models import Alert, AlertDetail, AlertListResponse, StatusUpdate


router = APIRouter(prefix="/alerts", tags=["alerts"])

SORT_COLUMNS = {"score", "days_since_last_purchase", "created_at"}


def _norm_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _filter_eq(series, value: str):
    return series.fillna("").astype(str).str.lower() == value.lower()


@router.get("", response_model=AlertListResponse)
def list_alerts(
    module: Optional[str] = None,
    priority: Optional[str] = None,
    product_family: Optional[str] = None,
    province: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="score"),
    order: str = Query(default="desc"),
) -> AlertListResponse:
    df = get_alerts_df()
    if df.empty:
        return AlertListResponse(total=0, page=page, page_size=page_size, data=[])

    module = _norm_text(module)
    priority = _norm_text(priority)
    product_family = _norm_text(product_family)
    province = _norm_text(province)
    status = _norm_text(status)

    if module:
        df = df[_filter_eq(df["module"], module.upper())]
    if priority:
        df = df[_filter_eq(df["priority_level"], priority)]
    if product_family:
        df = df[_filter_eq(df["product_family"], product_family)]
    if province:
        df = df[_filter_eq(df["province"], province)]
    if status:
        df = df[_filter_eq(df["status"], status)]
    if min_score is not None:
        df = df[df["score"] >= min_score]

    sort_col = sort_by if sort_by in SORT_COLUMNS else "score"
    ascending = order.lower() == "asc"
    df = df.sort_values(sort_col, ascending=ascending, na_position="last")

    total = int(len(df))
    start = (page - 1) * page_size
    end = start + page_size
    if start >= total:
        rows = []
    else:
        rows = serialize_records(df.iloc[start:end].to_dict(orient="records"))
    return AlertListResponse(total=total, page=page, page_size=page_size, data=[Alert(**row) for row in rows])


@router.get("/{alert_id}", response_model=AlertDetail)
def alert_detail(alert_id: str) -> AlertDetail:
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
    return AlertDetail(**alert)


@router.patch("/{alert_id}/status", response_model=Alert)
def patch_alert_status(alert_id: str, payload: StatusUpdate) -> Alert:
    try:
        alert = update_status(alert_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
    return Alert(**alert)

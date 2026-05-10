from __future__ import annotations

from fastapi import APIRouter

from ..data_loader import get_alerts_df, serialize_records
from ..models import Alert


router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/{client_id}/alerts")
def client_alerts(client_id: str) -> dict:
    df = get_alerts_df()
    if df.empty:
        return {"client_id": client_id, "alert_count": 0, "modules": [], "data": []}
    filtered = df[df["client_id"].astype(str) == str(client_id)].sort_values("score", ascending=False)
    modules = sorted(filtered["module"].dropna().astype(str).unique().tolist())
    return {
        "client_id": client_id,
        "alert_count": int(len(filtered)),
        "modules": modules,
        "data": [Alert(**row) for row in serialize_records(filtered.to_dict(orient="records"))],
    }

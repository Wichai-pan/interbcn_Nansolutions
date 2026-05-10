from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..data_loader import get_alerts_df, get_scoring_date, load_all_data
from ..models import OverviewResponse


router = APIRouter(tags=["overview"])


@router.get("/health")
def health() -> dict:
    data = load_all_data()
    df = data["alerts_df"]
    return {
        "status": "ok",
        "data_loaded": not df.empty,
        "alert_count": int(len(df)),
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


@router.get("/overview", response_model=OverviewResponse)
def overview() -> OverviewResponse:
    df = get_alerts_df()
    if df.empty:
        return OverviewResponse(
            scoring_date=get_scoring_date(),
            total_alerts=0,
            p1_count=0,
            p2_count=0,
            clients_at_risk=0,
            avg_score=0.0,
            module_breakdown={},
            priority_breakdown={},
        )

    priority = df["priority_level"].fillna("")
    actionable = df[priority.str.startswith(("P1", "P2"), na=False)]
    return OverviewResponse(
        scoring_date=get_scoring_date(),
        total_alerts=int(len(df)),
        p1_count=int(priority.str.startswith("P1", na=False).sum()),
        p2_count=int(priority.str.startswith("P2", na=False).sum()),
        clients_at_risk=int(actionable["client_id"].nunique()),
        avg_score=round(float(df["score"].mean()), 4),
        module_breakdown={str(k): int(v) for k, v in df["module"].value_counts().to_dict().items()},
        priority_breakdown={str(k): int(v) for k, v in df["priority_level"].value_counts().to_dict().items()},
    )

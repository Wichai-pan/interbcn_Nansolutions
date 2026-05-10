from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter

from ..data_loader import get_alerts_df
from ..models import ProvinceData


router = APIRouter(prefix="/map", tags=["map"])


@router.get("/provinces")
def provinces() -> Dict[str, List[ProvinceData]]:
    df = get_alerts_df()
    if df.empty:
        return {"data": []}

    df = df.copy()
    df["province"] = df["province"].fillna("Unknown").replace("", "Unknown")
    rows: List[ProvinceData] = []
    for province, group in df.groupby("province", dropna=False):
        module_counts = group["module"].value_counts()
        top_module = str(module_counts.index[0]) if not module_counts.empty else "UNKNOWN"
        p1_count = int(group["priority_level"].fillna("").str.startswith("P1", na=False).sum())
        rows.append(
            ProvinceData(
                province=str(province or "Unknown"),
                alert_count=int(len(group)),
                p1_count=p1_count,
                top_module=top_module,
            )
        )
    rows.sort(key=lambda item: item.alert_count, reverse=True)
    return {"data": rows}

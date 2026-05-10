from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from ..data_loader import get_scoring_date, get_selection_params, get_top_actions
from ..models import Alert


router = APIRouter(tags=["actions"])


@router.get("/top-actions")
def top_actions() -> Dict[str, Any]:
    data = [Alert(**row) for row in get_top_actions()]
    return {
        "scoring_date": get_scoring_date(),
        "top_n": len(data),
        "selection_params": get_selection_params(),
        "data": data,
    }

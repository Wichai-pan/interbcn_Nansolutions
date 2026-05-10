from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter

from ..data_loader import get_top_actions
from ..models import Alert


router = APIRouter(tags=["actions"])


@router.get("/top-actions")
def top_actions() -> Dict[str, List[Alert]]:
    return {"data": [Alert(**row) for row in get_top_actions()]}

"""
On-demand explanation endpoint.
POST /api/alerts/{alert_id}/explain
Calls Gemini via explanation_layer.explain_alert() and caches the result.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..data_loader import get_alert, get_scoring_date

router = APIRouter(prefix="/alerts", tags=["explain"])

_cache: Dict[str, Dict[str, str]] = {}


def _import_explain():
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from src.explanation_layer import explain_alert
        return explain_alert
    except Exception as exc:
        raise RuntimeError(f"Cannot import explanation_layer: {exc}") from exc


def _prepare(alert: dict) -> dict:
    prepared = dict(alert)
    if "product_family_biz" not in prepared:
        prepared["product_family_biz"] = prepared.get("product_family", "Unknown")
    if not prepared.get("evidence") and isinstance(prepared.get("raw"), dict):
        prepared["evidence"] = prepared["raw"].get("evidence", {})
    return prepared


@router.post("/{alert_id}/explain")
async def explain_alert_on_demand(alert_id: str) -> Dict[str, Any]:
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured on server")

    if alert_id in _cache:
        return {"alert_id": alert_id, "explanation": _cache[alert_id], "cached": True}

    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

    try:
        explain_fn = _import_explain()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    prepared = _prepare(alert)
    scoring_date = get_scoring_date()
    loop = asyncio.get_event_loop()
    try:
        explanation = await loop.run_in_executor(
            None,
            lambda: explain_fn(prepared, scoring_date),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini call failed: {exc}") from exc

    _cache[alert_id] = explanation
    return {"alert_id": alert_id, "explanation": explanation, "cached": False}

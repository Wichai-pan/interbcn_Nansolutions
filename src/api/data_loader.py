from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .config import settings


VALID_STATUSES = {"open", "in_progress", "resolved"}
status_overrides: Dict[str, str] = {}


def _warn(message: str) -> None:
    print(f"[api:data-loader] WARN: {message}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        _warn(f"{path} not found; using empty data")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _warn(f"failed to read {path}: {exc}; using empty data")
        return {}


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        _warn(f"{path} not found; using empty dataframe")
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        _warn(f"failed to read {path}: {exc}; using empty dataframe")
        return pd.DataFrame()


def _none_if_missing(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    return value


def _to_jsonable(value: Any) -> Any:
    value = _none_if_missing(value)
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _to_jsonable(value.item())
        except Exception:
            pass
    return value


def _normal_status(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "": "open",
        "pending": "open",
        "open": "open",
        "contacted": "in_progress",
        "in_progress": "in_progress",
        "resolved": "resolved",
        "closed": "resolved",
    }
    return mapping.get(text, "open")


def _score_from_row(row: Dict[str, Any]) -> float:
    for key in (
        "unified_score",
        "adjusted_score",
        "f1_final_score",
        "f2_priority_score",
        "f3_priority_score",
        "module_score",
        "replenishment_score",
        "score",
    ):
        value = _none_if_missing(row.get(key))
        if value is not None:
            try:
                return round(float(value), 4)
            except (TypeError, ValueError):
                continue
    return 0.0


def _days_since_last(row: Dict[str, Any]) -> Optional[int]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    value = row.get("days_since_last_purchase", evidence.get("days_since_last_purchase"))
    value = _none_if_missing(value)
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _alert_id(row: Dict[str, Any], module: str, index: int) -> str:
    existing = _none_if_missing(row.get("alert_id"))
    if existing:
        return str(existing)
    client = str(_none_if_missing(row.get("client_id")) or "unknown")
    family = str(_none_if_missing(row.get("product_family_biz") or row.get("product_family")) or "unknown")
    safe_family = "".join(ch if ch.isalnum() else "-" for ch in family).strip("-")
    return f"{module}-{client}-{safe_family}-{index + 1:06d}"


def _extract_explanation(row: Dict[str, Any]) -> Optional[Dict[str, str]]:
    explanation = row.get("ai_explanation") or row.get("explanation")
    if not isinstance(explanation, dict):
        return None
    return {
        "summary_en": str(explanation.get("summary_en") or ""),
        "summary_es": str(explanation.get("summary_es") or ""),
        "recommendation_en": str(explanation.get("recommendation_en") or ""),
        "recommendation_es": str(explanation.get("recommendation_es") or ""),
    }


def _standardize_records(records: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    standardized: List[Dict[str, Any]] = []
    created_at = _now_iso()
    for idx, raw in enumerate(records):
        row = {str(k): _to_jsonable(v) for k, v in dict(raw).items()}
        module = str(_none_if_missing(row.get("module")) or source or "").upper()
        if module not in {"F1", "F2", "F3"}:
            module = source.upper() if source.upper() in {"F1", "F2", "F3"} else "UNKNOWN"
        alert_id = _alert_id(row, module, idx)
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        linked = row.get("linked_signals")
        if not isinstance(linked, list):
            linked = [] if linked is None else [str(linked)]
        product_family = (
            _none_if_missing(row.get("product_family_biz"))
            or _none_if_missing(row.get("product_family"))
            or "Unknown"
        )
        segment = _none_if_missing(row.get("segment") or row.get("segment_code"))
        status = status_overrides.get(alert_id, _normal_status(row.get("status")))
        standardized.append(
            {
                "alert_id": alert_id,
                "module": module,
                "client_id": str(_none_if_missing(row.get("client_id")) or ""),
                "product_family": str(product_family),
                "priority_level": str(_none_if_missing(row.get("priority_level")) or "P4 Low"),
                "score": _score_from_row(row),
                "confidence_level": str(_none_if_missing(row.get("confidence_level")) or "low").lower(),
                "days_since_last_purchase": _days_since_last(row),
                "province": _none_if_missing(row.get("province")) or "Unknown",
                "segment": str(segment) if segment is not None else None,
                "ai_explanation": _extract_explanation(row),
                "linked_signals": [str(v) for v in linked if v is not None],
                "created_at": str(_none_if_missing(row.get("created_at")) or created_at),
                "status": status,
                "alert_type": _none_if_missing(row.get("alert_type")),
                "sub_type": _none_if_missing(row.get("sub_type")),
                "evidence": evidence,
                "raw": row,
            }
        )
    return standardized


def _records_from_df(df: pd.DataFrame, module: str) -> List[Dict[str, Any]]:
    if df.empty:
        return []
    records = df.replace({pd.NA: None}).to_dict(orient="records")
    for record in records:
        record.setdefault("module", module)
    return _standardize_records(records, module)


def _load_module_parquets(output_dir: Path) -> Dict[str, pd.DataFrame]:
    return {
        "F1_baseline": _read_parquet(output_dir / "stage1" / "f1_baseline_alerts.parquet"),
        "F1": _read_parquet(output_dir / "stage2" / "f1_combined_alerts.parquet"),
        "F2": _read_parquet(output_dir / "f2" / "f2_lost_customer_alerts.parquet"),
        "F3": _read_parquet(output_dir / "f3" / "f3_capture_opportunity_alerts.parquet"),
    }


@lru_cache(maxsize=1)
def load_all_data() -> Dict[str, Any]:
    output_dir = settings.output_path
    parquets = _load_module_parquets(output_dir)

    f4_all = _read_json(output_dir / "f4" / "all_alerts.json")
    top_actions = _read_json(output_dir / "f5" / "top_actions_explained.json")
    if not top_actions:
        top_actions = _read_json(output_dir / "f4" / "top_actions.json")

    if isinstance(f4_all.get("alerts"), list):
        alert_records = _standardize_records(f4_all["alerts"], "F4")
    else:
        alert_records = []
        alert_records.extend(_records_from_df(parquets["F1"], "F1"))
        alert_records.extend(_records_from_df(parquets["F2"], "F2"))
        alert_records.extend(_records_from_df(parquets["F3"], "F3"))

    top_records = []
    if isinstance(top_actions.get("actions"), list):
        top_records = _standardize_records(top_actions["actions"], "F4")

    alerts_df = pd.DataFrame(alert_records)
    if not alerts_df.empty:
        alerts_df = alerts_df.sort_values(["score", "alert_id"], ascending=[False, True]).reset_index(drop=True)

    return {
        "output_dir": output_dir,
        "parquets": parquets,
        "alerts_df": alerts_df,
        "top_actions": top_records,
        "loaded_at": _now_iso(),
    }


def reload_all_data() -> Dict[str, Any]:
    load_all_data.cache_clear()
    return load_all_data()


def get_alerts_df() -> pd.DataFrame:
    data = load_all_data()
    df = data["alerts_df"].copy()
    if not df.empty and status_overrides:
        df["status"] = df.apply(lambda r: status_overrides.get(r["alert_id"], r["status"]), axis=1)
    return df


def get_top_actions() -> List[Dict[str, Any]]:
    data = load_all_data()
    records = data["top_actions"]
    if not records:
        df = get_alerts_df()
        if df.empty or "score" not in df.columns:
            return []
        records = df.sort_values("score", ascending=False).head(5).to_dict(orient="records")
    return [apply_status(record) for record in records]


def apply_status(record: Dict[str, Any]) -> Dict[str, Any]:
    record = {str(k): _to_jsonable(v) for k, v in dict(record).items()}
    alert_id = str(record.get("alert_id", ""))
    if alert_id in status_overrides:
        record = dict(record)
        record["status"] = status_overrides[alert_id]
    return record


def serialize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [apply_status(record) for record in records]


def get_alert(alert_id: str) -> Optional[Dict[str, Any]]:
    df = get_alerts_df()
    if df.empty:
        return None
    match = df[df["alert_id"] == alert_id]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def update_status(alert_id: str, status: str) -> Optional[Dict[str, Any]]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    current = get_alert(alert_id)
    if current is None:
        return None
    status_overrides[alert_id] = status
    current["status"] = status
    return current

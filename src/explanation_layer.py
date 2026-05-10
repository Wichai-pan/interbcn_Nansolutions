"""
Explanation Layer (Gemini)
Inibsa Smart Demand Signals

Reads F4 outputs (top_actions.json + all_alerts.json), generates bilingual
EN/ES summary + recommendation per alert, and writes:
  ./output/f5/top_actions_explained.json
  ./output/f5/all_alerts_explained.json    (only if --enrich-all flag used)

Design:
  * Strict JSON output schema enforced by prompt
  * temperature=0.3 for stable but not deterministic output
  * Robust JSON parser (strips fences, finds outermost {})
  * Template fallback if API or parsing fails
  * Per-module prompt with strict language constraint (esp. F3 competitor wording)
"""
from __future__ import annotations
import os
import re
import json
import time
import argparse
import calendar
import datetime as dt
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# ENV & SDK
# ─────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

API_KEY = os.getenv("GEMINI_API_KEY")
# Key check deferred to call time so the module can be imported without the key

MODEL_NAME       = "gemini-2.5-flash"
API_ENDPOINT     = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent"
)
# gemini-2.5-flash uses internal "thinking" tokens that count against
# maxOutputTokens. We disable thinking to keep responses tight & predictable.
THINKING_BUDGET  = 0   # 0 = disabled
TEMPERATURE      = 0.3
MAX_OUTPUT_TOKENS = 1024
RETRIES          = 3
RETRY_BACKOFF_S  = 2

INPUT_F4 = Path("./output/f4")
OUTPUT_DIR = Path("./output/f5")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT (shared)
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a commercial intelligence assistant for Inibsa, a Spanish B2B
distributor of dental and medical consumables. You serve internal sales
representatives, not end customers.

STRICT RULES — non-negotiable:
1. Use ONLY the facts in the <evidence> block. Do not invent any number,
   date, product, or behavior.
2. Every quantitative claim in your output must trace back to a specific
   evidence field. If a field is null or missing, do not mention it.
3. Never promise outcomes. Avoid "the client will buy" / "el cliente
   comprará". Use "suggests", "indicates", "sugiere", "indica".
4. Refer to clients as "the dental clinic in {province}" using the province
   field provided in the evidence. If province is missing or unknown, fall
   back to "Client {client_id}". Do NOT invent company names.
5. Output MUST be a single valid JSON object. No prose before or after.
   No markdown code fences. No comments.
6. Required keys: summary_en, summary_es, recommendation_en,
   recommendation_es. No other keys allowed.
7. Length budget:
     summary: 35-55 words / 35-55 palabras
     recommendation: 25-40 words / 25-40 palabras
   The summary MUST contain at least one commercial insight beyond restating
   the evidence numbers (e.g. competitive risk implication, revenue
   opportunity size, urgency framing).
   The recommendation MUST include: (a) contact channel + time window
   anchored to priority_level, AND (b) one specific commercial angle the
   sales rep can use to open the conversation (e.g. seasonal promotion,
   product availability, potential revenue gap, win-back offer).
8. Spanish output must be natural Castilian Spanish, not literal
   translation from English.

OUTPUT SCHEMA (strict):
{
  "summary_en": "...",
  "summary_es": "...",
  "recommendation_en": "...",
  "recommendation_es": "..."
}
"""

# ─────────────────────────────────────────────────────────────
# PROMPT BUILDERS
# ─────────────────────────────────────────────────────────────
F1_TASK = """\
TASK: Explain a replenishment alert to a sales representative.

CONTEXT:
F1 uses TWO independent methods to detect overdue replenishment cycles.
The Statistical Analysis (Method B) is the PRIMARY signal — build your
narrative around it. The baseline+GRU (Method A) is a SECONDARY reference
used only to corroborate or qualify, not to lead.

  Method B — KMeans Behavioural Clustering (PRIMARY — lead with this):
    stat_personal_interval_days: this client's own median inter-order interval
    (180-day rolling window; more stable than short-term means).
    stat_f_in_score: how many personal intervals this client is overdue [0..10].
      0-3 = mild delay, 4-6 = moderate, 7-10 = severe.
    stat_grading_eur: 2-year cumulative spend × recency factor (EUR) —
    the revenue at stake if this client stops ordering.
    stat_behavioral_status: cluster verdict — use this as the primary framing
    of the client's situation ("Retention (Seasonal Inactive)", "Habitual", etc.)
    stat_n_active_products: number of distinct product lines still purchased.

  Method A — baseline+GRU (SECONDARY — use only to corroborate or flag divergence):
    days_since_last_purchase and expected_interval_days give urgency_multiplier
    (how many seasonal cycles this client is overdue per the baseline model).
    reorder_probability_pct: GRU model's probability of ordering in next 4 weeks.

  method_divergence: present when the two methods disagree significantly.
  If present, mention it briefly and lean on Method B.

The "summary" field MUST answer: WHY is this alert flagged today?
Structure: lead with the Statistical Analysis findings, then reference
baseline+GRU to corroborate.
- PRIMARY: use stat_behavioral_status as the opening framing of the client's state.
- PRIMARY: if stat_f_in_score is present, anchor urgency to it
  (e.g. "behavioural analysis scores this clinic {X}/10 overdue on its
  personal {Y}-day reorder rhythm").
- PRIMARY: if stat_grading_eur is present, state the revenue at stake.
- SECONDARY: mention days_since_last_purchase and expected_interval_days only
  to confirm the baseline+GRU signal aligns (or note divergence if it doesn't).
- SECONDARY: if reorder_probability_pct > 60, add one sentence about active
  demand / possible supplier leakage.
- If method_divergence is present, acknowledge conflicting signals and defer to Method B.
- If confidence_level is "low", acknowledge uncertainty briefly.
- Do NOT mention internal score fields or model/algorithm names.
- Do NOT mention calendar quarters.

The "recommendation" field MUST answer: WHAT should the sales rep do?
Suggest a contact channel (phone / email / visit) and a time window
("this week" / "within 3 days"). Anchor it to the priority_level.
Then add ONE specific commercial angle grounded in the Statistical Analysis:
* If stat_f_in_score > 7: frame as urgent account recovery ("lead with a
  win-back offer or loyalty incentive anchored to their purchase history")
* If stat_grading_eur is present: reference the EUR figure to justify a
  personalised offer ("this clinic has spent X€ over two years — open with
  a volume or loyalty incentive")
* If reorder_probability_pct > 65: frame as capturing an imminent order
  ("the clinic is likely ready to buy — lead with availability and pricing")
* If stat_behavioral_status contains "Seasonal": frame as seasonal reactivation
  ("match outreach timing to their seasonal rhythm")
* If confidence_level is "low" OR method_divergence is present: frame as a
  check-in ("open with a needs assessment before pitching")
* Default: mention current product availability or a relevant promotion
"""

F2_TASK = """\
TASK: Explain a lost-customer-risk alert to a sales representative.

CONTEXT:
F2 detects clients showing signs of churn. Three detection methods exist:
  - "silence_score": for technical products. Measures how far the current
    silence exceeds the client's historical p90 purchase interval.
  - "direct": for commodity clients silent for over 730 days. Treated as
    Likely Lost without further computation.
  - "historical_pattern": for active commodity clients showing volume or
    frequency decline vs their own 12-month baseline.

The lost_status field is one of: "Likely Lost", "At Risk", "Early Warning".

The "summary" field MUST answer: WHY is this client at risk?
Reference the relevant evidence by method:
  - silence_score → mention silence_score multiplier and threshold_used
  - direct → mention years of inactivity
  - historical_pattern → mention volume_drop_ratio and frequency_drop_ratio
Avoid stating churn as a certainty. Use language like "shows signs of",
"suggests deteriorating engagement".

The "recommendation" field MUST answer: WHAT recovery action to take?
Match the urgency to lost_status:
  - Likely Lost → field visit / account manager outreach
  - At Risk → proactive call with tailored offer
  - Early Warning → check-in via email or campaign
"""

F3_TASK = """\
TASK: Explain a capture-opportunity alert to a sales representative.

CONTEXT:
F3 detects clients with high commercial potential but low actual purchases
from Inibsa, suggesting unmet demand or possible competitor leakage.
Two methods exist:
  - "underutilization": active client whose 12-month purchases fall well
    below their estimated annual potential.
  - "cold_start": client with assigned potential but no purchase history.

opportunity_type is one of: "High Potential Underutilization",
"Moderate Underutilization", "Mild Underutilization",
"New Account Opportunity".

capture_window_flag indicates F2 overlap:
  - "FRESH_OPPORTUNITY": healthy active client, no F2 issue. Standard
    capture pitch.
  - "TRANSITIONAL": client At Risk in F2. Capture before drift continues.
  - "MONITOR": client Early Warning in F2. Light-touch follow-up.
  - "COLD_START": client never purchased. Prospecting required.

CRITICAL LANGUAGE CONSTRAINT:
You MUST NOT state that the client purchases from competitors. Inibsa
cannot observe competitor sales. Use phrasing like:
  - "potential unmet demand"
  - "possible competitor leakage"
  - "demanda no capturada"
  - "posible fuga a competencia"
Never assert competitor activity as a fact.

The "summary" field MUST answer: WHY is this an opportunity?
Reference:
  - utilization_ratio (as % of potential captured)
  - potential_gap in EUR
  - For cold_start: emphasize it is a never-engaged account
  - For TRANSITIONAL: mention the F2 overlap explicitly

The "recommendation" field MUST answer: WHAT capture action to take?
  - cold_start → prospecting / introductory visit
  - underutilization (FRESH_OPPORTUNITY) → upsell pitch tied to potential
  - TRANSITIONAL → faster account-manager engagement before drift
"""

# ─────────────────────────────────────────────────────────────
# EVIDENCE BUILDERS — map F4 evidence → prompt schema
# ─────────────────────────────────────────────────────────────
def _quarter_from_date(d: dt.date) -> str:
    return f"Q{((d.month - 1)//3) + 1}"

def _round_or_none(v, ndigits=4):
    if v is None: return None
    try:
        return round(float(v), ndigits)
    except (TypeError, ValueError):
        return v

_TM_F_IN_DIVERGENCE_THRESHOLD = 0.8

def build_f1_evidence(alert: dict, scoring_date_str: str) -> dict:
    ev = alert.get("evidence") or {}
    days     = ev.get("days_since_last_purchase")
    interval = ev.get("expected_interval")
    delay    = ev.get("delay")

    urgency_multiplier = None
    if interval and float(interval) > 0 and days is not None:
        urgency_multiplier = round(float(days) / float(interval), 1)

    rop = ev.get("reorder_probability")
    reorder_pct = round(float(rop) * 100, 1) if rop is not None else None

    # Stat fields from teammate's KMeans model
    stat_interval  = ev.get("stat_avg_interval_days")
    stat_grading   = ev.get("stat_grading_eur")
    stat_f_in      = ev.get("stat_f_in_fixed")
    stat_n         = ev.get("stat_n_active_products")
    stat_status    = ev.get("stat_behavioral_status")
    stat_cluster   = ev.get("stat_cluster")

    # Divergence flag: our urgency_multiplier (normalised to [0,10]) vs stat_f_in
    method_divergence = None
    if urgency_multiplier is not None and stat_f_in is not None:
        our_scaled = min(urgency_multiplier, 10.0)
        if abs(our_scaled - float(stat_f_in)) > _TM_F_IN_DIVERGENCE_THRESHOLD:
            if our_scaled > float(stat_f_in):
                method_divergence = "Model A flags higher urgency than statistical baseline"
            else:
                method_divergence = "Statistical baseline flags higher urgency than Model A"

    out = {
        "client_id":                    str(alert.get("client_id")),
        "province":                     alert.get("province"),
        "product_family_biz":           alert.get("product_family_biz"),
        "priority_level":               alert.get("priority_level"),
        "confidence_level":             alert.get("confidence_level"),
        "days_since_last_purchase":     days,
        "expected_interval_days":       _round_or_none(interval, 1),
        "delay_days":                   _round_or_none(delay, 1),
        "urgency_multiplier":           urgency_multiplier,
        "reorder_probability_pct":      reorder_pct,
        "stat_personal_interval_days":  _round_or_none(stat_interval, 1),
        "stat_grading_eur":             _round_or_none(stat_grading, 2),
        "stat_f_in_score":              _round_or_none(stat_f_in, 2),
        "stat_n_active_products":       stat_n,
        "stat_behavioral_status":       stat_status,
        "stat_cluster":                 stat_cluster,
        "method_divergence":            method_divergence,
    }
    # Drop None values to keep prompt lean
    return {k: v for k, v in out.items() if v is not None}

def build_f2_evidence(alert: dict) -> dict:
    ev = alert.get("evidence") or {}
    return {
        "client_id":              str(alert.get("client_id")),
        "product_family_biz":     alert.get("product_family_biz"),
        "province":               alert.get("province"),
        "priority_level":         alert.get("priority_level"),
        "confidence_level":       alert.get("confidence_level"),
        "method":                 ev.get("method"),
        "lost_status":            ev.get("lost_status"),
        "days_since_last_purchase": ev.get("days_since_last_purchase"),
        "silence_score":          _round_or_none(ev.get("silence_score"), 2),
        "threshold_used":         _round_or_none(ev.get("threshold_used"), 1),
        "volume_drop_ratio":      _round_or_none(ev.get("volume_drop_ratio"), 3),
        "frequency_drop_ratio":   _round_or_none(ev.get("frequency_drop_ratio"), 3),
        "hist_avg_monthly_value": _round_or_none(ev.get("hist_avg_monthly_value"), 2),
        "recent_avg_monthly_value": _round_or_none(ev.get("recent_avg_monthly_value"), 2),
    }

def build_f3_evidence(alert: dict) -> dict:
    ev = alert.get("evidence") or {}
    return {
        "client_id":             str(alert.get("client_id")),
        "product_family_biz":    alert.get("product_family_biz"),
        "province":              alert.get("province"),
        "priority_level":        alert.get("priority_level"),
        "confidence_level":      alert.get("confidence_level"),
        "method":                ev.get("method") or ("cold_start" if ev.get("is_cold_start") else "underutilization"),
        "opportunity_type":      ev.get("opportunity_type"),
        "is_cold_start":         ev.get("is_cold_start"),
        "potential_value_eur":   _round_or_none(ev.get("potential_value"), 2),
        "observed_value_12m_eur": _round_or_none(ev.get("observed_value_12m"), 2),
        "utilization_ratio":     _round_or_none(ev.get("utilization_ratio"), 4),
        "potential_gap_eur":     _round_or_none(ev.get("potential_gap"), 2),
        "capture_window_flag":   ev.get("capture_window_flag"),
        "lost_status_f2":        ev.get("lost_status_f2"),
    }

# ─────────────────────────────────────────────────────────────
# PROMPT ASSEMBLY
# ─────────────────────────────────────────────────────────────
def assemble_prompt(module: str, evidence: dict) -> str:
    if module == "F1":
        task = F1_TASK
    elif module == "F2":
        task = F2_TASK
    elif module == "F3":
        task = F3_TASK
    else:
        raise ValueError(f"Unknown module: {module}")
    ev_json = json.dumps(evidence, ensure_ascii=False, indent=2)
    return (
        SYSTEM_PROMPT.strip() + "\n\n" +
        task.strip() + "\n\n" +
        "<evidence>\n" + ev_json + "\n</evidence>\n\n" +
        "Now generate output for the evidence above. "
        "Return ONLY a JSON object matching the OUTPUT SCHEMA, "
        "with no markdown, comments, or extra prose."
    )

# ─────────────────────────────────────────────────────────────
# ROBUST JSON PARSER
# ─────────────────────────────────────────────────────────────
JSON_OBJ_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)

def safe_parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    s = raw.strip()
    # strip markdown fences if present
    if s.startswith("```"):
        s = re.sub(r"^```(?:json|JSON)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # try direct parse first
    try:
        return json.loads(s)
    except Exception:
        pass
    # extract first {...} block (greedy outer)
    m = JSON_OBJ_RE.search(s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def validate_schema(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"summary_en", "summary_es", "recommendation_en", "recommendation_es"}
    return required.issubset(obj.keys()) and all(
        isinstance(obj[k], str) and obj[k].strip() for k in required
    )

# ─────────────────────────────────────────────────────────────
# FALLBACK TEMPLATES
# ─────────────────────────────────────────────────────────────
def fallback_explanation(alert: dict) -> dict:
    cid    = alert.get("client_id", "?")
    mod    = alert.get("module", "?")
    prio   = alert.get("priority_level", "?")
    fam    = alert.get("product_family_biz", "?")
    return {
        "summary_en":        f"Client {cid} flagged by {mod} module with priority {prio} for product family {fam}. Review evidence for details.",
        "summary_es":        f"Cliente {cid} señalado por el módulo {mod} con prioridad {prio} en la familia {fam}. Revisar evidencia para más detalles.",
        "recommendation_en": f"Review the evidence and contact the client according to {prio} priority guidelines.",
        "recommendation_es": f"Revisar la evidencia y contactar al cliente según las directrices de prioridad {prio}.",
        "_fallback":         True,
    }

# ─────────────────────────────────────────────────────────────
# GEMINI CALL
# ─────────────────────────────────────────────────────────────
def call_gemini(prompt: str) -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":        TEMPERATURE,
            "maxOutputTokens":    MAX_OUTPUT_TOKENS,
            "responseMimeType":   "application/json",
            "thinkingConfig":     {"thinkingBudget": THINKING_BUDGET},
        },
    }
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.post(
                API_ENDPOINT,
                params={"key": key},
                json=payload,
                timeout=30,
            )
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                if attempt < RETRIES:
                    time.sleep(RETRY_BACKOFF_S * attempt)
                    continue
                print(f"  [WARN] Gemini API error after {RETRIES} tries: {last_err}")
                return None
            data = r.json()
            cands = data.get("candidates") or []
            if not cands:
                last_err = f"No candidates in response: {str(data)[:200]}"
                continue
            parts = cands[0].get("content", {}).get("parts", [])
            if not parts:
                last_err = "No parts in candidate"
                continue
            return parts[0].get("text", "")
        except Exception as e:
            last_err = str(e)
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
            else:
                print(f"  [WARN] Gemini call failed after {RETRIES} retries: {e}")
    return None

# ─────────────────────────────────────────────────────────────
# PER-ALERT PIPELINE
# ─────────────────────────────────────────────────────────────
def explain_alert(alert: dict, scoring_date_str: str) -> dict:
    module = alert.get("module")
    if module == "F1":
        ev = build_f1_evidence(alert, scoring_date_str)
    elif module == "F2":
        ev = build_f2_evidence(alert)
    elif module == "F3":
        ev = build_f3_evidence(alert)
    else:
        return fallback_explanation(alert)

    prompt = assemble_prompt(module, ev)
    raw    = call_gemini(prompt)
    parsed = safe_parse_json(raw) if raw else None
    if parsed and validate_schema(parsed):
        # sanitize: keep only the 4 required keys
        return {k: parsed[k].strip() for k in
                ("summary_en", "summary_es", "recommendation_en", "recommendation_es")}
    return fallback_explanation(alert)

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def process_file(in_path: Path, out_path: Path, top_only: bool):
    if not in_path.exists():
        print(f"[WARN] {in_path} not found — skipping")
        return
    blob = json.loads(in_path.read_text())
    scoring_date = blob.get("scoring_date", str(dt.date.today()))
    items_key = "actions" if "actions" in blob else "alerts"
    items = blob.get(items_key, [])
    print(f"\n[Explain] {in_path}  ({len(items)} items)")

    enriched = []
    for i, alert in enumerate(items, 1):
        print(f"  [{i}/{len(items)}] {alert.get('alert_id')} ({alert.get('module')})", flush=True)
        explanation = explain_alert(alert, scoring_date)
        out_alert = dict(alert)
        out_alert["explanation"] = explanation
        enriched.append(out_alert)

    out = dict(blob)
    out[items_key] = enriched
    out["explanation_meta"] = {
        "model":            MODEL_NAME,
        "temperature":      TEMPERATURE,
        "n_items":          len(enriched),
        "n_fallback":       sum(1 for a in enriched if a["explanation"].get("_fallback")),
        "generated_at":     dt.datetime.now().isoformat(timespec="seconds"),
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"  saved → {out_path}  ({out_path.stat().st_size/1024:.1f} KB)")
    print(f"  fallback used on {out['explanation_meta']['n_fallback']}/{len(enriched)} alerts")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enrich-all", action="store_true",
                    help="Also enrich all_alerts.json (slow; cost = N alerts × API call).")
    ap.add_argument("--max-all", type=int, default=50,
                    help="Cap on number of alerts in all_alerts to enrich (for cost control).")
    args = ap.parse_args()

    print("=" * 70)
    print("EXPLANATION LAYER — Gemini")
    print(f"  model: {MODEL_NAME}   temperature: {TEMPERATURE}")
    print("=" * 70)

    process_file(INPUT_F4 / "top_actions.json",
                 OUTPUT_DIR / "top_actions_explained.json",
                 top_only=True)

    if args.enrich_all:
        # Light version: only enrich top-K of all_alerts to keep cost bounded
        all_in = INPUT_F4 / "all_alerts.json"
        if all_in.exists():
            blob = json.loads(all_in.read_text())
            n_before = len(blob.get("alerts", []))
            blob["alerts"] = blob.get("alerts", [])[: args.max_all]
            n_after = len(blob["alerts"])
            print(f"\n[--enrich-all] Capping all_alerts to top {n_after}/{n_before}")
            tmp = OUTPUT_DIR / "_all_alerts_capped.json"
            tmp.write_text(json.dumps(blob, ensure_ascii=False, indent=2))
            process_file(tmp,
                         OUTPUT_DIR / "all_alerts_explained.json",
                         top_only=False)
            tmp.unlink()

    print("\n[DONE]")

if __name__ == "__main__":
    main()

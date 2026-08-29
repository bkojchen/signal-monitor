"""Transform layer: turn raw readings into green/amber/red statuses + overall."""
from __future__ import annotations
import datetime as dt
from typing import Dict, List

RANK = {"green": 0, "amber": 1, "red": 2, "stale": -1}


def _worse(a: str, b: str) -> str:
    return a if RANK.get(a, 0) >= RANK.get(b, 0) else b


def _roc(series: List[tuple], lookback: int) -> float | None:
    """Percent change of latest value vs `lookback` points back."""
    vals = [v for _, v in series]
    if len(vals) <= lookback:
        return None
    prev = vals[-1 - lookback]
    if prev == 0:
        return None
    return (vals[-1] / prev - 1.0) * 100


def _status_absolute(value: float, spec: dict) -> str:
    a = spec.get("absolute", {})
    if "red_above" in a and value >= a["red_above"]:   return "red"
    if "amber_above" in a and value >= a["amber_above"]: return "amber"
    if "red_below" in a and value <= a["red_below"]:   return "red"
    if "amber_below" in a and value <= a["amber_below"]: return "amber"
    return "green"


def _status_roc(change: float, spec: dict) -> str:
    r = spec.get("roc", {})
    red, amb = r.get("red_change_pct"), r.get("amber_change_pct")
    worse_is_up = spec.get("direction") != "lower_is_worse" and \
        (red is None or red > 0)
    if worse_is_up:                       # rising value is bad
        if red is not None and change >= red:  return "red"
        if amb is not None and change >= amb:  return "amber"
    else:                                 # falling value is bad (negative thresholds)
        if red is not None and change <= red:  return "red"
        if amb is not None and change <= amb:  return "amber"
    return "green"


def _fmt_change(change: float | None) -> str:
    if change is None:
        return "—"
    return f"{change:+.1f}%"


def resolve_signal(sig: str, spec: dict, current, history: Dict[str, List[tuple]],
                   stale_after: int) -> dict:
    out = {"key": sig, "label": spec["label"], "category": spec.get("category", "leading"),
           "unit": spec.get("unit", ""), "note": spec.get("note", ""),
           "cascade": bool(spec.get("cascade")), "sparkline": [],
           "status": "green", "value_str": "—", "change_str": "—", "trigger": "",
           "stale": False, "source_hint": spec.get("source_hint", "")}

    # provenance: automated feed vs. hand-entered
    _src = spec.get("source")
    if _src == "fred":
        out["auto"], out["source"] = True, "FRED"
    elif _src == "market_drawdown":
        out["auto"], out["source"] = True, "Yahoo"
    else:
        out["auto"], out["source"] = False, "Manual"

    # ---- categorical (manual) ----
    if spec.get("direction") == "categorical":
        val = current.get("value") if isinstance(current, dict) else current
        mapping = spec.get("categorical", {})
        out["status"] = mapping.get(str(val), "amber")
        out["value_str"] = str(val).replace("_", " ")
        out["trigger"] = "red on: " + ", ".join(k.replace("_", " ")
                                                 for k, s in mapping.items() if s == "red")
        upd = current.get("updated", "") if isinstance(current, dict) else ""
        out.update(_staleness(upd, stale_after))
        return out

    # ---- numeric ----
    series = history.get(sig, [])
    out["sparkline"] = [v for _, v in series][-30:]
    value = series[-1][1] if series else (current if isinstance(current, (int, float)) else None)
    if value is None:
        out["status"] = "stale"; out["value_str"] = "no data"; return out

    out["value_str"] = f"{value:,.2f}{spec.get('unit','')}"

    status = "green"; parts = []
    if "absolute" in spec:
        status = _worse(status, _status_absolute(value, spec))
        a = spec["absolute"]
        if "amber_above" in a: parts.append(f"amber ≥{a['amber_above']}{spec.get('unit','')}")
        if "amber_below" in a: parts.append(f"amber ≤{a['amber_below']}{spec.get('unit','')}")
    if "roc" in spec:
        change = _roc(series, spec["roc"]["lookback"])
        out["change_str"] = _fmt_change(change)
        if change is not None:
            status = _worse(status, _status_roc(change, spec))
        r = spec["roc"]
        parts.append(f"amber {r['amber_change_pct']:+g}% / qtr")

    out["status"] = status
    out["trigger"] = "  ·  ".join(parts)

    upd = current.get("updated", "") if isinstance(current, dict) else ""
    if upd:
        out.update(_staleness(upd, stale_after))
    return out


def _staleness(updated: str, stale_after: int) -> dict:
    if not updated:
        return {}
    try:
        d = dt.date.fromisoformat(str(updated))
    except ValueError:
        return {}
    age = (dt.date.today() - d).days
    return {"stale": age > stale_after, "updated": updated, "age_days": age}


def resolve_all(config: dict, current: Dict[str, object],
                history: Dict[str, List[tuple]], stale_after: int) -> List[dict]:
    specs = {**config.get("signals", {}), **config.get("manual_signals", {})}
    return [resolve_signal(sig, spec, current.get(sig), history, stale_after)
            for sig, spec in specs.items()]


def overall_status(signals: List[dict], playbook: dict) -> dict:
    active = [s for s in signals if s["status"] in ("green", "amber", "red")]
    reds = [s for s in active if s["status"] == "red"]
    ambers_plus = [s for s in active if s["status"] in ("amber", "red")]
    leading_alerts = [s for s in ambers_plus if s["category"] == "leading"]
    hy = next((s for s in signals if s["key"] == "hy_spread"), None)
    cascade_red = any(s["cascade"] and s["status"] == "red" for s in signals)

    level = "green"
    if len(leading_alerts) >= playbook.get("amber_if_leading_alerts_at_least", 2):
        level = "amber"
    if len(reds) >= playbook.get("red_if_reds_at_least", 2):
        level = "red"
    if playbook.get("red_if_cascade_red_and_hy_amber") and cascade_red and hy \
            and hy["status"] in ("amber", "red"):
        level = "red"

    pb = playbook.get(level, {})
    drivers = [s["label"] for s in sorted(ambers_plus, key=lambda x: -RANK[x["status"]])][:4]
    return {"level": level, "headline": pb.get("headline", level.upper()),
            "action": pb.get("action", ""), "drivers": drivers,
            "counts": {"red": len(reds), "amber": len(ambers_plus) - len(reds),
                       "green": len(active) - len(ambers_plus)}}

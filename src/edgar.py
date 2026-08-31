"""Automate the capex signals from SEC EDGAR (free, official XBRL API).

Strategy: try discrete quarterly data first (timely); if the four filers don't
line up on enough common quarters -- Microsoft's June fiscal year often prevents
it -- fall back to ANNUAL 10-K figures, which are unambiguous and always present.
Either way it returns the three signals plus a `note` describing what it used,
so the mode is always visible.

  hyperscaler_capex        raising | holding | cutting
  hyperscaler_capex_accel  accelerating | steady | decelerating | contracting
  capex_to_ocf             capex / operating cash flow, %

Set env SEC_USER_AGENT="you@example.com" for reliable access.
"""
from __future__ import annotations
import os, re, time

CIKS = {"MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724, "META": 1326801}
CAPEX_CONCEPTS = ["PaymentsToAcquirePropertyPlantAndEquipment",   # MSFT, GOOGL, META
                  "PaymentsToAcquireProductiveAssets"]            # AMZN
OCF_CONCEPTS = ["NetCashProvidedByUsedInOperatingActivities"]
QFRAME = re.compile(r"^CY\d{4}Q[1-4]$")

LAST_DEBUG: dict = {}   # populated by compute() for diagnostics


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", "signal-monitor contact@example.com")


def _fetch_concept(cik: int, concept: str) -> dict | None:
    import requests
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
    try:
        r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
        time.sleep(0.15)                    # stay well under SEC's 10 req/s
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _quarterly(js: dict | None) -> dict:
    out = {}
    if js:
        for f in js.get("units", {}).get("USD", []):
            if QFRAME.match(f.get("frame", "")):
                out[f["frame"]] = f["val"]
    return out


def _annual(js: dict | None) -> dict:
    """{ '2025': full_year_value } from 10-K facts."""
    out = {}
    if js:
        for f in js.get("units", {}).get("USD", []):
            if f.get("fp") == "FY" and f.get("form") == "10-K" and f.get("end"):
                out[f["end"][:4]] = f["val"]
    return out


def _series(cik: int, concepts: list, fetcher, extract) -> dict:
    for c in concepts:
        s = extract(fetcher(cik, c))
        if s:
            return s
    return {}


def _signals(cq: list, oq: list) -> dict:
    ttm_c, ttm_o = sum(cq[-4:]), sum(oq[-4:])          # quarterly: TTM; annual: last yr dominates
    ratio = round(ttm_c / ttm_o * 100, 1) if ttm_o else None
    out = {}
    if ratio is not None:
        out["capex_to_ocf"] = ratio
    return out, ratio


def _growth_signals(cq: list, step: int) -> dict:
    """direction + acceleration from a capex list; step=4 for quarters (YoY), 1 for years."""
    def g(i):
        return (cq[i] / cq[i - step] - 1) * 100 if i >= step and cq[i - step] else None
    g_now, g_prev = g(len(cq) - 1), g(len(cq) - 2)
    if g_now is None and len(cq) >= 2 and cq[-2]:
        g_now = (cq[-1] / cq[-2] - 1) * 100
    out = {}
    if g_now is not None:
        out["hyperscaler_capex"] = "cutting" if g_now < 0 else "holding" if g_now < 10 else "raising"
    if g_now is not None and g_prev is not None:
        d = g_now - g_prev
        out["hyperscaler_capex_accel"] = ("contracting" if g_now < 0 else
                                          "accelerating" if d > 2 else
                                          "decelerating" if d < -2 else "steady")
    return out


def _collect(extract, fetcher):
    capex, ocf, found, counts = {}, {}, [], {}
    for name, cik in CIKS.items():
        c = _series(cik, CAPEX_CONCEPTS, fetcher, extract)
        o = _series(cik, OCF_CONCEPTS, fetcher, extract)
        counts[name] = {"capex_pts": len(c), "ocf_pts": len(o)}
        if c and o:
            capex[cik], ocf[cik] = c, o
            found.append(name)
    LAST_DEBUG["per_company"] = counts
    return capex, ocf, found


def _aligned(capex, ocf):
    keys = sorted(set.intersection(*[set(capex[c]) for c in capex]) &
                  set.intersection(*[set(ocf[c]) for c in ocf]))
    cq = [sum(capex[c][k] for c in capex) for k in keys]
    oq = [sum(ocf[c][k] for c in ocf) for k in keys]
    return keys, cq, oq


def compute(fetcher=_fetch_concept) -> tuple[dict, str]:
    LAST_DEBUG.clear()
    # ---- try quarterly ----
    capex, ocf, found = _collect(_quarterly, fetcher)
    LAST_DEBUG["quarterly_per_company"] = dict(LAST_DEBUG.get("per_company", {}))
    if len(found) >= 2:
        keys, cq, oq = _aligned(capex, ocf)
        if len(keys) >= 2:
            out, _ = _signals(cq, oq)
            out.update(_growth_signals(cq, step=4))
            LAST_DEBUG.update({"mode": "quarterly", "keys": keys,
                               "capex_series": cq, "ocf_series": oq, "out": out})
            return out, f"EDGAR quarterly: {len(found)}/4 ({','.join(found)}), {len(keys)} qtrs {keys[0]}->{keys[-1]}"

    # ---- fall back to annual 10-K ----
    capex, ocf, found = _collect(_annual, fetcher)
    LAST_DEBUG["annual_per_company"] = dict(LAST_DEBUG.get("per_company", {}))
    if len(found) >= 2:
        keys, cq, oq = _aligned(capex, ocf)
        LAST_DEBUG.update({"mode": "annual", "keys": keys, "capex_series": cq, "ocf_series": oq})
        if len(keys) >= 2:
            out, _ = _signals(cq[-1:], oq[-1:])
            out.update(_growth_signals(cq, step=1))
            LAST_DEBUG["out"] = out
            return out, f"EDGAR annual: {len(found)}/4 ({','.join(found)}), FY {keys[0]}->{keys[-1]}"
        return {}, f"EDGAR annual: {len(found)} companies but <2 common years"

    return {}, f"EDGAR: no usable data (found {','.join(found) or 'none'})"

"""Automate the three capex signals from SEC EDGAR (free, official XBRL API).

Pulls quarterly capital expenditure and operating cash flow for the four
hyperscalers, aggregates over whichever companies return data, and computes:

  hyperscaler_capex        raising | holding | cutting        (1st derivative)
  hyperscaler_capex_accel  accelerating|steady|decelerating|contracting (2nd derivative)
  capex_to_ocf             trailing-twelve-month capex / OCF, %

Robustness: different filers tag capex differently (Amazon uses
PaymentsToAcquireProductiveAssets), so each concept has fallbacks, any single
company that fails is skipped rather than killing the run, and the returned
note says exactly what was found -- check it in the workflow log.

SEC asks automated callers to send a contact in the User-Agent. Set env
SEC_USER_AGENT="you@example.com" for reliability (a generic default is used otherwise).
"""
from __future__ import annotations
import os, re

CIKS = {"MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724, "META": 1326801}
CAPEX_CONCEPTS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",   # MSFT, GOOGL, META
    "PaymentsToAcquireProductiveAssets",            # AMZN
]
OCF_CONCEPTS = ["NetCashProvidedByUsedInOperatingActivities"]
QFRAME = re.compile(r"^CY\d{4}Q[1-4]$")             # SEC standardized 3-month calendar frames


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", "signal-monitor contact@example.com")


def _fetch_concept(cik: int, concept: str) -> dict | None:
    """Return the companyconcept JSON, or None on any failure (404, 403, network)."""
    import requests
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
    try:
        r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def quarterly_from_concept(js: dict | None) -> dict:
    """{ 'CY2025Q3': value } using only SEC standardized discrete-quarter frames."""
    out = {}
    if not js:
        return out
    for f in js.get("units", {}).get("USD", []):
        fr = f.get("frame", "")
        if QFRAME.match(fr):
            out[fr] = f["val"]
    return out


def _series(cik: int, concepts: list, fetcher) -> dict:
    """First non-empty quarterly series across candidate concept tags."""
    for c in concepts:
        q = quarterly_from_concept(fetcher(cik, c))
        if q:
            return q
    return {}


def compute(fetcher=_fetch_concept) -> tuple[dict, str]:
    """Return ({signal: value}, note). fetcher(cik, concept) is injectable for testing."""
    capex: dict = {}
    ocf: dict = {}
    found = []
    for name, cik in CIKS.items():
        cser = _series(cik, CAPEX_CONCEPTS, fetcher)
        oser = _series(cik, OCF_CONCEPTS, fetcher)
        if cser and oser:
            capex[cik], ocf[cik] = cser, oser
            found.append(name)

    if len(found) < 2:
        return {}, f"EDGAR: only {len(found)} companies returned data ({','.join(found) or 'none'})"

    cap_common = set.intersection(*[set(v) for v in capex.values()])
    ocf_common = set.intersection(*[set(v) for v in ocf.values()])
    quarters = sorted(cap_common & ocf_common)
    if len(quarters) < 2:
        return {}, f"EDGAR: {len(found)} companies but <2 common quarters"

    cq = [sum(capex[c][q] for c in capex) for q in quarters]
    oq = [sum(ocf[c][q] for c in ocf) for q in quarters]

    ttm_capex, ttm_ocf = sum(cq[-4:]), sum(oq[-4:])
    ratio = round(ttm_capex / ttm_ocf * 100, 1) if ttm_ocf else None

    def yoy(i: int):
        return (cq[i] / cq[i - 4] - 1) * 100 if i >= 4 and cq[i - 4] else None

    g_now, g_prev = yoy(len(cq) - 1), yoy(len(cq) - 2)
    if g_now is None:
        g_now = (cq[-1] / cq[-2] - 1) * 100 if cq[-2] else None

    direction = None
    if g_now is not None:
        direction = "cutting" if g_now < 0 else "holding" if g_now < 10 else "raising"

    accel = None
    if g_now is not None and g_prev is not None:
        delta = g_now - g_prev
        if g_now < 0:
            accel = "contracting"
        elif delta > 2:
            accel = "accelerating"
        elif delta < -2:
            accel = "decelerating"
        else:
            accel = "steady"

    out = {}
    if ratio is not None:
        out["capex_to_ocf"] = ratio
    if direction:
        out["hyperscaler_capex"] = direction
    if accel:
        out["hyperscaler_capex_accel"] = accel
    note = (f"EDGAR: {len(found)}/4 companies ({','.join(found)}), "
            f"{len(quarters)} quarters {quarters[0]}->{quarters[-1]}")
    return out, note

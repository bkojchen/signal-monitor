"""Automate the three capex signals from SEC EDGAR (free, official XBRL API).

Pulls quarterly capital expenditure and operating cash flow for the four
hyperscalers straight from their filings, aggregates, and computes:

  hyperscaler_capex        raising | holding | cutting     (1st derivative)
  hyperscaler_capex_accel  accelerating|steady|decelerating|contracting (2nd derivative)
  capex_to_ocf             trailing-twelve-month capex ÷ OCF, %

SEC asks automated callers to send a real contact in the User-Agent. Set env
SEC_USER_AGENT="you@example.com" (falls back to a generic string otherwise).
"""
from __future__ import annotations
import os, re

CIKS = {"MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724, "META": 1326801}
CAPEX_CONCEPT = "PaymentsToAcquirePropertyPlantAndEquipment"
OCF_CONCEPT = "NetCashProvidedByUsedInOperatingActivities"
QFRAME = re.compile(r"^CY\d{4}Q[1-4]$")          # SEC's standardized 3-month calendar frames


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", "signal-monitor/1.0 (contact: set SEC_USER_AGENT)")


def _fetch_concept(cik: int, concept: str) -> dict:
    import requests
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
    r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    r.raise_for_status()
    return r.json()


def quarterly_from_concept(js: dict) -> dict:
    """{ 'CY2025Q3': value } using only SEC's standardized discrete-quarter frames.

    Relying on the `frame` field avoids the year-to-date differencing that makes
    raw 10-Q cash-flow figures so error-prone: SEC already computes the clean
    3-month value and tags it CYyyyyQn.
    """
    out = {}
    for f in js.get("units", {}).get("USD", []):
        fr = f.get("frame", "")
        if QFRAME.match(fr):
            out[fr] = f["val"]
    return out


def _aggregate(per_company: dict) -> dict:
    """{quarter: sum across companies} keeping only quarters where all four reported."""
    return {q: sum(v.values()) for q, v in per_company.items() if len(v) == len(CIKS)}


def compute(fetcher=_fetch_concept) -> tuple[dict, str]:
    """Return ({signal: value}, note). `fetcher` is injectable for testing."""
    capex: dict = {}
    ocf: dict = {}
    for cik in CIKS.values():
        for q, v in quarterly_from_concept(fetcher(cik, CAPEX_CONCEPT)).items():
            capex.setdefault(q, {})[cik] = v
        for q, v in quarterly_from_concept(fetcher(cik, OCF_CONCEPT)).items():
            ocf.setdefault(q, {})[cik] = v

    ca, oa = _aggregate(capex), _aggregate(ocf)
    quarters = sorted(set(ca) & set(oa))                 # CYyyyyQn sorts chronologically
    if len(quarters) < 2:
        return {}, "insufficient EDGAR history"

    cq = [ca[q] for q in quarters]
    oq = [oa[q] for q in quarters]

    ttm_capex, ttm_ocf = sum(cq[-4:]), sum(oq[-4:])
    ratio = round(ttm_capex / ttm_ocf * 100, 1) if ttm_ocf else None

    def yoy(i: int):
        return (cq[i] / cq[i - 4] - 1) * 100 if i >= 4 and cq[i - 4] else None

    g_now, g_prev = yoy(len(cq) - 1), yoy(len(cq) - 2)

    if g_now is None:                                    # <5 quarters: fall back to QoQ
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
    return out, f"{len(quarters)} common quarters ({quarters[0]}→{quarters[-1]})"

"""Automate capex signals from SEC EDGAR (free official XBRL API).

Builds an ANNUALIZED QUARTERLY view so the capex-growth roll-over is visible
quarter-by-quarter instead of only once a year:

  1. reconstruct discrete quarterly capex/OCF per company via YTD differencing
     (robust to SEC's flaky quarterly frame tags; handles non-calendar fiscal years)
  2. aggregate across the four hyperscalers per calendar quarter
  3. trailing-twelve-month (TTM) sums remove seasonality
  4. TTM year-over-year growth = the curve you can watch bend
  5. change in that growth = acceleration -> accelerating | stabilizing | contracting

Signals produced:
  capex_growth_ttm         latest TTM YoY capex growth %  (its history IS the curve)
  hyperscaler_capex_accel  accelerating | stabilizing | contracting
  hyperscaler_capex        raising | holding | cutting
  capex_to_ocf             TTM capex / TTM OCF, %

Falls back to annual 10-K figures if quarterly reconstruction is too sparse.
Set env SEC_USER_AGENT="you@example.com" for reliable access.
"""
from __future__ import annotations
import datetime as dt, os
from collections import defaultdict

CIKS = {"MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724, "META": 1326801}
CAPEX_CONCEPTS = ["PaymentsToAcquirePropertyPlantAndEquipment",
                  "PaymentsToAcquireProductiveAssets"]
OCF_CONCEPTS = ["NetCashProvidedByUsedInOperatingActivities"]

LAST_DEBUG: dict = {}
LAST_CURVE: dict = {}          # {quarter_end_date: growth%} for the dashboard sparkline


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", "signal-monitor contact@example.com")


def _fetch_concept(cik: int, concept: str) -> dict | None:
    import requests, time
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
    try:
        r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
        time.sleep(0.15)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# ---------- helpers ----------
def _cal_quarter(end: str) -> str:
    d = dt.date.fromisoformat(end)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def _qkey(q: str):
    return (int(q[:4]), int(q[5:]))


def _months(s: str, e: str) -> int:
    return round((dt.date.fromisoformat(e) - dt.date.fromisoformat(s)).days / 30.4)


def _facts(js: dict | None) -> list:
    out = []
    if js:
        for f in js.get("units", {}).get("USD", []):
            s, e, v = f.get("start"), f.get("end"), f.get("val")
            if s and e and v is not None:
                out.append((s, e, v))
    return out


def _discrete_quarters(facts: list) -> dict:
    """{calendarQuarter: value} via year-to-date differencing within each fiscal year."""
    byfy = defaultdict(dict)
    for s, e, v in facts:
        m = _months(s, e)
        if m in (3, 6, 9, 12):
            byfy[s][m] = (e, v)
    out = {}
    for per in byfy.values():
        parts = []
        if 3 in per:
            parts.append(per[3])
        if 6 in per and 3 in per:
            parts.append((per[6][0], per[6][1] - per[3][1]))
        if 9 in per and 6 in per:
            parts.append((per[9][0], per[9][1] - per[6][1]))
        if 12 in per and 9 in per:
            parts.append((per[12][0], per[12][1] - per[9][1]))
        for e, v in parts:
            out[_cal_quarter(e)] = v
    return out


def _company_quarters(cik: int, concepts: list, fetcher) -> dict:
    merged = []
    for c in concepts:
        merged += _facts(fetcher(cik, c))
    return _discrete_quarters(merged)


def _aggregate(per_company: dict) -> dict:
    """{quarter: sum} keeping quarters present for EVERY company we have."""
    if not per_company:
        return {}
    common = set.intersection(*[set(v) for v in per_company.values()])
    return {q: sum(pc[q] for pc in per_company.values()) for q in common}


def _quarter_end(q: str) -> str:
    y, n = _qkey(q)
    return {1: f"{y}-03-31", 2: f"{y}-06-30", 3: f"{y}-09-30", 4: f"{y}-12-31"}[n]


def _ttm_growth_curve(agg: dict):
    """[(quarter, ttm_yoy_growth%)] sorted; needs >=8 quarters to yield points."""
    qs = sorted(agg, key=_qkey)
    vals = [agg[q] for q in qs]
    ttm = [sum(vals[i - 3:i + 1]) if i >= 3 else None for i in range(len(vals))]
    curve = []
    for i in range(len(qs)):
        if ttm[i] is not None and i >= 4 and ttm[i - 4]:
            curve.append((qs[i], round((ttm[i] / ttm[i - 4] - 1) * 100, 1)))
    return qs, vals, ttm, curve


# ---------- annual fallback ----------
def _annual(js: dict | None) -> dict:
    out = {}
    if js:
        for f in js.get("units", {}).get("USD", []):
            if f.get("fp") == "FY" and f.get("form") == "10-K" and f.get("end"):
                out[f["end"][:4]] = f["val"]
    return out


def _annual_compute(fetcher):
    capex, ocf, found = {}, {}, []
    for name, cik in CIKS.items():
        c, o = {}, {}
        for cc in CAPEX_CONCEPTS:
            c.update(_annual(fetcher(cik, cc)))
        o.update(_annual(fetcher(cik, OCF_CONCEPTS[0])))
        if c and o:
            capex[cik], ocf[cik] = c, o
            found.append(name)
    if len(found) < 2:
        return {}, f"EDGAR annual: only {len(found)} companies"
    yrs = sorted(set.intersection(*[set(capex[c]) for c in capex]) &
                 set.intersection(*[set(ocf[c]) for c in ocf]))[-6:]
    if len(yrs) < 2:
        return {}, f"EDGAR annual: <2 common years {yrs}"
    cq = [sum(capex[c][y] for c in capex) for y in yrs]
    oq = [sum(ocf[c][y] for c in ocf) for y in yrs]
    out = {"capex_to_ocf": round(cq[-1] / oq[-1] * 100, 1)}
    g_now = (cq[-1] / cq[-2] - 1) * 100 if cq[-2] else None
    g_prev = (cq[-2] / cq[-3] - 1) * 100 if len(cq) >= 3 and cq[-3] else None
    if g_now is not None:
        out["hyperscaler_capex"] = "cutting" if g_now < 0 else "holding" if g_now < 10 else "raising"
        out["capex_growth_ttm"] = round(g_now, 1)
    if g_now is not None and g_prev is not None:
        d = g_now - g_prev
        out["hyperscaler_capex_accel"] = ("contracting" if d < -2 else
                                          "accelerating" if d > 2 else "stabilizing")
    LAST_DEBUG.update({"mode": "annual", "years": yrs, "capex": cq, "ocf": oq})
    return out, f"EDGAR annual: {len(found)}/4 ({','.join(found)}), FY {yrs[0]}->{yrs[-1]}"


# ---------- main ----------
def compute(fetcher=_fetch_concept) -> tuple[dict, str]:
    LAST_DEBUG.clear()
    LAST_CURVE.clear()

    capex, ocf, found = {}, {}, []
    for name, cik in CIKS.items():
        c = _company_quarters(cik, CAPEX_CONCEPTS, fetcher)
        o = _company_quarters(cik, OCF_CONCEPTS, fetcher)
        if len(c) >= 8 and len(o) >= 8:
            capex[cik], ocf[cik] = c, o
            found.append(name)
    LAST_DEBUG["quarterly_found"] = found

    if len(found) >= 3:
        cap_agg, ocf_agg = _aggregate(capex), _aggregate(ocf)
        qs, cvals, cttm, curve = _ttm_growth_curve(cap_agg)
        _, _, ottm, _ = _ttm_growth_curve(ocf_agg)
        if len(curve) >= 2:
            out = {}
            # TTM capex/OCF at the latest common quarter
            common_q = sorted(set(cap_agg) & set(ocf_agg), key=_qkey)
            def ttm_at(agg, q):
                i = sorted(agg, key=_qkey).index(q)
                sv = sorted(agg, key=_qkey)
                return sum(agg[k] for k in sv[i - 3:i + 1]) if i >= 3 else None
            lq = common_q[-1]
            tc, to = ttm_at(cap_agg, lq), ttm_at(ocf_agg, lq)
            if tc and to:
                out["capex_to_ocf"] = round(tc / to * 100, 1)
            g_now = curve[-1][1]
            out["capex_growth_ttm"] = g_now
            out["hyperscaler_capex"] = "cutting" if g_now < 0 else "holding" if g_now < 10 else "raising"
            d = curve[-1][1] - curve[-2][1]
            out["hyperscaler_capex_accel"] = ("contracting" if d < -2 else
                                              "accelerating" if d > 2 else "stabilizing")
            LAST_CURVE.update({_quarter_end(q): v for q, v in curve})
            LAST_DEBUG.update({"mode": "quarterly", "found": found,
                               "curve": curve[-10:], "n_quarters": len(qs),
                               "latest_quarter": lq})
            return out, (f"EDGAR quarterly: {len(found)}/4 ({','.join(found)}), "
                         f"{len(curve)} curve pts, latest {curve[-1][0]} "
                         f"growth {g_now:+.1f}% accel {out['hyperscaler_capex_accel']}")

    return _annual_compute(fetcher)

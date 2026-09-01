"""Extract layer: pull raw values from FRED, market prices, and manual inputs."""
from __future__ import annotations
import csv, datetime as dt, os
from typing import Dict, List

HISTORY = os.path.join(os.path.dirname(__file__), "..", "data", "history.csv")


def _write_debug(note: str, computed: dict) -> None:
    """Leave a detailed breadcrumb in data/edgar_debug.txt (committed by the workflow)."""
    try:
        import json
        try:
            import edgar as _e
            detail = getattr(_e, "LAST_DEBUG", {})
        except Exception:
            detail = {}
        path = os.path.join(os.path.dirname(__file__), "..", "data", "edgar_debug.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(f"{dt.datetime.now(dt.timezone.utc).isoformat()}\n{note}\n"
                    f"computed: {computed}\n\ndetail:\n{json.dumps(detail, indent=2, default=str)}\n")
    except Exception:
        pass


def _today() -> str:
    return dt.date.today().isoformat()


# --------------------------------------------------------------------------- #
#  FRED
# --------------------------------------------------------------------------- #
def fetch_fred(series_id: str, api_key: str) -> float | None:
    """Latest non-missing observation for a FRED series."""
    import requests
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id, "api_key": api_key, "file_type": "json",
        "sort_order": "desc", "limit": 12,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    for obs in r.json().get("observations", []):
        if obs["value"] not in (".", "", None):
            return float(obs["value"])
    return None


# --------------------------------------------------------------------------- #
#  Market drawdown (Yahoo via yfinance) — equal-weight basket vs trailing high
# --------------------------------------------------------------------------- #
def fetch_market_drawdown(tickers: List[str], lookback_days: int = 365) -> float | None:
    import yfinance as yf
    data = yf.download(tickers, period=f"{lookback_days}d", progress=False,
                       auto_adjust=True)["Close"].dropna()
    if data.empty:
        return None
    norm = data / data.iloc[0]          # rebase each name to 1.0
    basket = norm.mean(axis=1)          # equal-weight
    peak = basket.cummax().iloc[-1]
    return round((basket.iloc[-1] / peak - 1.0) * 100, 2)   # % below trailing high


# --------------------------------------------------------------------------- #
#  Manual inputs
# --------------------------------------------------------------------------- #
def load_manual(path: str) -> Dict[str, dict]:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f) or {}


# --------------------------------------------------------------------------- #
#  History store  (long format: date, signal, value)
# --------------------------------------------------------------------------- #
def append_history(records: Dict[str, float]) -> None:
    """Append today's readings, one row per signal, de-duping same-day rows."""
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    today = _today()
    rows: List[dict] = []
    if os.path.exists(HISTORY):
        with open(HISTORY) as f:
            rows = [r for r in csv.DictReader(f)
                    if not (r["date"] == today and r["signal"] in records)]
    for sig, val in records.items():
        if val is not None:
            rows.append({"date": today, "signal": sig, "value": val})
    rows.sort(key=lambda r: (r["signal"], r["date"]))
    with open(HISTORY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "signal", "value"])
        w.writeheader()
        w.writerows(rows)


def _replace_series(signal: str, series: dict) -> None:
    """Replace all history rows for `signal` with a dated {date: value} curve."""
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    rows = []
    if os.path.exists(HISTORY):
        with open(HISTORY) as f:
            rows = [r for r in csv.DictReader(f) if r["signal"] != signal]
    for date, val in series.items():
        rows.append({"date": date, "signal": signal, "value": val})
    rows.sort(key=lambda r: (r["signal"], r["date"]))
    with open(HISTORY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "signal", "value"])
        w.writeheader()
        w.writerows(rows)


def read_history() -> Dict[str, List[tuple]]:
    """Return {signal: [(date, value), ... ascending]}."""
    out: Dict[str, List[tuple]] = {}
    if not os.path.exists(HISTORY):
        return out
    with open(HISTORY) as f:
        for r in csv.DictReader(f):
            try:
                out.setdefault(r["signal"], []).append((r["date"], float(r["value"])))
            except ValueError:
                pass  # categorical values aren't stored numerically
    for s in out:
        out[s].sort()
    return out


# --------------------------------------------------------------------------- #
#  Orchestrated extract
# --------------------------------------------------------------------------- #
def run_extract(config: dict, manual_path: str) -> Dict[str, object]:
    """Return {signal: current_value}. Numeric signals also get appended to history."""
    numeric: Dict[str, float] = {}
    current: Dict[str, object] = {}
    key = config.get("fred_api_key", "")

    for sig, spec in config.get("signals", {}).items():
        try:
            if spec["source"] == "fred":
                v = fetch_fred(spec["series_id"], key)
            elif spec["source"] == "market_drawdown":
                v = fetch_market_drawdown(spec["tickers"])
            else:
                v = None
        except Exception as e:               # a dead source must not kill the run
            print(f"  ! {sig}: {e}")
            v = None
        if v is not None:
            numeric[sig] = v
            current[sig] = v

    manual = load_manual(manual_path)
    for sig, spec in config.get("manual_signals", {}).items():
        entry = manual.get(sig, {})
        val = entry.get("value")
        current[sig] = {"value": val, "updated": str(entry.get("updated", ""))}
        if spec.get("direction") != "categorical" and isinstance(val, (int, float)):
            numeric[sig] = float(val)

    # ---- EDGAR-computed capex signals (one fetch covers several signals) ----
    edgar_sigs = {s: spec for s, spec in config.get("signals", {}).items()
                  if spec.get("source") == "edgar"}
    if edgar_sigs:
        try:
            import edgar as _edgar
            computed, note = _edgar.compute()
            print(f"  {note}")
            _write_debug(note, computed)
            for sig, spec in edgar_sigs.items():
                if sig in computed:
                    v = computed[sig]
                    current[sig] = v
                    # capex_growth_ttm is stored as a full quarterly curve below, not a single point
                    if sig != "capex_growth_ttm" and spec.get("direction") != "categorical" \
                            and isinstance(v, (int, float)):
                        numeric[sig] = float(v)
            if getattr(_edgar, "LAST_CURVE", None):
                _replace_series("capex_growth_ttm", _edgar.LAST_CURVE)
        except Exception as e:
            print(f"  ! edgar: {e}")
            _write_debug(f"exception: {e}", {})

    append_history(numeric)
    return current

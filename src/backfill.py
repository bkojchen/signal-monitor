"""One-time backfill: pull real history for the AUTOMATED signals from FRED + Yahoo
and write it into data/history.csv, so rate-of-change signals work from day one.

Run once, locally or anywhere with internet + your FRED key:

    export FRED_API_KEY=your_key            # or leave it in config.yaml
    pip install -r requirements.txt
    python3 src/backfill.py                  # default ~200 calendar days
    python3 src/backfill.py --days 400       # pull more if you want a longer runway

Manual signals (GPU rent, loan quality, etc.) have no historical feed, so this
leaves any existing manual rows untouched and only (re)builds the automated ones.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
HISTORY = os.path.join(ROOT, "data", "history.csv")


def load_config():
    import yaml
    with open(os.path.join(ROOT, "config.yaml")) as f:
        return yaml.safe_load(f)


def fred_series(series_id: str, api_key: str, start: str) -> list[tuple]:
    """All observations for a FRED series since `start` (ascending)."""
    import requests
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json",
              "observation_start": start, "sort_order": "asc"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    out = []
    for o in r.json().get("observations", []):
        if o["value"] not in (".", "", None):
            out.append((o["date"], round(float(o["value"]), 4)))
    return out


def market_drawdown_series(tickers: list[str], start: str) -> list[tuple]:
    """Running drawdown (% below trailing peak) of an equal-weight basket."""
    import yfinance as yf
    data = yf.download(tickers, start=start, progress=False, auto_adjust=True)["Close"]
    data = data.dropna()
    if data.empty:
        return []
    norm = data / data.iloc[0]
    basket = norm.mean(axis=1)
    peak = basket.cummax()
    dd = (basket / peak - 1.0) * 100
    return [(d.strftime("%Y-%m-%d"), round(float(v), 2)) for d, v in dd.items()]


def read_existing() -> list[dict]:
    if not os.path.exists(HISTORY):
        return []
    with open(HISTORY, newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=200, help="calendar days of history to pull")
    args = ap.parse_args()

    cfg = load_config()
    key = os.environ.get("FRED_API_KEY") or cfg.get("fred_api_key", "")
    if "PUT_YOUR_FREE_FRED_KEY" in key or not key:
        sys.exit("No FRED key. Set FRED_API_KEY or put it in config.yaml.")

    start = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    auto = cfg.get("signals", {})
    backfilled: dict[str, list[tuple]] = {}

    for sig, spec in auto.items():
        try:
            if spec.get("source") == "fred":
                rows = fred_series(spec["series_id"], key, start)
            elif spec.get("source") == "market_drawdown":
                rows = market_drawdown_series(spec["tickers"], start)
            else:
                continue
            backfilled[sig] = rows
            print(f"  {sig:22s} {len(rows):4d} points  "
                  f"({rows[0][0]} → {rows[-1][0]})" if rows else f"  {sig}: none")
        except Exception as e:
            print(f"  ! {sig}: {e}")

    # keep every existing row that ISN'T an auto signal we just rebuilt (i.e. manual rows)
    kept = [r for r in read_existing() if r["signal"] not in backfilled]
    rows = kept + [{"date": d, "signal": s, "value": v}
                   for s, series in backfilled.items() for d, v in series]
    rows.sort(key=lambda r: (r["signal"], r["date"]))

    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "signal", "value"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n• wrote {len(rows)} rows to {HISTORY}  "
          f"({len(kept)} manual kept, {sum(len(v) for v in backfilled.values())} backfilled)")
    print("• commit data/history.csv, then your scheduled runs append to it going forward.")


if __name__ == "__main__":
    main()

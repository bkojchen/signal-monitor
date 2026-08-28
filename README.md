# AI Credit-Cascade Monitor

A small ETL that pulls the leading indicators from the *"Peak Cheap"* thesis, resolves each to
**green / amber / red**, and renders a self-contained HTML dashboard with your playbook action attached.

It is deliberately split into what can be trusted to an API and what can't:

| Automated (no touching) | Manual (you update on review) |
|---|---|
| High-yield & IG credit spreads, VIX, 2s10s — **FRED** | GPU rental rate |
| AI-complex drawdown — **Yahoo Finance** | Marginal GPU-loan quality (rating/spread) |
| | Hyperscaler capex guidance |
| | Server-life / impairment disclosures |
| | AI-lab funding rounds |
| | Neocloud covenant / default events |

The manual signals have no clean free API — scraping them would break constantly, so they live in
`signals_manual.yaml` with a source hint for each and a staleness flag if you forget to update them.

## Quick start

```bash
pip install -r requirements.txt

# 1) Preview the UI immediately, no key needed (uses bundled sample data):
python3 src/main.py --mock
open output/dashboard.html            # macOS  (Linux: xdg-open, Windows: start)

# 2) Go live — get a free FRED key (30 seconds):
#    https://fred.stlouisfed.org/docs/api/api_key.html
#    paste it into config.yaml  ->  fred_api_key
python3 src/main.py
```

Each live run appends today's hard-data readings to `data/history.csv` (that's what powers the
rate-of-change triggers and the sparklines), then rewrites `output/dashboard.html`.

## Your weekly loop

1. Open `signals_manual.yaml`, update the six values + their `updated` date (source hints are in `config.yaml`).
2. Run `python3 src/main.py`.
3. Read the banner. Green → carry on. Amber → the WATCH action. Red → the ACT action.

## Automate it (daily, hands-off)

```bash
# crontab -e   — runs 07:30 every weekday, logs output
30 7 * * 1-5 cd /path/to/signal-monitor && /usr/bin/python3 src/main.py >> run.log 2>&1
```

The hard-data signals then refresh themselves; you only touch the manual file when something moves.

## Tuning

- **Thresholds** live in `config.yaml` under each signal (`absolute` levels and `roc` % moves).
  They're starting points from the thesis — calibrate to your own risk tolerance.
- **Overall logic** is the `playbook:` block: how many alerts tip WATCH, what tips ACT, and the
  exact action text shown on the banner (mirrors the green/amber/red plan we wrote).
- **Add a signal**: add an entry under `signals:` (FRED series id or a market ticker) — the
  transform and dashboard pick it up automatically.

## Structure

```
config.yaml          signal definitions, thresholds, playbook
signals_manual.yaml  the six values you maintain
src/extract.py       FRED + Yahoo + manual  ->  data/history.csv
src/transform.py     readings  ->  statuses  ->  overall
src/dashboard.py     ->  output/dashboard.html
src/main.py          orchestration ( --mock to preview )
```

Not investment advice. The thresholds encode one bearish thesis; they are a discipline for acting
fast if it starts to play out, not a prediction that it will. Confirm any real move with your adviser/gestor.

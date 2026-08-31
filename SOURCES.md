# Where to get each manual signal

> **Now automated — no entry needed:** `hyperscaler_capex`, `hyperscaler_capex_accel`, and
> `capex_to_ocf` are computed directly from SEC EDGAR filings (`src/edgar.py`). Any manual
> instructions for these below are obsolete — ignore them.

Six signals have no clean free API, so you hand-enter them in `signals_manual.yaml`.
None need to be daily — most move on earnings or news. Here's where to look and exactly
what to type. The **trend matters more than the precise number**; you're watching for direction.

---

### 1. `gpu_rent_h100` — H100 rental rate ($/GPU-hour)
**Why it matters:** falling rents = GPU oversupply / softening demand = collateral eroding faster than the loans against it. The thesis's single best leading tell.
**Where:** free GPU price aggregators — [cloud-gpus.com](https://cloud-gpus.com), [getdeploying.com/gpus](https://getdeploying.com/gpus), or the live board at [vast.ai](https://vast.ai). Take a representative **on-demand H100 SXM** price (eyeball the median across providers).
**Enter:** the number, e.g. `2.35`. Check ~monthly. A drop of >15% vs your last entry trips amber, >30% red.

### 2. `marginal_loan_quality` — quality of the newest GPU-backed debt deal
**Why it matters:** late-cycle credit reaches for worse borrowers. When the *newest* neocloud deal prices as junk, the financing chain is stretching.
**Where:** headlines on the latest CoreWeave / Nebius / Crusoe / Lambda debt raise — Reuters, Bloomberg, FT, The Information — and rating-agency press releases (Moody's/S&P/Fitch, free).
**Enter one of:** `investment_grade` · `crossover` (BBB-/BB+ borderline) · `junk` (BB or below) · `stalled` (deal pulled or repriced higher). Check when a new deal is reported.

### 3. `hyperscaler_capex` — Microsoft / Alphabet / Amazon / Meta capex guidance
**Why it matters:** these four are the demand anchor. Any collective *cut* is the ground shifting.
**Where:** their quarterly earnings (late Jan, Apr, Jul, Oct). Free transcripts on Motley Fool / Seeking Alpha, or news coverage — look for capex guidance language.
**Enter one of:** `raising` · `holding` · `cutting`. Update once a quarter around earnings.

### 4. `depreciation_disclosure` — server useful-life / impairment
**Why it matters:** earnings have been flattered by *extending* server life to 6 years. Anyone **shortening** it again, or taking a GPU impairment charge, is admitting the assets age faster than claimed.
**Where:** 10-Q/10-K filings on [SEC EDGAR full-text search](https://efts.sec.gov/LATEST/search-index?q=%22useful+life%22) (free) — search "useful life" / "servers" — plus earnings-call mentions and news of any impairment.
**Enter one of:** `extending` · `stable` · `shortening` · `charge_taken`. Quarterly / event-driven.

### 5. `ai_lab_rounds` — OpenAI / Anthropic / xAI funding health
**Why it matters:** lab valuations mark up the whole complex. A flat, delayed, or down round removes that fuel.
**Where:** The Information, TechCrunch, Bloomberg, Reuters on the latest raise — was it up, flat, delayed, or down?
**Enter one of:** `up_round` · `flat` · `delayed` · `down_round`. Every few months.

### 6. `neocloud_events` — covenant breach / default / forced GPU sale
**Why it matters:** this is the detonation point — the moment a leveraged GPU cloud can't pay and dumps chips into the market.
**Where:** credit/restructuring news and filings on CoreWeave, Crusoe, Lambda, Nebius and smaller "neoclouds" — Reuters, Bloomberg, distressed-debt coverage.
**Enter one of:** `none` · `stress` · `covenant_breach` · `default`. You'll type `none` most weeks — until you don't.

---

## The update ritual (2 minutes, ~weekly)

1. On GitHub, open `signals_manual.yaml` → pencil icon.
2. For anything that moved, change `value:` and set `updated:` to today (`YYYY-MM-DD`).
3. Commit. The page rebuilds within a minute; a reading older than 45 days shows a **stale** flag.

You don't have to touch all six every time — update what changed, leave the rest. The `updated`
date on each card (and the stale flag) tells you at a glance what's getting old.

---

# New signals — from *The Second Derivative* & *The Teaser Period*

These track the *mechanism* the earlier board only saw the symptoms of. Most move on quarterly
earnings or on a specific event, so they carry longer stale windows (they won't nag between updates).

## Watch the acceleration, not the level (*Second Derivative*)

### `hyperscaler_capex_accel` — is capex *growth* still speeding up? *(cascade)*
The article's central number. Not "are they spending more" (that's the old `hyperscaler_capex`), but "is the growth *rate* itself rising or slowing." Their estimate: already negative.
**Where:** the four hyperscalers' capex guidance across the last few quarters — compute the change in the growth rate. **Enter:** `accelerating` · `steady` · `decelerating` · `contracting`.

### `capex_cut_rewarded` — has a cut been *rewarded*? *(cascade)*
The regime-flip trigger: the first hyperscaler to announce a capex **cut** and see its stock **rise**. That inversion ends the arms race. **Watch Meta/Zuckerberg first.**
**Enter:** `none` · `cut_announced` · `cut_rewarded`.

### `capex_to_ocf` — capex as % of operating cash flow
Above 100%, the build is no longer self-funded — it runs on debt/equity ("the fortress is being spent"). **Where:** sum the four hyperscalers' capex ÷ operating cash flow from earnings. **Enter:** the number (e.g. `85`).

## The funding treadmill & the reset wall (*Teaser Period*)

### `openai_step_up` — round-over-round valuation multiple *(cascade)*
The treadmill that keeps the naked borrower solvent. Prior steps ran 1.7–1.9×; the implied IPO step is ~1.23×. Toward 1.0× = the refinance is failing. **Where:** each new raise ÷ prior valuation. **Enter:** the multiple (e.g. `1.23`).

### `openai_ipo_status` — the refinance of last resort *(cascade)*
**Enter:** `on_track` · `delayed` · `pulled` · `priced_below`. (The delay itself is the signal.)

### `contract_renegotiation` — the reset-wall trigger *(cascade)*
Any take-or-pay compute deal deferred or renegotiated — "capacity rephasing," "efficiency-linked pricing." The **first** amendment re-rates the entire $2.3T backlog from "contracted" to "negotiable." **Enter:** `none` · `rumored` · `confirmed`.

### `index_concentration` — your own portfolio's exposure
Top-10 (mostly AI) share of the S&P 500: ~40% now vs ~27% at the dot-com peak. This is literally how concentrated your World/S&P ETFs are. **Where:** S&P / index factsheets. **Enter:** the % (e.g. `40`).

## Cadence

- **Around earnings (Jan/Apr/Jul/Oct):** capex 2nd-derivative, capex/OCF, cut-rewarded.
- **On a headline:** step-up (new raise), IPO status, contract renegotiation.
- **Occasionally:** index concentration (drifts slowly).

Most of the year these read `none` / `on_track` / green — you're waiting for the one that flips.

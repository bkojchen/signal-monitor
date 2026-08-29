# Where to get each manual signal

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

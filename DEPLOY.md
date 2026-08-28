# Make it live (self-hosting, self-updating)

Two ways, depending on whether you want a **URL** or **full privacy**.

## Option A — Hosted + auto-updating (GitHub Pages)   ← the "live URL" one

A scheduled job pulls fresh data every weekday morning and republishes the page. Nothing runs on
your machine. ~5 minutes to set up.

1. **Create a GitHub repo** and push this folder to it.
   ```bash
   git init && git add . && git commit -m "signal monitor"
   git branch -M main
   git remote add origin https://github.com/<you>/signal-monitor.git
   git push -u origin main
   ```
2. **Add your FRED key as a secret** (keeps it out of the code):
   repo → **Settings → Secrets and variables → Actions → New repository secret**
   Name `FRED_API_KEY`, value = your key. (Free key: https://fred.stlouisfed.org/docs/api/api_key.html)
3. **Turn on Pages**: **Settings → Pages → Build and deployment → Deploy from a branch →**
   branch `main`, folder `/docs` → Save.
4. **Kick the first run**: **Actions** tab → *Update dashboard* → **Run workflow**.
   When it finishes, your live page is at `https://<you>.github.io/signal-monitor/`.

From then on it refreshes itself on the schedule in `.github/workflows/update.yml`
(edit the `cron:` line to change timing). The open page also auto-reloads every 30 min.

**Updating your six manual readings:** edit `signals_manual.yaml` straight in GitHub's web editor
(pencil icon) and commit. That push re-runs the job and the live page updates within a minute — you
never need to touch a terminal.

> ⚠️ **Privacy:** a Pages site on a free/personal repo is **public** (the URL is unlisted, but
> reachable). This page shows only market indicators and your green/amber/red reads — no balances,
> no account data — so that's usually fine. If you'd rather it not be public at all, use Option B,
> or put the Pages URL behind Cloudflare Access.

## Option B — Live but fully private (your machine)

No hosting, nothing public. Rebuilds on an interval and serves locally with browser auto-refresh:

```bash
pip install -r requirements.txt      # add your FRED key to config.yaml (or export FRED_API_KEY)
python3 src/serve.py                  # → http://localhost:8777   (--every 600 for 10-min refresh)
```

Leave it running in a terminal tab (or as a background service). Same dashboard, same auto-refresh,
but it never leaves your laptop. Manual signals: edit `signals_manual.yaml`, it's picked up on the
next rebuild.

## Which to pick

- Want to glance at it from your phone anywhere → **Option A**.
- Want zero public footprint → **Option B**.
- You can run both: Pages for convenience, and keep the repo private if you're comfortable with the
  Pages-is-public caveat, or just don't enable Pages and rely on Actions to keep `data/history.csv`
  accumulating while you view locally.

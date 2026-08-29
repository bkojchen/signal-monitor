"""ETL orchestrator:  extract -> append history -> transform -> render dashboard."""
from __future__ import annotations
import argparse, json, os, shutil, sys

sys.path.insert(0, os.path.dirname(__file__))
import extract, transform, dashboard  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_config(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser(description="AI credit-cascade signal monitor")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--manual", default=os.path.join(ROOT, "signals_manual.yaml"))
    ap.add_argument("--output", default=os.path.join(ROOT, "output", "dashboard.html"))
    ap.add_argument("--mock", action="store_true",
                    help="skip network; use bundled sample history to preview the UI")
    ap.add_argument("--refresh", type=int, default=0,
                    help="auto-reload the page every N seconds (for hosted/live use)")
    ap.add_argument("--email", action="store_true", help="email the dashboard after building")
    ap.add_argument("--email-mode", choices=["always", "on-change"], default="always",
                    help="'on-change' only emails when the overall level worsens")
    args = ap.parse_args()

    config = load_config(args.config)
    # a FRED key in the environment (e.g. a GitHub Actions secret) beats config.yaml
    if os.environ.get("FRED_API_KEY"):
        config["fred_api_key"] = os.environ["FRED_API_KEY"]
    stale_after = load_config(args.manual).get("stale_after_days", 45)

    if args.mock:
        sample = os.path.join(ROOT, "data", "sample_history.csv")
        if os.path.exists(sample):
            shutil.copy(sample, extract.HISTORY)
        current = extract.load_manual(args.manual)
        current = {**{k: v for k, v in current.items() if isinstance(v, dict)}}
        print("• mock mode: using sample history + manual file")
    else:
        if "PUT_YOUR_FREE_FRED_KEY" in config.get("fred_api_key", ""):
            sys.exit("Set your free FRED key in config.yaml (or run with --mock to preview).")
        print("• extracting live data …")
        current = extract.run_extract(config, args.manual)

    history = extract.read_history()
    signals = transform.resolve_all(config, current, history, stale_after)
    overall = transform.overall_status(signals, config["playbook"])

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(dashboard.render(signals, overall, mock=args.mock,
                                 refresh_seconds=args.refresh))

    # machine-readable sibling, handy for alerts or a future API
    import datetime as _dt
    status_path = os.path.join(os.path.dirname(args.output), "status.json")
    with open(status_path, "w") as f:
        json.dump({"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                   "overall": overall,
                   "signals": [{"key": s["key"], "label": s["label"],
                                "status": s["status"], "value": s["value_str"]}
                               for s in signals]}, f, indent=2)

    print(f"• status: {overall['headline']}  "
          f"({overall['counts']['red']}R/{overall['counts']['amber']}A/{overall['counts']['green']}G)")
    print(f"• dashboard → {args.output}")

    if args.email:
        import notify
        cfg = notify.smtp_config()
        if not cfg:
            print("  ! --email set but SMTP env vars missing "
                  "(SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO) — skipping send")
        else:
            rank = {"green": 0, "amber": 1, "red": 2}
            last_file = os.path.join(ROOT, "data", "last_level.txt")
            last = ""
            if os.path.exists(last_file):
                last = open(last_file).read().strip()
            worsened = rank.get(overall["level"], 0) > rank.get(last, -1)
            if args.email_mode == "on-change" and not worsened:
                print(f"  · on-change mode: level {overall['level']} not worse than "
                      f"{last or 'none'} — no email")
            else:
                notify.send(overall, signals, args.output, cfg)
            os.makedirs(os.path.dirname(last_file), exist_ok=True)
            open(last_file, "w").write(overall["level"])


if __name__ == "__main__":
    main()

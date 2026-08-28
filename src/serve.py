"""Optional: run a live dashboard locally on http://localhost:8777

Rebuilds from fresh data on an interval and serves the page (which also
auto-reloads in the browser). Useful if you'd rather keep it fully private
on your own machine than publish to GitHub Pages.

    python3 src/serve.py                # every 30 min
    python3 src/serve.py --every 600    # every 10 min
"""
from __future__ import annotations
import argparse, http.server, os, socketserver, subprocess, sys, threading, time

ROOT = os.path.join(os.path.dirname(__file__), "..")
DOCS = os.path.join(ROOT, "docs")


def rebuild(refresh: int):
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "main.py"),
                    "--output", os.path.join(DOCS, "index.html"),
                    "--refresh", str(refresh)], check=False)


def loop(every: int):
    while True:
        print("• rebuilding …")
        rebuild(every)
        time.sleep(every)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=1800, help="seconds between rebuilds")
    ap.add_argument("--port", type=int, default=8777)
    args = ap.parse_args()

    os.makedirs(DOCS, exist_ok=True)
    rebuild(args.every)
    threading.Thread(target=loop, args=(args.every,), daemon=True).start()

    os.chdir(DOCS)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        print(f"• live at http://localhost:{args.port}  (Ctrl-C to stop)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()

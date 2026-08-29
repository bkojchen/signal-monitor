"""Email delivery: send an inbox-friendly summary + attach the full dashboard.

Config comes from environment variables (so they can be GitHub Actions secrets):
  SMTP_HOST  SMTP_PORT  SMTP_USER  SMTP_PASS  EMAIL_FROM  EMAIL_TO  [DASHBOARD_URL]
For Gmail: host=smtp.gmail.com port=465, and SMTP_PASS must be a 16-char App Password.
"""
from __future__ import annotations
import os, smtplib, ssl
from email.message import EmailMessage
from typing import List

BG = {"green": "#e7f0ea", "amber": "#f6edd8", "red": "#f6e2dc"}
FG = {"green": "#2f6b45", "amber": "#8a6414", "red": "#9e3320", "stale": "#6b7280"}


def smtp_config() -> dict | None:
    need = ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"]
    if not all(os.environ.get(k) for k in need):
        return None
    return {"host": os.environ["SMTP_HOST"], "port": int(os.environ.get("SMTP_PORT", 465)),
            "user": os.environ["SMTP_USER"], "pass": os.environ["SMTP_PASS"],
            "to": os.environ["EMAIL_TO"],
            "from": os.environ.get("EMAIL_FROM", os.environ["SMTP_USER"]),
            "url": os.environ.get("DASHBOARD_URL", "")}


def build_summary_html(overall: dict, signals: List[dict], url: str) -> str:
    lvl = overall["level"]
    rows = ""
    order = {"red": 0, "amber": 1, "green": 2, "stale": 3}
    for s in sorted(signals, key=lambda x: order.get(x["status"], 9)):
        fg = FG.get(s["status"], "#6b7280")
        rows += (
            f'<tr>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #eee;font:14px system-ui;">{s["label"]}</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #eee;font:13px ui-monospace,monospace;color:#444;">{s["value_str"]}</td>'
            f'<td style="padding:7px 10px;border-bottom:1px solid #eee;font:bold 12px system-ui;color:{fg};text-transform:uppercase;">{s["status"]}</td>'
            f'</tr>')
    link = (f'<p style="font:14px system-ui;"><a href="{url}" '
            f'style="color:#2563eb;">Open the live dashboard →</a></p>') if url else ""
    return f"""<div style="max-width:640px;margin:0 auto;font-family:system-ui,sans-serif;color:#1a1a1a;">
  <div style="background:{BG.get(lvl,'#eee')};border-left:6px solid {FG.get(lvl,'#666')};
       border-radius:10px;padding:18px 20px;margin-bottom:16px;">
    <div style="font-size:12px;letter-spacing:.08em;color:#666;">SYSTEM STATUS</div>
    <div style="font-size:30px;font-weight:700;color:{FG.get(lvl,'#666')};letter-spacing:.04em;">{overall['headline']}</div>
    <div style="font-size:13px;color:#555;margin-top:4px;">Driven by: {', '.join(overall['drivers']) or 'no active alerts'}</div>
  </div>
  <div style="background:#f7f7f5;border:1px solid #eee;border-radius:10px;padding:14px 16px;font:14px system-ui;margin-bottom:16px;">
    <b>Action:</b> {overall['action']}</div>
  {link}
  <table style="border-collapse:collapse;width:100%;margin-top:8px;">
    <tr><th align="left" style="font:11px system-ui;color:#888;padding:0 10px 6px;">SIGNAL</th>
        <th align="left" style="font:11px system-ui;color:#888;padding:0 10px 6px;">VALUE</th>
        <th align="left" style="font:11px system-ui;color:#888;padding:0 10px 6px;">STATUS</th></tr>
    {rows}
  </table>
  <p style="font:12px system-ui;color:#999;margin-top:18px;">Full dashboard attached. Not investment advice.</p>
</div>"""


def send(overall: dict, signals: List[dict], attachment: str, cfg: dict) -> None:
    html = build_summary_html(overall, signals, cfg.get("url", ""))
    subject = (f"[{overall['headline']}] AI monitor — "
               f"{overall['counts']['red']} red / {overall['counts']['amber']} amber")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"], msg["To"] = cfg["from"], cfg["to"]
    msg.set_content("This email needs an HTML-capable client. The dashboard is attached.")
    msg.add_alternative(html, subtype="html")
    if attachment and os.path.exists(attachment):
        with open(attachment, "rb") as f:
            msg.add_attachment(f.read(), maintype="text", subtype="html",
                               filename="dashboard.html")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx) as s:
        s.login(cfg["user"], cfg["pass"])
        s.send_message(msg)
    print(f"• emailed {cfg['to']}  ({subject})")

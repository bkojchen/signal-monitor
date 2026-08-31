"""Presentation layer: render a self-contained HTML instrument panel."""
from __future__ import annotations
import datetime as dt
from typing import List

# muted, non-default palette (ink panel + sage/ochre/brick status)
C = {
    "green": "#6f9e7b", "amber": "#cf9f52", "red": "#c85a44", "stale": "#5c6675",
}


def _spark(values: List[float], status: str, w=132, h=34) -> str:
    if len(values) < 2:
        return f'<svg width="{w}" height="{h}"></svg>'
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1
    pts = " ".join(
        f"{i/(len(values)-1)*(w-4)+2:.1f},{h-2-((v-lo)/rng)*(h-6):.1f}"
        for i, v in enumerate(values))
    col = C.get(status, "#5c6675")
    last_x = w - 2
    last_y = h - 2 - ((values[-1] - lo) / rng) * (h - 6)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{pts}" fill="none" stroke="{col}" '
            f'stroke-width="1.6" stroke-linejoin="round" opacity="0.9"/>'
            f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.4" fill="{col}"/></svg>')


def _card(s: dict) -> str:
    col = C.get(s["status"], "#5c6675")
    stale = ' <span class="stale">stale</span>' if s.get("stale") else ""
    cascade = ' <span class="tag">cascade</span>' if s.get("cascade") else ""
    change = (f'<span class="delta">{s["change_str"]}</span>'
              if s.get("change_str", "—") != "—" else "")
    if s.get("auto"):
        badge = f'<span class="src src-auto">● auto · {s.get("source","")}</span>'
    else:
        upd = f' · {s["updated"]}' if s.get("updated") else ""
        badge = f'<span class="src src-manual">✎ manual{upd}</span>'
    return f"""
    <article class="card" style="--c:{col}">
      <div class="card-top">
        <span class="eyebrow">{s['category']}{cascade}</span>
        <span class="dot"></span>
      </div>
      <h3>{s['label']}{stale}</h3>
      <div class="value">{s['value_str']} {change}</div>
      <div class="spark">{_spark(s.get('sparkline', []), s['status'])}</div>
      <div class="card-foot">
        <span class="trigger">{s['trigger']}</span>
        {badge}
      </div>
    </article>"""


def render(signals: List[dict], overall: dict, mock: bool = False,
           refresh_seconds: int = 0) -> str:
    lvl = overall["level"]
    col = C.get(lvl, "#5c6675")
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    build_epoch = dt.datetime.now(dt.timezone.utc).timestamp()
    refresh_meta = (f'<meta http-equiv="refresh" content="{refresh_seconds}">'
                    if refresh_seconds > 0 else "")
    if refresh_seconds > 0:
        mins = max(1, refresh_seconds // 60)
        live_pill = (f'<span class="live"><span class="live-dot"></span>LIVE'
                     f'<span class="live-sub">· auto-refresh {mins}m</span></span>')
    else:
        live_pill = ""
    drivers = " · ".join(overall["drivers"]) or "no active alerts"
    cn = overall["counts"]
    order = {"red": 0, "amber": 1, "green": 2, "stale": 3}
    cards = "".join(_card(s) for s in sorted(signals, key=lambda x: order.get(x["status"], 9)))
    mock_banner = ('<div class="mockbar">SAMPLE DATA — run without --mock and add your '
                   'FRED key for live readings</div>') if mock else ""
    stale_note = ""
    stale = [s["label"] for s in signals if s.get("stale")]
    if stale:
        stale_note = f'<p class="foot-warn">Stale manual inputs: {", ".join(stale)} — update signals_manual.yaml.</p>'

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Credit-Cascade Monitor</title>
{refresh_meta}
<style>
  :root {{ --ink:#0f131b; --panel:#161c27; --line:#232c3a; --text:#dfe4ec;
           --muted:#8a94a6; --c:{col}; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--ink); color:var(--text);
    font-family: system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; line-height:1.4; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:20px 18px 60px; }}
  .mono {{ font-family: ui-monospace,"SF Mono",Menlo,Consolas,monospace; }}
  .mockbar {{ background:#3a2f16; color:#e8c877; text-align:center; font-size:12px;
    letter-spacing:.04em; padding:7px; border-radius:8px; margin-bottom:16px; }}
  header {{ display:flex; justify-content:space-between; align-items:baseline;
    border-bottom:1px solid var(--line); padding-bottom:12px; margin-bottom:20px; }}
  header h1 {{ font-size:15px; font-weight:600; letter-spacing:.02em; margin:0; }}
  header .ts {{ color:var(--muted); font-size:12px; }}
  .live {{ display:inline-flex; align-items:center; gap:6px; color:#6f9e7b;
    font-size:11px; letter-spacing:.1em; margin-right:12px; }}
  .live-dot {{ width:7px; height:7px; border-radius:50%; background:#6f9e7b;
    animation:blink 1.8s infinite; }}
  .live-sub {{ color:var(--muted); letter-spacing:0; }}
  .age-fresh {{ color:#6f9e7b; }}
  .age-stale {{ color:#c85a44; font-weight:600; }}
  .stale-warn {{ display:none; background:#241310; color:#e0a08f; border:1px solid #5a2f24;
    border-radius:8px; padding:9px 13px; font-size:12.5px; margin-bottom:14px; }}
  @keyframes blink {{ 0%,100%{{opacity:1;}} 50%{{opacity:.25;}} }}
  @media (prefers-reduced-motion: reduce) {{ .live-dot {{ animation:none; }} }}

  /* signature: the status banner */
  .status {{ position:relative; background:var(--panel); border-radius:14px;
    padding:26px 26px 24px 30px; overflow:hidden; border:1px solid var(--line); }}
  .status::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:6px;
    background:var(--c); }}
  .status .head {{ display:flex; align-items:center; gap:16px; }}
  .status .beacon {{ width:18px; height:18px; border-radius:50%; background:var(--c);
    box-shadow:0 0 0 0 var(--c); animation:pulse 2.6s infinite; }}
  @keyframes pulse {{ 0%{{box-shadow:0 0 0 0 color-mix(in srgb,var(--c) 55%,transparent);}}
    70%{{box-shadow:0 0 0 14px transparent;}} 100%{{box-shadow:0 0 0 0 transparent;}} }}
  @media (prefers-reduced-motion: reduce) {{ .status .beacon {{ animation:none; }} }}
  .status .word {{ font-size:40px; font-weight:700; letter-spacing:.06em; color:var(--c); }}
  .status .counts {{ margin-left:auto; text-align:right; color:var(--muted); font-size:12px; }}
  .status .counts b {{ color:var(--text); }}
  .status .drivers {{ color:var(--muted); font-size:13px; margin:14px 0 16px; }}
  .status .drivers b {{ color:var(--text); font-weight:500; }}
  .status .action {{ font-size:14.5px; color:var(--text); background:#111722;
    border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}

  .section-label {{ color:var(--muted); font-size:11px; letter-spacing:.14em;
    text-transform:uppercase; margin:30px 2px 12px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
    padding:15px 16px 14px; --c:#5c6675; }}
  .card-top {{ display:flex; justify-content:space-between; align-items:center; }}
  .eyebrow {{ color:var(--muted); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; }}
  .tag {{ color:var(--c); border:1px solid var(--c); border-radius:20px; padding:1px 7px;
    font-size:9px; margin-left:5px; vertical-align:middle; }}
  .dot {{ width:10px; height:10px; border-radius:50%; background:var(--c); }}
  .card h3 {{ font-size:13.5px; font-weight:500; margin:9px 0 8px; color:var(--text); }}
  .stale {{ color:#5c6675; font-size:10px; border:1px solid #333c4b; border-radius:10px;
    padding:0 6px; margin-left:4px; }}
  .value {{ font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:23px;
    font-weight:600; color:var(--c); }}
  .delta {{ font-size:12px; color:var(--muted); margin-left:4px; }}
  .spark {{ margin:8px 0 6px; }}
  .card-foot {{ display:flex; justify-content:space-between; align-items:center; gap:8px;
    margin-top:2px; }}
  .trigger {{ color:var(--muted); font-size:11px; }}
  .src {{ font-size:9.5px; letter-spacing:.03em; padding:2px 7px; border-radius:20px;
    white-space:nowrap; }}
  .src-auto {{ color:#7fa8c9; border:1px solid #2c3e50; background:#141b26; }}
  .src-manual {{ color:#cf9f52; border:1px solid #443a24; background:#1c1810; }}
  .foot {{ color:var(--muted); font-size:12px; margin-top:34px; border-top:1px solid var(--line);
    padding-top:14px; }}
  .foot-warn {{ color:#cf9f52; }}
  a {{ color:#8fb3c9; }}
</style></head>
<body><div class="wrap">
  {mock_banner}
  <div id="staleWarn" class="stale-warn">⚠ This page is over a day old — the scheduled build likely didn't run. Open <b>Actions → Run workflow</b> to refresh.</div>
  <header>
    <h1>AI Credit-Cascade Monitor</h1>
    <span>{live_pill}<span class="ts mono" id="built" data-epoch="{build_epoch:.0f}">updated {now}</span></span>
  </header>

  <section class="status">
    <div class="head">
      <span class="beacon"></span>
      <span class="word">{overall['headline']}</span>
      <span class="counts"><b>{cn['red']}</b> red · <b>{cn['amber']}</b> amber · <b>{cn['green']}</b> green</span>
    </div>
    <p class="drivers">Driven by: <b>{drivers}</b></p>
    <div class="action">{overall['action']}</div>
  </section>

  <p class="section-label">Signals — worst first</p>
  <div class="grid">{cards}</div>

  <div class="foot">
    <p><span class="src src-auto">● auto</span> refreshes itself from a live feed (FRED / Yahoo).
       <span class="src src-manual">✎ manual</span> is hand-entered in <code>signals_manual.yaml</code> — see SOURCES.md for where to check each.</p>
    {stale_note}
    <p>Not investment advice. Thresholds are starting points — calibrate them, and confirm any action with your adviser/gestor.</p>
  </div>
</div>
<script>
(function(){{
  var el=document.getElementById('built');
  if(!el){{return;}}
  var epoch=parseFloat(el.getAttribute('data-epoch'))*1000;
  if(!epoch){{return;}}
  var built=new Date(epoch), ageH=(Date.now()-epoch)/3600000, rel;
  if(ageH<1){{rel=Math.max(1,Math.round(ageH*60))+' min ago';}}
  else if(ageH<24){{rel=Math.round(ageH)+'h ago';}}
  else {{rel=Math.round(ageH/24)+'d ago';}}
  var loc=built.toLocaleString([], {{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}});
  el.textContent='updated '+loc+' · '+rel;
  el.classList.add(ageH>=24?'age-stale':'age-fresh');
  if(ageH>=24){{var w=document.getElementById('staleWarn'); if(w){{w.style.display='block';}}}}
}})();
</script>
</body></html>"""

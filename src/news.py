"""News watcher: auto-FLAG (not auto-value) event-driven manual signals.

For each signal with a `news_query`, it checks Google News RSS (free, no key) and,
if fresh matching headlines exist, marks that signal "needs review" with the latest
headline + link. You still set the value — this just tells you WHEN to look, so the
event-driven signals stop going stale silently.
"""
from __future__ import annotations
import datetime as dt, urllib.parse
import xml.etree.ElementTree as ET


def _fetch_rss(query: str) -> str:
    import requests
    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en")
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 signal-monitor"}, timeout=30)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def parse_items(xml_text: str) -> list:
    items = []
    if not xml_text:
        return items
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return items
    for it in root.iter("item"):
        items.append({"title": it.findtext("title", ""),
                      "link": it.findtext("link", ""),
                      "pub": it.findtext("pubDate", "")})
    return items


def _recent(items: list, days: int) -> list:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = []
    for it in items:
        d = None
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                d = dt.datetime.strptime(it["pub"], fmt)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=dt.timezone.utc)
                break
            except Exception:
                continue
        if d is None or d >= cutoff:      # keep if fresh or undated
            out.append(it)
    return out


def check(queries: dict, days: int = 14, fetcher=_fetch_rss) -> dict:
    """queries: {signal: query}. Returns {signal: {count, headline, url}} for hits only."""
    results = {}
    for sig, q in queries.items():
        items = _recent(parse_items(fetcher(q)), days)
        if items:
            results[sig] = {"count": len(items),
                            "headline": items[0]["title"][:140],
                            "url": items[0]["link"]}
    return results

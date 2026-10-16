"""RSS/Atom feeds plus Google News RSS searches."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import date, datetime
from typing import Iterator
from urllib.parse import quote_plus

import feedparser

from ..http import BROWSER_UA, get, session
from . import make_event, since_date

log = logging.getLogger(__name__)
GNEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
TAG_RE = re.compile(r"<[^>]+>")


def _strip(html: str) -> str:
    return TAG_RE.sub(" ", html or "")


def _published(entry) -> str:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return ""
    return datetime(*t[:6]).date().isoformat()


def _entries(s, url: str) -> list:
    r = get(s, url, headers={"User-Agent": BROWSER_UA})
    if r.status_code != 200:
        log.warning("feed %s returned %s", url, r.status_code)
        return []
    return feedparser.parse(r.content).entries


def _emit(entry, *, feed_name: str, category: str, since: date, query: str | None) -> dict | None:
    link = entry.get("link", "")
    pub = _published(entry)
    if pub and pub < since.isoformat():
        return None
    title = entry.get("title", "")
    # Google News wraps the publisher in the title: "Headline - Publisher"
    publisher = (entry.get("source") or {}).get("title") if query else feed_name
    key = entry.get("id") or link or title
    eid = "rss:" + hashlib.sha1(key.encode()).hexdigest()[:16]
    return make_event(
        id=eid, source="rss", category=category, title=title, url=link, published=pub,
        summary=_strip(entry.get("summary", ""))[:1500],
        feed=feed_name, publisher=publisher, query=query,
    )


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    rc = cfg["rss"]
    since = since_date(rc.get("lookback_days", 3))
    s = session()
    for feed in rc.get("feeds", []):
        try:
            for e in _entries(s, feed["url"]):
                ev = _emit(e, feed_name=feed["name"], category=feed.get("category", "news"), since=since, query=None)
                if ev:
                    yield ev
        except Exception as ex:  # noqa: BLE001
            log.error("feed %s failed: %s", feed["name"], ex)
        time.sleep(0.5)
    for q in rc.get("google_news_queries", []):
        try:
            for e in _entries(s, GNEWS.format(q=quote_plus(q))):
                ev = _emit(e, feed_name="Google News", category="news", since=since, query=q)
                if ev:
                    yield ev
        except Exception as ex:  # noqa: BLE001
            log.error("google news %r failed: %s", q, ex)
        time.sleep(1.0)

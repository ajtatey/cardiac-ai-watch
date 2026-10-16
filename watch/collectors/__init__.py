"""Collector registry. Each collector is `fn(cfg, state) -> Iterator[event]`.

An event is a dict with at least: id, source, category, title, url,
published (YYYY-MM-DD or ""), summary. Extra fields go under `extra`.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Iterator

Collector = Callable[[dict, dict], Iterator[dict]]


def since_date(days: int) -> date:
    return date.today() - timedelta(days=days)


def make_event(*, id: str, source: str, category: str, title: str, url: str,
               published: str, summary: str, **extra) -> dict:
    return {
        "id": id,
        "source": source,
        "category": category,
        "title": " ".join((title or "").split())[:300],
        "url": url or "",
        "published": published or "",
        "summary": " ".join((summary or "").split())[:4000],
        "extra": extra,
    }


def registry() -> dict[str, Collector]:
    from . import clinicaltrials, edgar, fda_510k, fda_recalls, federal_register, pubmed, rss
    return {
        "fda_510k": fda_510k.collect,
        "fda_recalls": fda_recalls.collect,
        "pubmed": pubmed.collect,
        "clinicaltrials": clinicaltrials.collect,
        "federal_register": federal_register.collect,
        "edgar": edgar.collect,
        "rss": rss.collect,
    }

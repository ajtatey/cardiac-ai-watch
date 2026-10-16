"""Federal Register documents from CMS and FDA matching the configured terms."""
from __future__ import annotations

import logging
from typing import Iterator

from ..http import get, session
from . import make_event, since_date

log = logging.getLogger(__name__)
URL = "https://www.federalregister.gov/api/v1/documents.json"
FIELDS = ["document_number", "title", "type", "abstract", "publication_date", "html_url", "agencies", "action", "docket_ids"]


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    fr = cfg["federal_register"]
    since = since_date(fr.get("lookback_days", 14)).isoformat()
    s = session("cardiac-ai-watch/1.0")
    seen: set[str] = set()
    for term in fr["terms"]:
        params = [("conditions[term]", term), ("conditions[publication_date][gte]", since),
                  ("order", "newest"), ("per_page", "100")]
        params += [("conditions[agencies][]", a) for a in fr.get("agencies", [])]
        params += [("fields[]", f) for f in FIELDS]
        try:
            r = get(s, URL, params=params)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception as e:  # noqa: BLE001
            log.error("federal register %s failed: %s", term, e)
            continue
        for d in results:
            dn = d.get("document_number")
            if not dn or dn in seen:
                continue
            seen.add(dn)
            agencies = [a.get("name") or a.get("raw_name") for a in d.get("agencies", [])]
            is_cms = any("Medicare" in (a or "") for a in agencies)
            yield make_event(
                id=f"fedreg:{dn}",
                source="federal_register",
                category="reimbursement" if is_cms else "regulatory",
                title=f"{d.get('type')}: {d.get('title')}",
                url=d.get("html_url", ""),
                published=d.get("publication_date", ""),
                summary=f"{'; '.join(a for a in agencies if a)}. {d.get('action') or ''} {d.get('abstract') or ''}",
                document_type=d.get("type"), agencies=agencies, matched_term=term,
                docket_ids=d.get("docket_ids"),
            )

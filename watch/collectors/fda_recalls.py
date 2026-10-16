"""FDA device recalls from openFDA for watched product codes and companies."""
from __future__ import annotations

import logging
import os
from typing import Iterator

from ..http import get, session
from . import make_event, since_date

log = logging.getLogger(__name__)
URL = "https://api.fda.gov/device/recall.json"


def _query(s, search: str) -> list[dict]:
    params = {"search": search, "limit": 100}
    if os.environ.get("OPENFDA_API_KEY"):
        params["api_key"] = os.environ["OPENFDA_API_KEY"]
    r = get(s, URL, params=params)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json().get("results", [])


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    s = session()
    since = since_date(365).strftime("%Y%m%d")
    searches = [f"product_code:{c}" for c in cfg["fda"].get("product_codes", [])]
    searches += [f'recalling_firm:"{c["fda_applicant"]}"' for c in cfg["companies"] if c.get("fda_applicant")]
    seen: set[str] = set()
    for q in searches:
        try:
            recs = _query(s, q)
        except Exception as e:  # noqa: BLE001
            log.error("openFDA recall %s failed: %s", q, e)
            continue
        for rec in recs:
            rid = rec.get("res_event_number") or rec.get("product_res_number") or rec.get("cfres_id")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            initiated = (rec.get("event_date_initiated") or "").replace("-", "")
            if initiated and initiated < since:
                continue
            firm = rec.get("recalling_firm", "")
            yield make_event(
                id=f"fdarecall:{rid}",
                source="fda_recalls",
                category="safety",
                title=f"FDA recall: {firm} — {rec.get('product_description', '')[:120]}",
                url=f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfres/res.cfm?id={rec.get('cfres_id', '')}",
                published=rec.get("event_date_initiated", ""),
                summary=f"{rec.get('recall_status', '')}. Reason: {rec.get('reason_for_recall', '')} "
                        f"Action: {rec.get('action', '')} Product code {rec.get('product_code')}.",
                recalling_firm=firm,
                product_code=rec.get("product_code"),
                raw=rec,
            )

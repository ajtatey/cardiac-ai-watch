"""SEC EDGAR: filings by tracked public companies, plus full-text search hits
for tracked names across every filer (e.g. a competitor named in a 10-K)."""
from __future__ import annotations

import logging
import time
from typing import Iterator

from ..http import SEC_UA, get, session
from . import make_event, since_date

log = logging.getLogger(__name__)
FTS = "https://efts.sec.gov/LatestSearchResults"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


def _doc_url(cik: str, adsh: str, filename: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{filename}"


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    ed = cfg["edgar"]
    since = since_date(ed.get("lookback_days", 7)).isoformat()
    s = session(SEC_UA)
    seen: set[str] = set()

    # Company filings for tracked CIKs
    for c in cfg["companies"]:
        cik = c.get("edgar_cik")
        if not cik:
            continue
        try:
            r = get(s, SUBMISSIONS.format(cik=cik.zfill(10)))
            r.raise_for_status()
            rec = r.json().get("filings", {}).get("recent", {})
        except Exception as e:  # noqa: BLE001
            log.error("edgar submissions %s failed: %s", cik, e)
            continue
        for i, adsh in enumerate(rec.get("accessionNumber", [])):
            fdate = rec["filingDate"][i]
            if fdate < since or adsh in seen:
                continue
            seen.add(adsh)
            form = rec["form"][i]
            doc = rec.get("primaryDocument", [""])[i]
            yield make_event(
                id=f"edgar:{adsh}",
                source="edgar",
                category="financial",
                title=f"{c['name']} filed {form}: {rec.get('primaryDocDescription', [''])[i] or doc}",
                url=_doc_url(cik, adsh, doc) if doc else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
                published=fdate,
                summary=f"SEC filing {form} by {c['name']} (CIK {cik}). Items: {rec.get('items', [''])[i]}",
                company=c["slug"], form=form, accession=adsh,
            )
        time.sleep(0.3)

    # Full-text search for tracked names across all filers
    for term in ed.get("fulltext_terms", []):
        params = {"q": term, "dateRange": "custom", "startdt": since, "enddt": "2099-12-31"}
        try:
            r = get(s, FTS, params=params)
            r.raise_for_status()
            hits = r.json().get("hits", {}).get("hits", [])
        except Exception as e:  # noqa: BLE001
            # efts.sec.gov returns 403 from some networks; filings for tracked
            # CIKs above still work. Log once per run and move on.
            log.warning("edgar fulltext search unavailable (%s); skipping remaining terms", e)
            break
        for h in hits:
            src = h.get("_source", {})
            hid = h.get("_id", "")  # "adsh:filename"
            adsh = hid.split(":")[0]
            if not adsh or adsh in seen:
                continue
            seen.add(adsh)
            ciks = src.get("ciks", [])
            names = src.get("display_names", [])
            filename = hid.split(":", 1)[1] if ":" in hid else ""
            yield make_event(
                id=f"edgar:{adsh}",
                source="edgar",
                category="financial",
                title=f"{'; '.join(names[:2])} filed {src.get('form')} mentioning {term}",
                url=_doc_url(ciks[0], adsh, filename) if ciks and filename else "https://efts.sec.gov/LatestSearchResults",
                published=src.get("file_date", ""),
                summary=f"Full-text hit for {term} in {src.get('form')} ({src.get('file_description', '')}). Filers: {'; '.join(names)}.",
                form=src.get("form"), accession=adsh, matched_term=term, filers=names,
            )
        time.sleep(0.3)

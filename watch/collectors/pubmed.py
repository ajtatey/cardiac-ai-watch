"""New PubMed records matching the configured queries (NCBI E-utilities)."""
from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import Iterator

from ..http import get, session
from . import make_event

log = logging.getLogger(__name__)
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def _params(**kw) -> dict:
    kw.setdefault("db", "pubmed")
    kw.setdefault("tool", "cardiac-ai-watch")
    kw.setdefault("email", "andrew@argot.dev")
    if os.environ.get("NCBI_API_KEY"):
        kw["api_key"] = os.environ["NCBI_API_KEY"]
    return kw


def _search(s, term: str, days: int) -> list[str]:
    r = get(s, BASE + "esearch.fcgi", params=_params(term=term, reldate=days, datetype="edat", retmode="json", retmax=300))
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def _fetch(s, pmids: list[str]) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        r = get(s, BASE + "efetch.fcgi", params=_params(id=",".join(chunk), retmode="xml"))
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID") or ""
            title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
            abstract = " ".join("".join(a.itertext()) for a in art.findall(".//Abstract/AbstractText"))
            journal = art.findtext(".//Journal/Title") or art.findtext(".//MedlineTA") or ""
            year = art.findtext(".//JournalIssue/PubDate/Year") or art.findtext(".//ArticleDate/Year") or ""
            month = art.findtext(".//ArticleDate/Month") or art.findtext(".//JournalIssue/PubDate/Month") or "01"
            day = art.findtext(".//ArticleDate/Day") or art.findtext(".//JournalIssue/PubDate/Day") or "01"
            doi = next((e.text for e in art.findall(".//ArticleId") if e.get("IdType") == "doi"), None)
            authors = [f"{a.findtext('LastName') or ''} {a.findtext('Initials') or ''}".strip() for a in art.findall(".//Author")[:6]]
            pub_types = [pt.text for pt in art.findall(".//PublicationType") if pt.text]
            affiliations = [af.text for af in art.findall(".//AffiliationInfo/Affiliation") if af.text][:5]
            try:
                published = f"{int(year):04d}-{int(month) if month.isdigit() else 1:02d}-{int(day):02d}" if year else ""
            except ValueError:
                published = year
            out.append({
                "pmid": pmid, "title": title, "abstract": abstract, "journal": journal,
                "published": published, "doi": doi, "authors": authors,
                "pub_types": pub_types, "affiliations": affiliations,
            })
        time.sleep(0.4)
    return out


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    pm = cfg["pubmed"]
    s = session("cardiac-ai-watch/1.0")
    pmids: list[str] = []
    for q in pm["queries"]:
        try:
            pmids.extend(_search(s, q, pm.get("lookback_days", 5)))
        except Exception as e:  # noqa: BLE001
            log.error("pubmed search failed: %s", e)
        time.sleep(0.4)
    pmids = list(dict.fromkeys(pmids))
    if not pmids:
        return
    for a in _fetch(s, pmids):
        yield make_event(
            id=f"pubmed:{a['pmid']}",
            source="pubmed",
            category="clinical",
            title=a["title"],
            url=f"https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/",
            published=a["published"],
            summary=f"{a['journal']}. {', '.join(a['authors'])}. {a['abstract']}",
            journal=a["journal"], doi=a["doi"], authors=a["authors"],
            pub_types=a["pub_types"], affiliations=a["affiliations"],
        )

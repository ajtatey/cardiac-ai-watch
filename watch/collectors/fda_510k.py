"""FDA 510(k) / De Novo records from openFDA, by product code and by applicant.

Also downloads the FDA summary PDF for each record and extracts its text so
triage can read the indications for use without opening the PDF.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

from ..config import FDA_DOCS_DIR
from ..http import BROWSER_UA, get, session
from . import make_event, since_date

log = logging.getLogger(__name__)

OPENFDA = "https://api.fda.gov/device/510k.json"
PDF_510K = "https://www.accessdata.fda.gov/cdrh_docs/pdf{yy}/{k}.pdf"
PDF_DEN = "https://www.accessdata.fda.gov/cdrh_docs/reviews/{k}.pdf"
DETAIL_510K = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={k}"
DETAIL_DEN = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?ID={k}"


def is_de_novo(k: str) -> bool:
    return k.upper().startswith("DEN")


def pdf_url(k: str) -> str:
    return PDF_DEN.format(k=k) if is_de_novo(k) else PDF_510K.format(yy=k[1:3], k=k)


def detail_url(k: str) -> str:
    return (DETAIL_DEN if is_de_novo(k) else DETAIL_510K).format(k=k)


def _query(s, search: str, api_key: str | None) -> list[dict]:
    out: list[dict] = []
    params = {"search": search, "limit": 100, "skip": 0, "sort": "decision_date:desc"}
    if api_key:
        params["api_key"] = api_key
    while True:
        r = get(s, OPENFDA, params=params)
        if r.status_code == 404:
            break
        r.raise_for_status()
        body = r.json()
        page = body.get("results", [])
        out.extend(page)
        total = body.get("meta", {}).get("results", {}).get("total", 0)
        params["skip"] += len(page)
        if not page or params["skip"] >= total:
            break
    return out


def fetch_summary(k: str, s) -> tuple[str | None, str | None]:
    """Download the summary PDF and extract text. Returns (pdf_relpath, text_relpath)."""
    FDA_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = FDA_DOCS_DIR / f"{k}.pdf"
    txt_path = FDA_DOCS_DIR / f"{k}.txt"
    if not pdf_path.exists():
        r = get(s, pdf_url(k), headers={"User-Agent": BROWSER_UA}, allow_redirects=True)
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            log.info("%s: summary PDF not available yet (%s)", k, r.status_code)
            return None, None
        pdf_path.write_bytes(r.content)
        time.sleep(1)
    if not txt_path.exists():
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:12])
            txt_path.write_text(text[:30000])
        except Exception as e:  # noqa: BLE001
            log.warning("%s: text extraction failed: %s", k, e)
            return str(pdf_path.relative_to(FDA_DOCS_DIR.parent.parent)), None
    root = FDA_DOCS_DIR.parent.parent
    return str(pdf_path.relative_to(root)), str(txt_path.relative_to(root))


def _event(rec: dict, matched_company: str | None, s) -> dict:
    k = rec["k_number"]
    openfda = rec.get("openfda") or {}
    has_summary = rec.get("statement_or_summary") == "Summary" or is_de_novo(k)
    pdf_rel, txt_rel = (None, None)
    if has_summary:
        pdf_rel, txt_rel = fetch_summary(k, s)
    kind = "De Novo grant" if is_de_novo(k) else "510(k) clearance"
    summary = (
        f"{kind}. Applicant: {rec.get('applicant')}. Device: {rec.get('device_name')}. "
        f"Product code {rec.get('product_code')} ({openfda.get('device_name')}), "
        f"regulation {openfda.get('regulation_number')}, class {openfda.get('device_class')}. "
        f"Decision {rec.get('decision_date')} ({rec.get('decision_description')}), "
        f"received {rec.get('date_received')}, {rec.get('clearance_type')} pathway. "
        f"Filed as {rec.get('statement_or_summary') or 'n/a'}."
    )
    return make_event(
        id=f"fda510k:{k}",
        source="fda_510k",
        category="regulatory",
        title=f"FDA {kind}: {rec.get('applicant')} — {rec.get('device_name')} ({k})",
        url=detail_url(k),
        published=rec.get("decision_date", ""),
        summary=summary,
        k_number=k,
        applicant=rec.get("applicant"),
        device_name=rec.get("device_name"),
        product_code=rec.get("product_code"),
        regulation_number=openfda.get("regulation_number"),
        decision_date=rec.get("decision_date"),
        matched_company=matched_company,
        summary_pdf_url=pdf_url(k) if has_summary else None,
        summary_pdf_path=pdf_rel,
        summary_text_path=txt_rel,
        raw=rec,
    )


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    import os
    api_key = os.environ.get("OPENFDA_API_KEY")
    fda = cfg["fda"]
    since = since_date(fda.get("lookback_days", 120)).strftime("%Y%m%d")
    s = session()
    seen: set[str] = set()

    # 1. Tracked companies by applicant name: full history (older records are
    #    flagged historical so the CLI can store them without alerting).
    for c in cfg["companies"]:
        q = c.get("fda_applicant")
        if not q:
            continue
        try:
            recs = _query(s, f'applicant:"{q}"', api_key)
        except Exception as e:  # noqa: BLE001
            log.error("openFDA applicant %s failed: %s", q, e)
            continue
        for rec in recs:
            k = rec["k_number"]
            if k in seen:
                continue
            seen.add(k)
            ev = _event(rec, c["slug"], s)
            ev["extra"]["historical"] = rec.get("decision_date", "").replace("-", "") < since
            yield ev

    # 2. Product codes within the lookback window.
    for code in fda.get("product_codes", []):
        try:
            recs = _query(s, f"product_code:{code} AND decision_date:[{since} TO 20991231]", api_key)
        except Exception as e:  # noqa: BLE001
            log.error("openFDA product code %s failed: %s", code, e)
            continue
        for rec in recs:
            k = rec["k_number"]
            if k in seen:
                continue
            seen.add(k)
            ev = _event(rec, None, s)
            ev["extra"]["historical"] = False
            yield ev

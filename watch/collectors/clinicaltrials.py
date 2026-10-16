"""ClinicalTrials.gov v2: studies updated recently that match the queries.

The event id includes the last-update date so a status change on a known
trial surfaces as a new event.
"""
from __future__ import annotations

import logging
from typing import Iterator

from ..http import get, session
from . import make_event, since_date

log = logging.getLogger(__name__)
URL = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OfficialTitle", "OverallStatus", "LastUpdatePostDate", "StudyFirstPostDate",
    "LeadSponsorName", "Condition", "InterventionName", "BriefSummary", "StartDate",
    "PrimaryCompletionDate", "EnrollmentCount", "StudyType", "Phase", "WhyStopped",
])


def collect(cfg: dict, state: dict) -> Iterator[dict]:
    ct = cfg["clinicaltrials"]
    since = since_date(ct.get("lookback_days", 7)).isoformat()
    s = session("cardiac-ai-watch/1.0")
    seen: set[str] = set()
    for q in ct["queries"]:
        params = {
            "query.term": q,
            "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{since},MAX]",
            "fields": FIELDS, "pageSize": 100, "countTotal": "true",
        }
        try:
            r = get(s, URL, params=params)
            r.raise_for_status()
            studies = r.json().get("studies", [])
        except Exception as e:  # noqa: BLE001
            log.error("clinicaltrials query failed: %s", e)
            continue
        for st in studies:
            p = st.get("protocolSection", {})
            ident, status = p.get("identificationModule", {}), p.get("statusModule", {})
            nct = ident.get("nctId")
            upd = (status.get("lastUpdatePostDateStruct") or {}).get("date", "")
            key = f"{nct}:{upd}"
            if not nct or key in seen:
                continue
            seen.add(key)
            sponsor = (p.get("sponsorCollaboratorsModule", {}).get("leadSponsor") or {}).get("name", "")
            conds = p.get("conditionsModule", {}).get("conditions", [])
            intervs = [i.get("name") for i in p.get("armsInterventionsModule", {}).get("interventions", []) if i.get("name")]
            design = p.get("designModule", {})
            first_post = (status.get("studyFirstPostDateStruct") or {}).get("date", "")
            is_new = first_post >= since
            summary = (
                f"{'NEW REGISTRATION' if is_new else 'UPDATED'} — status {status.get('overallStatus')}. "
                f"Sponsor: {sponsor}. Conditions: {', '.join(conds[:5])}. Interventions: {', '.join(intervs[:5])}. "
                f"Type {design.get('studyType')}, enrollment {(design.get('enrollmentInfo') or {}).get('count')}. "
                f"Start {(status.get('startDateStruct') or {}).get('date')}, primary completion "
                f"{(status.get('primaryCompletionDateStruct') or {}).get('date')}. "
                f"{('Stopped: ' + status['whyStopped'] + '. ') if status.get('whyStopped') else ''}"
                f"{p.get('descriptionModule', {}).get('briefSummary', '')}"
            )
            yield make_event(
                id=f"ctgov:{key}",
                source="clinicaltrials",
                category="trial",
                title=f"{ident.get('briefTitle')} ({nct})",
                url=f"https://clinicaltrials.gov/study/{nct}",
                published=upd,
                summary=summary,
                nct_id=nct, status=status.get("overallStatus"), sponsor=sponsor,
                new_registration=is_new, conditions=conds, interventions=intervs,
            )

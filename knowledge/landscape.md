# Landscape: AI coronary CT in the US

_One-page view, agent-maintained. Last reviewed 2026-10-17. Every row cites its source; details live in `knowledge/companies/`._

## Who has what cleared (CCTA plaque, physiology, prognosis)

| Company | Plaque quantification | CT-FFR (PJA) | Ischemia / prognosis | Latest action |
|---|---|---|---|---|
| Cleerly | Cleerly Plaque v1.0, [K261210](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K261210) (2026-07-29); LABS v3.0 [K260588](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K260588) | none | Cleerly ISCHEMIA, [K231335](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K231335) (QXZ, 2023) | 2026-07-29 |
| HeartFlow | Heartflow Analysis incl. plaque, [K250902](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K250902) (2025-07-18) | FFRct, De Novo [DEN130045](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?ID=DEN130045) (2014) onward | "risk assessment" wording in K250902 | 2025-07-18 |
| Elucid | PlaqueIQ, [K261855](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K261855) (2026-09-18) | FFR-IQ, [K262015](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K262015) (2026-09-29), second PJA holder | none | 2026-09-29 |
| Caristo | CaRi-Plaque, [K242240](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K242240) (2025-02-20) | none | CaRi-Heart De Novo [DEN250042](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?ID=DEN250042) (2026-07-28), new code SIU, 21 CFR 870.2215 | 2026-07-28 |
| Siemens Healthineers | syngo.CT Coronary Cockpit, [K253786](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K253786) (2026-06-25), console-bundled; predicate Cleerly Labs v2.0 | none | none | 2026-06-25 |
| Keya Medical | DEEPVESSEL Plaque, [K260497](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K260497) (2026-06-04) | none in US | none | 2026-06-04 |
| Circle CVI | cvi42 Coronary Plaque, [K251027](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K251027) (2025-10-27) | none | none | 2025-10-27 |
| Artrya | Salix Coronary Plaque, [K251837](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K251837) (2025-08-20) | none | none | 2025-08-20 |

Predicate chains worth knowing: Autoplaque (Cedars-Sinai, K122429 / K212758) anchors Elucid, Caristo, Keya and HeartFlow's plaque feature; Caristo CaRi-Plaque anchors Artrya; Cleerly Labs v2.0 anchors Siemens Coronary Cockpit.

## Where the codes stand

- **Plaque analysis: CPT 75577**, Category I, effective 2026-01-01 (Category III from 2021). Vendor-reported 2026 national averages about $1,012-1,021 office/IDTF and about $951 OPPS. Aetna, Humana, Cigna and UnitedHealthcare cover. Sources: [AuntMinnie](https://www.auntminnie.com/clinical-news/ct/news/15772754/cms-finalizes-medicare-reimbursement-for-caristos-coronary-plaque-analysis), [Elucid](https://businesswire.com/news/home/20251203262228/en/Elucid-Gains-Broad-CMS-Reimbursement-of-Coronary-Plaque-Analysis-Using-PlaqueIQ), [HeartFlow](https://heartflow.com/newsroom/heartflow-announces-new-category-i-cpt-code).
- **FFR-CT: CPT 75580**, Category I since 2024-01-01, replacing 0501T-0504T. OPPS APC 5724, $1,017 in CY2025 (HeartFlow-reported). Elucid can now bill it too. Sources: [AuntMinnie](https://www.auntminnie.com/clinical-news/ct/article/15662727/new-cpt-code-issued-for-ffrct), [HeartFlow payer guide](https://www.heartflow.com/wp-content/uploads/2025/02/cat-i-transition-for-payers.pdf), [Cleerly billing guidance](https://cleerlyhealth.com/reimbursement-guidelines).
- **Underlying scan:** Medicare physician payment for cardiac CT fell across 2010-2026 despite CCTA's Class 1 guideline status ([JCCT, PubMed 42859062](https://pubmed.ncbi.nlm.nih.gov/42859062/)).
- **Prognosis (SIU):** no CPT code yet for CaRi-Heart-type long-term risk prediction.

## Trials to watch (CCTA plaque as endpoint)

Completion dates are not yet captured by the collector; check the registry entries.

- Eli Lilly lepodisiran plaque study in elevated Lp(a), recruiting: [NCT07613294](https://clinicaltrials.gov/study/NCT07613294)
- Mazdutide coronary plaque study, China NCCD, recruiting: [NCT07657676](https://clinicaltrials.gov/study/NCT07657676)
- Baylor ProActive Athlete Heart Program, CCTA screening, not yet recruiting: [NCT07460583](https://clinicaltrials.gov/study/NCT07460583)
- PICCOLETO XIII REVEAL-DCB, new registration: [NCT07868523](https://clinicaltrials.gov/study/NCT07868523)

Drug trials using CCTA plaque endpoints are a demand channel for core-lab plaque quantification; check which vendor each one uses.

## Open items

- CaRi-Heart decision summary (special controls for SIU) not yet posted.
- What K261855 changed versus PlaqueIQ K241524.
- Whether Elucid announces 75580 billing or a combined plaque-plus-FFR report.

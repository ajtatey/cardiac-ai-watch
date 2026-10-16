# Cardiac AI Watch

An agent-run intelligence desk for AI in cardiac imaging: coronary CT plaque
and FFR-CT, calcium scoring, pericoronary inflammation, cardiac MRI and echo
AI, and the regulatory, reimbursement, evidence and business landscape around
them. Built for Cleerly; tracks HeartFlow, Elucid, Caristo, Artrya and about
twenty others by name, and the whole field by FDA product code and topic.

## How it works

```
 collectors (code, every 30 min)      triage (agent, hourly)        delivery (code)
 ───────────────────────────────      ───────────────────────       ─────────────────────────
 openFDA 510(k)/De Novo by code  ─┐                               ┌─ P0 → alert email now
 openFDA recalls                  │   new events → relevance,     │
 PubMed                           ├─▶ priority, summary,      ───┼─ P1/P2 → morning brief
 ClinicalTrials.gov               │   why-it-matters, dossiers    │          (7am ET)
 Federal Register (CMS, FDA)      │                               └─ P3 → counted only
 SEC EDGAR                        │
 RSS + Google News               ─┘   editor (agent, daily) → editorial note for the brief
```

- **Store**: one JSON file per kept event under `data/events/`, an index in
  `data/index.json`, FDA summary text under `data/fda_summaries/`. All in git,
  so every decision is auditable.
- **Triage** has two interchangeable paths: a Claude Code cloud routine that
  follows `AGENT.md`, or a scripted call to the Claude API when
  `ANTHROPIC_API_KEY` is set (`python -m watch triage`).
- **Knowledge base**: `knowledge/companies/<slug>.md` dossiers. The regulatory
  table is auto-generated; the prose is agent-maintained.
- **Email** goes through Resend. Alerts for P0 events go out within 30 minutes
  of triage; the brief goes out daily.

## Commands

```sh
python -m watch collect                 # run all collectors (or --only pubmed rss)
python -m watch triage --export p.json  # pending events for an agent
python -m watch triage --apply r.json   # write an agent's decisions
python -m watch triage                  # scripted triage via Claude API (needs key)
python -m watch alerts [--dry-run]      # email P0s not yet alerted
python -m watch brief [--dry-run]       # compose + send the brief, mark items reported
python -m watch knowledge               # refresh dossier tables
python -m watch status
```

Local setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`,
and a `.env` with `RESEND_API_KEY=...` (never committed).

## Configuration

Everything lives in `config.yaml`: companies and aliases, FDA product codes,
PubMed and ClinicalTrials queries, feeds and Google News queries, Federal
Register terms, email routing, and the P0 definition. Add a company by adding
an entry; add a source by adding a collector in `watch/collectors/` and
registering it in `watch/collectors/__init__.py`.

## Scheduling

- `.github/workflows/collect.yml`: twice an hour. Collect, scripted triage if a
  key is present, send P0 alerts, refresh dossiers, commit.
- `.github/workflows/brief.yml`: daily 11:00 UTC. Compose and send the brief, commit.
- Claude Code cloud routines (see `AGENT.md`): hourly triage analyst, daily editor.

Secrets: `RESEND_API_KEY` (set). Optional: `ANTHROPIC_API_KEY` for scripted
triage, `OPENFDA_API_KEY`, `NCBI_API_KEY`. Repo variable `EMAIL_TO` overrides
the recipient list in `config.yaml`.

## Known limits

- openFDA refreshes weekly, so a clearance appears a few days after decision.
- SEC full-text search returns 403 from some networks; company filings by CIK still work.
- FDA summary PDFs are kept locally but not committed; the extracted text is.
- Google News RSS is the fallback for trade sites that block feed readers.

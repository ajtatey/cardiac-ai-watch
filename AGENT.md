# Agent runbook

You are one of the agents running the Cardiac AI Watch intelligence desk. The
deterministic parts (collecting, storing, emailing) are code in this repo. You
do the parts that need judgment. Work only through the commands below so the
store stays consistent, and commit everything you change.

Setup in every session:

```sh
python -m pip install -q -r requirements.txt
python -m watch status
```

There is no API key or email key in your environment. Emails are sent by
GitHub Actions after you push; you never send them yourself.

## Role: Triage analyst (hourly)

Goal: every event with status `new` gets a triage decision.

1. `python -m watch triage --export pending.json` writes the pending events.
   If it reports 0, stop.
2. Read `pending.json`. Each event has `title`, `summary`, `url`, source
   fields, and for FDA records an `fda_summary_excerpt` with the indications
   for use and predicate. When you need more, read the full text under
   `data/fda_summaries/<K>.txt` or fetch the `url`.
3. Decide for each event, following the rubric in `watch/triage.py`
   (`system_prompt`) and the P0 definition in `config.yaml`:
   - `priority`: P0 (email now), P1 (leads the brief), P2 (in brief), P3 (count only), or `drop`.
   - `relevance` 0-5, `tags`, `companies` (slugs from `config.yaml`),
     `summary` (two factual sentences), `why_it_matters` (implication for Cleerly or the field).
   - Duplicates: give the best source P1/P2 and mark the rest P3 saying "duplicate".
   - Cleerly's own clearances are P1, not P0.
4. Write `results.json` as a list of `{id, relevance, priority, tags, companies, summary, why_it_matters}`,
   then `python -m watch triage --apply results.json --by "agent:<model>"`.
5. For every P0 and P1, update the relevant dossier under `knowledge/companies/<slug>.md`:
   add a dated bullet to Timeline, and update Products, Clinical evidence,
   Reimbursement or Business as appropriate. Keep the auto-generated block intact.
   Create `knowledge/companies/<slug>.md` for a new company only if it is a
   direct competitor in AI cardiac imaging; otherwise mention it in `knowledge/watchlist.md`.
6. `python -m watch knowledge`, then commit and push:
   `git add -A data knowledge && git commit -m "triage: <n> events" && git pull --rebase origin main && git push origin main`.
   If the push is rejected, push a branch and open a PR titled "triage: <date>".

## Role: Editor (daily, before the brief is sent at 11:00 UTC)

1. `git pull`. Read today's triaged items: `python -m watch brief --dry-run`
   writes the brief to `data/briefs/outbox/` without sending or marking anything.
2. Write `data/briefs/<YYYY-MM-DD>.editorial.md` (today's date in UTC): 150-350 words,
   markdown, for a reader who runs strategy or regulatory at Cleerly. Lead with what
   changed and why it matters, connect items to each other and to the dossiers,
   name what to watch next. Bold the first phrase of each paragraph. No headers.
   If nothing material happened, say so in two sentences.
3. Review the week in `knowledge/`: fix anything stale, fill gaps from the
   stored FDA summary texts, and keep `knowledge/landscape.md` current (one page:
   who has what cleared, where codes stand, what trials are due).
4. Commit and push as above. The brief workflow picks up the editorial automatically.

## Rules

- Never edit `data/index.json` or event files by hand; use the CLI.
- Never delete PDFs or summary texts.
- Cite a URL for every claim you add to `knowledge/`.
- If a collector is clearly broken (same error across runs in `data/state.json`),
  fix it in `watch/collectors/` and open a PR; do not push collector changes to main.

"""Triage: decide what matters.

Two paths produce identical output:
  * `run_api()`    — scripted, uses the Claude API when ANTHROPIC_API_KEY is set.
  * export/apply   — an agent (e.g. a Claude Code cloud routine) reads the
                     export, reasons, and writes results back via `apply()`.

Triage fields written onto each event:
  triage: {relevance 0-5, priority P0|P1|P2|P3, tags[], companies[],
           summary, why_it_matters, triaged_by, triaged_at}
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .config import ROOT
from .store import STATUS_NEW, STATUS_TRIAGED, Store, now_iso

log = logging.getLogger(__name__)

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "relevance": {"type": "integer", "minimum": 0, "maximum": 5},
                    "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3", "drop"]},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "companies": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
                "required": ["id", "relevance", "priority", "tags", "companies", "summary", "why_it_matters"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def pending(store: Store) -> list[dict]:
    return list(store.iter_events([STATUS_NEW]))


def compact(event: dict, *, with_documents: bool = True) -> dict:
    """The slice of an event a triager needs to see."""
    x = event.get("extra", {})
    out = {
        "id": event["id"],
        "source": event["source"],
        "category": event["category"],
        "title": event["title"],
        "url": event["url"],
        "published": event["published"],
        "summary": event["summary"][:1500],
        "prefilter_companies": (event.get("prefilter") or {}).get("companies", []),
    }
    for k in ("k_number", "applicant", "product_code", "regulation_number", "sponsor", "status",
              "new_registration", "journal", "pub_types", "form", "filers", "publisher", "query", "feed"):
        if x.get(k) not in (None, "", []):
            out[k] = x[k]
    if with_documents and x.get("summary_text_path"):
        p = ROOT / x["summary_text_path"]
        if p.exists():
            out["fda_summary_excerpt"] = fda_excerpt(p.read_text())
    return out


def fda_excerpt(text: str, limit: int = 3500) -> str:
    """Pull the useful parts of an FDA summary: the indications-for-use statement
    and the start of the 510(k) summary, skipping the cover-letter boilerplate."""
    import re
    flat = re.sub(r"[ \t]+", " ", text)
    parts: list[str] = []
    m = re.search(r"Indications for Use\s*\(Describe\)(.{0,1800}?)(Type of Use|PLEASE DO NOT WRITE|FORM FDA)", flat, re.S | re.I)
    if m:
        parts.append("INDICATIONS FOR USE: " + " ".join(m.group(1).split()))
    m = re.search(r"510\(k\)\s+Summary(.{0,2500})", flat, re.S | re.I)
    if m:
        parts.append("510(k) SUMMARY: " + " ".join(m.group(1).split()))
    m = re.search(r"(predicate device[s]?\s*[:\-]?.{0,600})", flat, re.S | re.I)
    if m and "predicate" not in " ".join(parts).lower():
        parts.append("PREDICATE: " + " ".join(m.group(1).split()))
    if not parts:
        return " ".join(flat.split())[:limit]
    return "\n".join(parts)[:limit]


def export(store: Store, path: Path | None) -> int:
    items = [compact(e) for e in pending(store)]
    text = json.dumps(items, indent=1, ensure_ascii=False)
    if path:
        path.write_text(text)
    else:
        print(text)
    return len(items)


def apply(store: Store, results: list[dict], *, triaged_by: str) -> dict:
    """Write triage results. Returns counts by priority."""
    counts: dict = {}
    for r in results:
        ev = store.load(r["id"])
        if not ev:
            log.warning("apply: unknown or dropped id %s", r["id"])
            continue
        prio = r.get("priority", "P3")
        if prio == "drop" or int(r.get("relevance", 0)) == 0:
            store.drop(ev["id"])
            counts["drop"] = counts.get("drop", 0) + 1
            continue
        ev["triage"] = {
            "relevance": int(r.get("relevance", 0)),
            "priority": prio,
            "tags": list(r.get("tags", []))[:12],
            "companies": list(r.get("companies", []))[:12],
            "summary": str(r.get("summary", ""))[:1200],
            "why_it_matters": str(r.get("why_it_matters", ""))[:1200],
            "triaged_by": triaged_by,
            "triaged_at": now_iso(),
        }
        ev["status"] = STATUS_TRIAGED
        ev.setdefault("alerted_at", None)
        ev.setdefault("reported_in", None)
        store.update(ev)
        counts[prio] = counts.get(prio, 0) + 1
    store.save()
    return counts


def system_prompt(cfg: dict) -> str:
    companies = "\n".join(f"- {c['slug']}: {c['name']} (aliases: {', '.join(c.get('aliases', []))})" for c in cfg["companies"])
    return f"""You are the triage analyst for a competitive and regulatory intelligence desk covering:
{cfg['topic'].strip()}

The desk serves Cleerly (slug `cleerly`), a US company selling AI coronary CT plaque analysis.
Everything is judged by how much it matters to someone running strategy, regulatory,
clinical evidence, or reimbursement at Cleerly.

Tracked companies (use these slugs in `companies`):
{companies}

Priority rubric:
- P0 (email immediately): {cfg['alerts']['p0_definition'].strip()}
- P1 (leads the morning brief): a competitor product launch, partnership with a scanner vendor
  or large health system, notable financing under $50M, a peer-reviewed study of a tracked or
  competing product with clinical or economic endpoints, a new pivotal trial registration,
  a guideline statement touching CCTA-based plaque or physiology, a proposed CMS rule that
  mentions the relevant codes, an FDA clearance for an adjacent cardiac AI product.
- P2 (in the brief): relevant research without a product tie, routine trial updates, general
  market or trade-press coverage of AI cardiac imaging, filings that merely mention a tracked name.
- P3 (counted, not shown): tangential but on-topic.
- drop: off-topic (e.g. non-cardiac radiology AI, generic health news, unrelated devices
  that happen to share a product code).

Relevance 0-5: 0 = off-topic, 5 = squarely about AI coronary/cardiac imaging products.
`summary`: two sentences max, factual, for a reader who knows the field.
`why_it_matters`: one or two sentences on the implication for Cleerly or the field. If none, say so briefly.
`tags`: short lowercase tokens such as regulatory, ccta, plaque, ffr-ct, echo, cmr, cac,
reimbursement, cpt, trial, evidence, financing, m&a, partnership, recall, guideline.
Return one result per input event, preserving ids exactly."""


def run_api(cfg: dict, store: Store, *, model: str = "claude-opus-5-5", batch_size: int = 12) -> dict:
    """Scripted triage through the Claude API. Requires ANTHROPIC_API_KEY (or ant auth)."""
    import anthropic

    client = anthropic.Anthropic()
    items = pending(store)
    if not items:
        log.info("triage: nothing pending")
        return {}
    totals: dict = {}
    sys_prompt = system_prompt(cfg)
    for i in range(0, len(items), batch_size):
        batch = [compact(e) for e in items[i:i + batch_size]]
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=16000,
                system=[{"type": "text", "text": sys_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": "Triage these events:\n\n" + json.dumps(batch, ensure_ascii=False)}],
                output_config={"format": {"type": "json_schema", "schema": RESULT_SCHEMA}},
            )
        except anthropic.RateLimitError as e:
            log.error("rate limited: %s", e)
            break
        except anthropic.APIStatusError as e:
            log.error("API error %s: %s", e.status_code, e.message)
            break
        if resp.stop_reason == "refusal":
            log.warning("batch refused: %s", getattr(resp, "stop_details", None))
            continue
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        results = json.loads(text).get("results", [])
        counts = apply(store, results, triaged_by=f"api:{model}")
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
        log.info("triage batch %d: %s (in=%d out=%d cached=%s)", i // batch_size + 1, counts,
                 resp.usage.input_tokens, resp.usage.output_tokens, resp.usage.cache_read_input_tokens)
    return totals


def api_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

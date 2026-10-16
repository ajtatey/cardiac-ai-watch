"""Company dossiers under knowledge/companies/. The agent owns the prose;
this module maintains an auto-generated regulatory table between markers."""
from __future__ import annotations

from .config import KNOWLEDGE_DIR
from .store import Store

BEGIN, END = "<!-- auto:fda:begin -->", "<!-- auto:fda:end -->"

TEMPLATE = """# {name}

_Slug: `{slug}`. Aliases: {aliases}._

## Snapshot
_(agent-maintained: what they sell, who buys it, where they are strong or weak relative to Cleerly)_

## Products and cleared indications
_(agent-maintained: one bullet per product, with the indication wording and predicate chain)_

## Regulatory record (auto-generated)
{begin}
{table}
{end}

## Clinical evidence
_(agent-maintained: key studies with endpoints, sample size, and what they claim)_

## Reimbursement
_(agent-maintained: codes used, payer coverage, CMS status)_

## Business
_(agent-maintained: financing, partnerships, leadership, hiring signals)_

## Timeline
_(agent-maintained: dated bullets, newest first)_

## Open questions
_(agent-maintained)_
"""


def _table(rows: list[dict]) -> str:
    if not rows:
        return "_No FDA records found yet._"
    out = ["| Decision | Number | Device | Product code | Summary |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r.get("decision_date") or "", reverse=True):
        doc = f"[PDF]({r['summary_pdf_url']})" if r.get("summary_pdf_url") else "—"
        out.append(f"| {r.get('decision_date')} | [{r['k_number']}]({r['url']}) | {r.get('device_name')} | {r.get('product_code')} | {doc} |")
    return "\n".join(out)


def update_dossiers(cfg: dict, store: Store) -> int:
    KNOWLEDGE_DIR.joinpath("companies").mkdir(parents=True, exist_ok=True)
    by_company: dict[str, list[dict]] = {}
    for ev in store.iter_events():
        if ev["source"] != "fda_510k":
            continue
        slugs = set((ev.get("prefilter") or {}).get("companies", []))
        if ev["extra"].get("matched_company"):
            slugs.add(ev["extra"]["matched_company"])
        for s in slugs:
            by_company.setdefault(s, []).append({**ev["extra"], "url": ev["url"]})
    n = 0
    for c in cfg["companies"]:
        path = KNOWLEDGE_DIR / "companies" / f"{c['slug']}.md"
        table = _table(by_company.get(c["slug"], []))
        if path.exists():
            text = path.read_text()
            if BEGIN in text and END in text:
                head, rest = text.split(BEGIN, 1)
                _, tail = rest.split(END, 1)
                text = f"{head}{BEGIN}\n{table}\n{END}{tail}"
            path.write_text(text)
        else:
            path.write_text(TEMPLATE.format(name=c["name"], slug=c["slug"], aliases=", ".join(c.get("aliases", [])),
                                            begin=BEGIN, end=END, table=table))
        n += 1
    return n

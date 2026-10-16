"""Morning brief and P0 alerts: compose, render, send, mark as reported."""
from __future__ import annotations

import html as H
import logging
import re
from datetime import date

from .config import BRIEFS_DIR
from .mailer import send
from .store import STATUS_TRIAGED, Store, now_iso

log = logging.getLogger(__name__)

CATEGORY_LABEL = {
    "regulatory": "Regulatory", "reimbursement": "Reimbursement & policy", "clinical": "Clinical evidence",
    "trial": "Clinical trials", "financial": "Financial & filings", "news": "News & market",
    "press": "Press releases", "safety": "Safety",
}
ORDER = ["regulatory", "reimbursement", "safety", "financial", "clinical", "trial", "press", "news"]

STYLE = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1a1a1a;max-width:720px;margin:0 auto;padding:24px;line-height:1.45}
h1{font-size:22px;margin:0 0 4px} h2{font-size:16px;margin:28px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}
.meta{color:#666;font-size:13px} .item{margin:0 0 16px;padding-left:12px;border-left:3px solid #ddd}
.item.P0{border-color:#c0392b}.item.P1{border-color:#e67e22}.item.P2{border-color:#bbb}
.title{font-weight:600} .why{color:#444} .src{color:#777;font-size:12px}
.pill{display:inline-block;font-size:11px;padding:1px 6px;border-radius:8px;background:#eee;margin-right:6px}
.P0 .pill{background:#c0392b;color:#fff}.P1 .pill{background:#e67e22;color:#fff}
.editorial{background:#f6f7f9;padding:14px 16px;border-radius:8px;margin:16px 0}
.foot{color:#888;font-size:12px;margin-top:32px}
"""


def _md_inline(s: str) -> str:
    s = H.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    """Tiny markdown subset: headings, bullets, paragraphs, bold, links."""
    out, para, in_list = [], [], False

    def flush():
        nonlocal para
        if para:
            out.append("<p>" + _md_inline(" ".join(para)) + "</p>")
            para = []

    for line in md.splitlines():
        if line.startswith("#"):
            flush()
            if in_list:
                out.append("</ul>"); in_list = False
            level = min(len(line) - len(line.lstrip("#")), 3)
            out.append(f"<h{level + 1}>{_md_inline(line.lstrip('# ').strip())}</h{level + 1}>")
        elif re.match(r"^\s*[-*] ", line):
            flush()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append("<li>" + _md_inline(re.sub(r"^\s*[-*] ", "", line)) + "</li>")
        elif not line.strip():
            flush()
            if in_list:
                out.append("</ul>"); in_list = False
        else:
            para.append(line.strip())
    flush()
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _item_html(ev: dict) -> str:
    t = ev["triage"]
    pub = f" · {ev['published']}" if ev.get("published") else ""
    comp = f" · {', '.join(t['companies'])}" if t.get("companies") else ""
    return (
        f'<div class="item {t["priority"]}"><span class="pill">{t["priority"]}</span>'
        f'<span class="title"><a href="{H.escape(ev["url"])}">{H.escape(ev["title"])}</a></span>'
        f'<div>{H.escape(t["summary"])}</div>'
        f'<div class="why">{H.escape(t["why_it_matters"])}</div>'
        f'<div class="src">{H.escape(ev["source"])}{pub}{comp}</div></div>'
    )


def _item_md(ev: dict) -> str:
    t = ev["triage"]
    return (f"- **[{t['priority']}] {ev['title']}**  \n  {t['summary']}  \n  _{t['why_it_matters']}_  \n"
            f"  {ev['url']} ({ev['source']}{', ' + ev['published'] if ev.get('published') else ''})")


def compose(cfg: dict, store: Store, day: str) -> tuple[str, str, str, list[dict]]:
    """Return (subject, html, markdown, events_included)."""
    items = [e for e in store.iter_events([STATUS_TRIAGED])
             if not e.get("reported_in") and e["triage"]["priority"] in ("P0", "P1", "P2")]
    low = [e for e in store.iter_events([STATUS_TRIAGED]) if not e.get("reported_in") and e["triage"]["priority"] == "P3"]
    items.sort(key=lambda e: (e["triage"]["priority"], ORDER.index(e["category"]) if e["category"] in ORDER else 99, e.get("published", "")), reverse=False)

    editorial_path = BRIEFS_DIR / f"{day}.editorial.md"
    editorial = editorial_path.read_text().strip() if editorial_path.exists() else ""

    p0 = [e for e in items if e["triage"]["priority"] == "P0"]
    p1 = [e for e in items if e["triage"]["priority"] == "P1"]
    headline = f"{len(p0)} alert{'s' if len(p0) != 1 else ''}, {len(p1)} lead item{'s' if len(p1) != 1 else ''}, {len(items)} items total"
    subject = f"{cfg['email']['brief_subject_prefix']} — {day}: {headline}"

    md = [f"# Cardiac AI brief — {day}", "", headline, ""]
    html = [f"<!doctype html><html><head><meta charset='utf-8'><style>{STYLE}</style></head><body>",
            f"<h1>Cardiac AI brief</h1><div class='meta'>{day} · {H.escape(headline)}</div>"]
    if editorial:
        md += ["## Editor's note", editorial, ""]
        html.append(f"<div class='editorial'>{md_to_html(editorial)}</div>")
    if p0:
        md += ["## Alerts"] + [_item_md(e) for e in p0] + [""]
        html.append("<h2>Alerts</h2>" + "".join(_item_html(e) for e in p0))
    if p1:
        md += ["## Lead items"] + [_item_md(e) for e in p1] + [""]
        html.append("<h2>Lead items</h2>" + "".join(_item_html(e) for e in p1))
    rest = [e for e in items if e["triage"]["priority"] == "P2"]
    for cat in ORDER:
        group = [e for e in rest if e["category"] == cat]
        if not group:
            continue
        label = CATEGORY_LABEL.get(cat, cat.title())
        md += [f"## {label}"] + [_item_md(e) for e in group] + [""]
        html.append(f"<h2>{label}</h2>" + "".join(_item_html(e) for e in group))
    if not items:
        md.append("Nothing rose above the threshold since the last brief.")
        html.append("<p>Nothing rose above the threshold since the last brief.</p>")
    counts = store.counts()
    foot = (f"{len(low)} low-priority items counted but not shown. Store: {counts}. "
            f"Generated {now_iso()} by Cardiac AI Watch.")
    md += ["---", foot]
    html.append(f"<div class='foot'>{H.escape(foot)}</div></body></html>")
    return subject, "\n".join(html), "\n".join(md), items + low


def run_brief(cfg: dict, store: Store, *, day: str | None = None, dry_run: bool = False, force: bool = False) -> bool:
    day = day or date.today().isoformat()
    if store.state.get("last_brief") == day and not force:
        log.info("brief for %s already sent", day)
        return False
    subject, html, md, included = compose(cfg, store, day)
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEFS_DIR / f"{day}.md").write_text(md + "\n")
    send(cfg, subject=subject, html=html, text=md, dry_run=dry_run, tag="brief")
    if not dry_run:
        for e in included:
            e["reported_in"] = day
            store.update(e)
        store.state["last_brief"] = day
        store.save()
    return True


def run_alerts(cfg: dict, store: Store, *, dry_run: bool = False) -> int:
    sent = 0
    for e in store.iter_events([STATUS_TRIAGED]):
        if e["triage"]["priority"] != "P0" or e.get("alerted_at"):
            continue
        t = e["triage"]
        subject = f"{cfg['email']['alert_subject_prefix']}: {e['title'][:120]}"
        html = (f"<!doctype html><html><head><meta charset='utf-8'><style>{STYLE}</style></head><body>"
                f"<h1>Alert</h1>{_item_html(e)}"
                f"<div class='foot'>Source: {H.escape(e['source'])}. Sent {now_iso()} by Cardiac AI Watch.</div></body></html>")
        text = f"ALERT\n\n{e['title']}\n\n{t['summary']}\n\n{t['why_it_matters']}\n\n{e['url']}\n"
        send(cfg, subject=subject, html=html, text=text, dry_run=dry_run, tag="alert")
        if not dry_run:
            e["alerted_at"] = now_iso()
            store.update(e)
        sent += 1
    store.save()
    return sent

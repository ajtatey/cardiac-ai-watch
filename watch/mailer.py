"""Email delivery through Resend."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

from .config import BRIEFS_DIR

log = logging.getLogger(__name__)
RESEND_URL = "https://api.resend.com/emails"


def send(cfg: dict, *, subject: str, html: str, text: str, dry_run: bool = False, tag: str = "brief") -> str | None:
    """Send an email. In dry-run mode (or with no key) writes the HTML to data/briefs/outbox/."""
    key = os.environ.get("RESEND_API_KEY")
    if dry_run or not key:
        out = BRIEFS_DIR / "outbox"
        out.mkdir(parents=True, exist_ok=True)
        fn = out / (Path(subject.replace("/", "-").replace(" ", "_")[:80]).name + ".html")
        fn.write_text(html)
        log.info("%s: wrote %s (no RESEND_API_KEY)" if not key else "%s: dry-run wrote %s", tag, fn)
        return None
    payload = {
        "from": cfg["email"]["from"],
        "to": cfg["email"]["to"],
        "subject": subject,
        "html": html,
        "text": text,
        "tags": [{"name": "kind", "value": tag}],
    }
    r = requests.post(RESEND_URL, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    if r.status_code >= 300:
        log.error("resend %s: %s", r.status_code, r.text[:300])
        r.raise_for_status()
    mid = r.json().get("id")
    log.info("%s: sent %r to %s (id %s)", tag, subject, cfg["email"]["to"], mid)
    return mid

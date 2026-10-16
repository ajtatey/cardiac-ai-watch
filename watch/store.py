"""Event store: one JSON file per kept event, plus an index of every id seen.

Layout
  data/events/<source>/<safe_id>.json   full event (only for kept events)
  data/index.json                       {id: {status, source, priority, path, first_seen}}
  data/state.json                       collector cursors, last brief date, etc.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .config import EVENTS_DIR, INDEX_FILE, STATE_FILE

STATUS_NEW = "new"            # collected, awaiting triage
STATUS_TRIAGED = "triaged"    # triage fields populated
STATUS_DROPPED = "dropped"    # prefilter or triage said irrelevant; no file kept

PRIORITIES = ("P0", "P1", "P2", "P3")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_name(event_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", event_id)[:180]


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open() as f:
        return json.load(f)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(obj, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


class Store:
    def __init__(self) -> None:
        self.index: dict = _read_json(INDEX_FILE, {})
        self.state: dict = _read_json(STATE_FILE, {})

    # ----- persistence -------------------------------------------------
    def save(self) -> None:
        _write_json(INDEX_FILE, self.index)
        _write_json(STATE_FILE, self.state)

    # ----- events ------------------------------------------------------
    def has(self, event_id: str) -> bool:
        return event_id in self.index

    def event_path(self, source: str, event_id: str) -> Path:
        return EVENTS_DIR / source / f"{safe_name(event_id)}.json"

    def add(self, event: dict, *, keep: bool) -> None:
        """Record a newly collected event. If keep is False only the id is indexed."""
        eid, source = event["id"], event["source"]
        entry = {
            "source": source,
            "status": event.get("status", STATUS_NEW) if keep else STATUS_DROPPED,
            "first_seen": now_iso(),
            "priority": (event.get("triage") or {}).get("priority") if keep else None,
            "title": event.get("title", "")[:160],
        }
        if keep:
            event.setdefault("status", STATUS_NEW)
            event.setdefault("collected_at", now_iso())
            path = self.event_path(source, eid)
            _write_json(path, event)
            entry["path"] = str(path.relative_to(EVENTS_DIR.parent.parent))
        self.index[eid] = entry

    def load(self, event_id: str) -> dict | None:
        entry = self.index.get(event_id)
        if not entry or "path" not in entry:
            return None
        return _read_json(EVENTS_DIR.parent.parent / entry["path"], None)

    def update(self, event: dict) -> None:
        eid = event["id"]
        entry = self.index[eid]
        entry["status"] = event.get("status", entry["status"])
        entry["priority"] = (event.get("triage") or {}).get("priority")
        _write_json(EVENTS_DIR.parent.parent / entry["path"], event)

    def drop(self, event_id: str) -> None:
        """Mark an event irrelevant after triage and delete its file."""
        entry = self.index[event_id]
        if "path" in entry:
            p = EVENTS_DIR.parent.parent / entry["path"]
            if p.exists():
                p.unlink()
            entry.pop("path", None)
        entry["status"] = STATUS_DROPPED
        entry["priority"] = None

    def iter_events(self, statuses: Iterable[str] | None = None) -> Iterator[dict]:
        wanted = set(statuses) if statuses else None
        for eid, entry in sorted(self.index.items()):
            if "path" not in entry:
                continue
            if wanted and entry["status"] not in wanted:
                continue
            ev = self.load(eid)
            if ev:
                yield ev

    def counts(self) -> dict:
        out: dict = {}
        for entry in self.index.values():
            key = entry["status"] if entry["status"] != STATUS_TRIAGED else f"triaged/{entry.get('priority')}"
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items()))

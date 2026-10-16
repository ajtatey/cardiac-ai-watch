"""Command line entry point: python -m watch <command>."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import brief, knowledge, prefilter, triage
from .collectors import registry
from .config import load_config, load_dotenv
from .store import STATUS_TRIAGED, Store, now_iso

log = logging.getLogger("watch")


def cmd_collect(args, cfg, store: Store) -> int:
    collectors = registry()
    names = args.only or list(collectors)
    totals: dict = {}
    for name in names:
        fn = collectors[name]
        new = kept = 0
        try:
            for ev in fn(cfg, store.state):
                if store.has(ev["id"]):
                    continue
                new += 1
                pf = prefilter.score(cfg, ev)
                ev["prefilter"] = pf
                if ev["extra"].get("historical"):
                    # Tracked-company FDA records older than the window: keep for
                    # dossiers, never alert or report.
                    ev["triage"] = {"relevance": 3, "priority": "P3", "tags": ["historical", "regulatory"],
                                    "companies": pf["companies"], "summary": "Historical FDA record stored for dossier context.",
                                    "why_it_matters": "", "triaged_by": "collector", "triaged_at": now_iso()}
                    ev["status"] = STATUS_TRIAGED
                    ev["reported_in"] = "historical"
                    ev["alerted_at"] = None
                    store.add(ev, keep=True)
                    kept += 1
                    continue
                store.add(ev, keep=pf["keep"])
                kept += int(pf["keep"])
        except Exception as e:  # noqa: BLE001
            log.exception("collector %s crashed: %s", name, e)
        store.state.setdefault("collectors", {})[name] = {"last_run": now_iso(), "new": new, "kept": kept}
        totals[name] = (new, kept)
        log.info("%s: %d new, %d kept", name, new, kept)
        store.save()
    print(json.dumps({k: {"new": v[0], "kept": v[1]} for k, v in totals.items()}, indent=1))
    return 0


def cmd_triage(args, cfg, store: Store) -> int:
    if args.export is not None:
        n = triage.export(store, Path(args.export) if args.export else None)
        log.info("exported %d pending events", n)
        return 0
    if args.apply:
        results = json.loads(Path(args.apply).read_text())
        if isinstance(results, dict):
            results = results.get("results", [])
        counts = triage.apply(store, results, triaged_by=args.by or "agent")
        print(json.dumps(counts))
        return 0
    if not triage.api_available():
        n = len(triage.pending(store))
        log.warning("no ANTHROPIC_API_KEY; %d events pending. Use `triage --export` for an agent, "
                    "or set a key for scripted triage.", n)
        return 0
    counts = triage.run_api(cfg, store, model=args.model)
    print(json.dumps(counts))
    return 0


def cmd_alerts(args, cfg, store: Store) -> int:
    n = brief.run_alerts(cfg, store, dry_run=args.dry_run)
    log.info("alerts sent: %d", n)
    return 0


def cmd_brief(args, cfg, store: Store) -> int:
    sent = brief.run_brief(cfg, store, day=args.date, dry_run=args.dry_run, force=args.force)
    log.info("brief %s", "sent" if sent else "skipped")
    return 0


def cmd_knowledge(args, cfg, store: Store) -> int:
    n = knowledge.update_dossiers(cfg, store)
    log.info("updated %d dossiers", n)
    return 0


def cmd_status(args, cfg, store: Store) -> int:
    print(json.dumps({"counts": store.counts(), "state": store.state}, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(prog="watch", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="run collectors and store new events")
    c.add_argument("--only", nargs="*", help="collector names")
    c.set_defaults(fn=cmd_collect)

    t = sub.add_parser("triage", help="triage pending events (API, or export/apply for an agent)")
    t.add_argument("--export", nargs="?", const="", metavar="FILE", help="write pending events as JSON (stdout if no FILE)")
    t.add_argument("--apply", metavar="FILE", help="apply triage results JSON")
    t.add_argument("--by", help="label for triaged_by when applying")
    t.add_argument("--model", default="claude-opus-5-5")
    t.set_defaults(fn=cmd_triage)

    a = sub.add_parser("alerts", help="email P0 events not yet alerted")
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(fn=cmd_alerts)

    b = sub.add_parser("brief", help="compose and email the brief")
    b.add_argument("--date")
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--force", action="store_true", help="send even if today's brief was already sent")
    b.set_defaults(fn=cmd_brief)

    k = sub.add_parser("knowledge", help="refresh auto-generated sections of company dossiers")
    k.set_defaults(fn=cmd_knowledge)

    s = sub.add_parser("status", help="show store counts and collector state")
    s.set_defaults(fn=cmd_status)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    cfg = load_config()
    store = Store()
    return args.fn(args, cfg, store)


if __name__ == "__main__":
    sys.exit(main())

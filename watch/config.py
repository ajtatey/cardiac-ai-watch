from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"
EVENTS_DIR = DATA_DIR / "events"
INDEX_FILE = DATA_DIR / "index.json"
BRIEFS_DIR = DATA_DIR / "briefs"
FDA_DOCS_DIR = DATA_DIR / "fda_summaries"
KNOWLEDGE_DIR = ROOT / "knowledge"
STATE_FILE = DATA_DIR / "state.json"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, no quotes handling beyond strip."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config() -> dict:
    with CONFIG_FILE.open() as f:
        cfg = yaml.safe_load(f)
    # Env overrides for email routing so CI can redirect without editing YAML.
    if os.environ.get("EMAIL_TO"):
        cfg["email"]["to"] = [x.strip() for x in os.environ["EMAIL_TO"].split(",") if x.strip()]
    if os.environ.get("EMAIL_FROM"):
        cfg["email"]["from"] = os.environ["EMAIL_FROM"]
    return cfg

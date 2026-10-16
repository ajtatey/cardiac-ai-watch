"""Cheap keyword relevance scoring run before any model sees an event.

Targeted sources (FDA by product code, PubMed, ClinicalTrials, Federal
Register, EDGAR) are always kept. Broad sources (RSS, Google News) must hit a
cardiac-imaging term, or name a tracked company, to be kept.
"""
from __future__ import annotations

import re

CARDIAC = [
    r"coronar", r"cardiac", r"\bheart\b", r"ccta", r"ct angiograph", r"\bffr", r"plaque",
    r"atheroscler", r"myocard", r"echocardiog", r"\becho\b", r"cardiac mri", r"\bcmr\b",
    r"calcium scor", r"\bcac\b", r"stenos", r"ischemi", r"angina", r"chest pain",
    r"ventric", r"pericoronary", r"perivascular", r"cardiolog", r"cardiovascular",
    r"structural heart", r"\btavr\b", r"valve", r"nuclear cardiology", r"\bspect\b",
]
AI = [
    r"artificial intelligence", r"\bai\b", r"machine learning", r"deep learning", r"algorithm",
    r"software", r"automat", r"quantif", r"image analysis", r"neural network", r"\bsamd\b",
    r"fda", r"510\(k\)", r"clearance", r"de novo", r"cpt", r"reimburse", r"medicare", r"coverage",
]
BROAD_SOURCES = {"rss"}


def _hits(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text)]


def company_matches(cfg: dict, text: str) -> list[str]:
    t = text.lower()
    out = []
    for c in cfg["companies"]:
        for alias in c.get("aliases", []) + [c["name"]]:
            a = alias.lower()
            # short aliases need word boundaries to avoid "AI" matching everything
            pat = rf"\b{re.escape(a)}\b" if len(a) <= 6 else re.escape(a)
            if re.search(pat, t):
                out.append(c["slug"])
                break
    return out


def score(cfg: dict, event: dict) -> dict:
    text = f"{event.get('title', '')} {event.get('summary', '')}".lower()
    cardiac = _hits(CARDIAC, text)
    ai = _hits(AI, text)
    companies = company_matches(cfg, text)
    s = 2 * len(cardiac) + len(ai) + 5 * len(companies)
    if event["source"] in BROAD_SOURCES:
        keep = bool(companies) or (bool(cardiac) and bool(ai))
    else:
        keep = True
    return {"score": s, "cardiac": cardiac, "ai": ai, "companies": companies, "keep": keep}

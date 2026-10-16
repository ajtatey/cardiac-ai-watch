from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
# SEC asks for a descriptive UA with a contact address.
SEC_UA = "cardiac-ai-watch (andrew@argot.dev)"
TIMEOUT = 40


def session(user_agent: str = BROWSER_UA) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent, "Accept": "*/*"})
    return s


def get(s: requests.Session, url: str, *, retries: int = 2, **kw) -> requests.Response:
    """GET with small retry on 429/5xx and connection errors."""
    kw.setdefault("timeout", TIMEOUT)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = s.get(url, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return r
        except requests.RequestException as e:  # noqa: PERF203
            last = e
            time.sleep(2 * (attempt + 1))
    assert last is not None
    raise last

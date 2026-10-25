"""A throttled, cached JSON GET shared by the Kalshi and Polymarket pullers.

Every response is cached under data/raw/cache/<host>/<sha256 of the URL>.json (gitignored), so a
rerun makes no request it has already made. The cache index (URL -> file, SHA-256, time) goes
into data/raw/MANIFEST.json via `record()`.
"""

import hashlib
import json
import threading
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import requests

from sharpmkt.config import MANIFEST, RAW, USER_AGENT

CACHE = RAW / "cache"
MIN_INTERVAL = {"api.elections.kalshi.com": 0.25, "gamma-api.polymarket.com": 0.12,
                "clob.polymarket.com": 0.12}  # seconds between requests, per host
_locks: dict[str, threading.Lock] = {}
_last: dict[str, float] = {}
_session = threading.local()
_index_lock = threading.Lock()
INDEX: dict[str, dict] = {}


def _get_session() -> requests.Session:
    if not hasattr(_session, "s"):
        _session.s = requests.Session()
        _session.s.headers["User-Agent"] = USER_AGENT
    return _session.s


def _wait(host: str) -> None:
    lock = _locks.setdefault(host, threading.Lock())
    with lock:
        gap = MIN_INTERVAL.get(host, 0.2) - (time.monotonic() - _last.get(host, 0.0))
        if gap > 0:
            time.sleep(gap)
        _last[host] = time.monotonic()


def get_json(url: str, refresh: bool = False):
    host = urlparse(url).hostname or ""
    key = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE / host / f"{key}.json"
    if path.exists() and not refresh:
        body = path.read_bytes()
    else:
        for attempt in range(10):
            _wait(host)
            try:
                r = _get_session().get(url, timeout=60)
            except (requests.ConnectionError, requests.Timeout):
                time.sleep(min(60, 2 ** attempt))
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                retry = r.headers.get("Retry-After")
                time.sleep(float(retry) if retry and retry.isdigit() else min(60, 2 ** attempt))
                continue
            break
        else:
            raise RuntimeError(f"gave up on {url}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        body = r.content
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    with _index_lock:
        INDEX.setdefault(str(path.relative_to(RAW)), {
            "url": url, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
            "retrieved": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                timespec="seconds")})
    return json.loads(body)


def record(extra: dict | None = None) -> None:
    """Merge this run's cache index (and any extra file entries) into the manifest."""
    m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
    m["files"].update(INDEX)
    m["files"].update(extra or {})
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=0, sort_keys=True) + "\n")

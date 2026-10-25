"""HTTP + on-disk cache. Standard library only, on purpose.

A tax helper that drags in `requests` is a tax helper people do not install
inside a locked-down finance environment. Everything here is stdlib.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any

BASE_URL = os.environ.get("ITRSARAL_BASE_URL", "https://itrsaral.in/api")

#: How long a cached file is served without asking the network again.
#: Six hours: these figures move on quarters and Budgets, never on minutes.
CACHE_TTL = int(os.environ.get("ITRSARAL_CACHE_TTL", 6 * 60 * 60))

CACHE_DIR = os.environ.get(
    "ITRSARAL_CACHE_DIR", os.path.join(tempfile.gettempdir(), "itrsaral-cache")
)

USER_AGENT = "itrsaral-python (+https://github.com/anurag/itrsaral-python)"

_memory: dict[str, tuple[float, Any]] = {}


class ITRSaralError(RuntimeError):
    """Raised when a dataset cannot be fetched and no cached copy exists."""


def _cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name + ".json")


def _read_cache(name: str) -> tuple[float, Any] | None:
    path = _cache_path(name)
    try:
        age = os.path.getmtime(path)
        with open(path, encoding="utf-8") as fh:
            return age, json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(name: str, payload: Any) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        # write-then-rename, so a crash mid-write cannot leave a half file
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, _cache_path(name))
    except OSError:
        pass  # a cache we cannot write is a slowdown, never an error


def fetch(name: str, *, refresh: bool = False, timeout: float = 15.0) -> Any:
    """Return one dataset as parsed JSON.

    Served from memory, then from disk, then from the network. If the network
    fails but a stale cached copy exists, the stale copy is returned — a figure
    from this morning beats a traceback.
    """
    now = time.time()

    if not refresh:
        hit = _memory.get(name)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]

        disk = _read_cache(name)
        if disk and now - disk[0] < CACHE_TTL:
            _memory[name] = (disk[0], disk[1])
            return disk[1]

    request = urllib.request.Request(
        f"{BASE_URL}/{name}.json", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        stale = _read_cache(name)
        if stale:
            _memory[name] = (stale[0], stale[1])
            return stale[1]
        raise ITRSaralError(
            f"could not fetch {name!r} from {BASE_URL} and no cached copy exists"
        ) from exc

    _memory[name] = (now, payload)
    _write_cache(name, payload)
    return payload


def clear_cache() -> None:
    """Forget everything held in memory and on disk."""
    _memory.clear()
    try:
        for entry in os.listdir(CACHE_DIR):
            if entry.endswith(".json"):
                os.remove(os.path.join(CACHE_DIR, entry))
    except OSError:
        pass

"""Tiny in-memory TTL cache so repeated demo searches never hit GitHub twice."""
import time
from typing import Any, Optional

from .config import CACHE_TTL

_store: dict[str, tuple[float, Any]] = {}


def get(key: str) -> Optional[Any]:
    entry = _store.get(key)
    if entry is None:
        return None
    expires, value = entry
    if expires < time.time():
        _store.pop(key, None)
        return None
    return value


def put(key: str, value: Any, ttl: Optional[int] = None) -> None:
    _store[key] = (time.time() + (ttl or CACHE_TTL), value)

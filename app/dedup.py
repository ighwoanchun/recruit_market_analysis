from __future__ import annotations

from typing import Iterable, List, Set, TypeVar

T = TypeVar("T")

def dedup_by_url(items: Iterable[T], get_url) -> List[T]:
    seen: Set[str] = set()
    out: List[T] = []
    for it in items:
        url = (get_url(it) or "").strip()
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(it)
    return out

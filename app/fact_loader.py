from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_all_facts(base_dir: str = "data/facts") -> List[Dict[str, Any]]:
    base = Path(base_dir)
    if not base.exists():
        return []
    out: List[Dict[str, Any]] = []
    for p in base.rglob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out

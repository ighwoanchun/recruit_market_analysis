from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class FactStore:
    base_dir: Path = Path("data/facts")

    def path_for(self, *, url: str, date_utc: Optional[str] = None) -> Path:
        # date_utc: "YYYY-MM-DD"
        if not date_utc:
            date_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        h = _url_hash(url)
        return self.base_dir / date_utc / f"{h}.json"

    def exists(self, *, url: str, date_utc: Optional[str] = None) -> bool:
        return self.path_for(url=url, date_utc=date_utc).exists()

    def load(self, *, url: str, date_utc: Optional[str] = None) -> Dict[str, Any]:
        p = self.path_for(url=url, date_utc=date_utc)
        return json.loads(p.read_text(encoding="utf-8"))

    def save(
        self,
        *,
        url: str,
        source: str,
        title: str,
        published_date: Optional[str],
        fact_json: Dict[str, Any],
        date_utc: Optional[str] = None,
    ) -> Path:
        p = self.path_for(url=url, date_utc=date_utc)
        p.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "meta": {
                "url": url,
                "source": source,
                "title": title,
                "published_date": published_date,  # "YYYY-MM-DD" or None
                "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "fact": fact_json,
        }
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

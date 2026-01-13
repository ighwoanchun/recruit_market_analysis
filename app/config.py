import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Settings:
    slack_webhook_url: str
    report_days: int
    competitors: List[str]

    @staticmethod
    def from_env() -> "Settings":
        webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        if not webhook:
            raise ValueError("Missing env: SLACK_WEBHOOK_URL")

        days_raw = os.environ.get("REPORT_DAYS", "7").strip()
        try:
            days = int(days_raw)
        except ValueError as e:
            raise ValueError(f"Invalid REPORT_DAYS: {days_raw}") from e

        competitors_raw = os.environ.get("COMPETITORS", "").strip()
        competitors = [c.strip() for c in competitors_raw.split(",") if c.strip()]
        if not competitors:
            # Default fallback (safe)
            competitors = ["saramin", "jobkorea"]

        return Settings(
            slack_webhook_url=webhook,
            report_days=days,
            competitors=competitors,
        )

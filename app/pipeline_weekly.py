from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from .config import Settings
from .collector_rss import Item, collect_news_for_competitor
from .report_generator import build_draft_report, to_markdown
from .slack_sender import send_to_slack


def main() -> None:
    settings = Settings.from_env()

    collected: Dict[str, List[Item]] = {}
    for c in settings.competitors:
        try:
            collected[c] = collect_news_for_competitor(c)
        except Exception as e:
            # Keep pipeline alive; report the failure in output
            collected[c] = []
            print(f"[WARN] collector failed for {c}: {e}")

    report = build_draft_report(collected, days=settings.report_days)
    md = to_markdown(report)

    # Save to repo artifacts
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weekly_report.md").write_text(md, encoding="utf-8")

    # Send to Slack
    send_to_slack(settings.slack_webhook_url, md)


if __name__ == "__main__":
    main()

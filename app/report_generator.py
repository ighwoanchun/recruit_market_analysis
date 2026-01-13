from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from .collector_rss import Item


@dataclass
class WeeklyReport:
    title: str
    generated_at: datetime
    sections: Dict[str, str]  # section_name -> markdown


def filter_recent(items: List[Item], days: int) -> List[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for it in items:
        # if no published time, keep it but it will be marked
        if it.published_at is None or it.published_at >= cutoff:
            out.append(it)
    return out


def build_draft_report(collected: Dict[str, List[Item]], days: int) -> WeeklyReport:
    now = datetime.now(timezone.utc)
    title = f"[주간 경쟁사 동향 초안] 최근 {days}일 수집 요약"

    md = []
    md.append(f"- 생성 시각(UTC): {now.strftime('%Y-%m-%d %H:%M')}")
    md.append(f"- 범위: 최근 {days}일")
    md.append("")

    for company, items in collected.items():
        recent = filter_recent(items, days)
        md.append(f"## {company}")
        if not recent:
            md.append("- 수집된 항목 없음")
            md.append("")
            continue

        for it in recent[:10]:
            published = it.published_at.strftime("%Y-%m-%d") if it.published_at else "날짜 확인 불가"
            md.append(f"- ({published}) {it.title} — {it.source} / {it.url}")
        md.append("")

    sections = {"draft": "\n".join(md)}
    return WeeklyReport(title=title, generated_at=now, sections=sections)


def to_markdown(report: WeeklyReport) -> str:
    body = [f"*{report.title}*", ""]
    for _, content in report.sections.items():
        body.append(content)
    return "\n".join(body).strip() + "\n"

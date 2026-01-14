from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .job_scraper_proto import JobPosting, analyze_titles_basic, scrape_list_page_by_href


@dataclass(frozen=True)
class CompetitorJobSource:
    name: str
    list_url: str
    href_contains: str
    limit: int = 30


def build_jobs_section(sources: List[CompetitorJobSource]) -> str:
    lines: List[str] = []
    lines.append("*[공고 샘플 기반 직무군 분포(경쟁사별)]*")
    lines.append("_※ 각 플랫폼 '리스트 페이지'에서 공고 제목 링크를 샘플 수집해 집계합니다. (페이지 구조/차단 시 누락 가능)_")
    lines.append("")

    for src in sources:
        try:
            posts: List[JobPosting] = scrape_list_page_by_href(
                source=src.name,
                list_url=src.list_url,
                href_contains=src.href_contains,
                limit=src.limit,
                sleep_sec=1.0,
            )

            if not posts:
                lines.append(f"*■ {src.name}*")
                lines.append("- 수집 실패 또는 공고 링크를 찾지 못함")
                lines.append("")
                continue

            buckets: Dict[str, int] = analyze_titles_basic(posts)
            total = sum(buckets.values()) or 1

            order: List[Tuple[str, int]] = [
                ("개발", buckets.get("개발", 0)),
                ("데이터/AI", buckets.get("데이터/AI", 0)),
                ("영업", buckets.get("영업", 0)),
                ("마케팅", buckets.get("마케팅", 0)),
                ("디자인", buckets.get("디자인", 0)),
                ("기타", buckets.get("기타", 0)),
            ]

            lines.append(f"*■ {src.name}* (샘플 {len(posts)}개)")
            parts = []
            for k, v in order:
                pct = round(v * 100 / total)
                parts.append(f"{k} {v}({pct}%)")
            lines.append("- " + " / ".join(parts))
            lines.append("")
        except Exception as e:
            lines.append(f"*■ {src.name}*")
            lines.append(f"- 수집/분석 오류: {type(e).__name__}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"

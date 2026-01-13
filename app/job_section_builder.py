from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .job_scraper_proto import scrape_list_page, analyze_titles_basic, JobPosting


@dataclass(frozen=True)
class CompetitorJobSource:
    name: str
    list_url: str
    link_css: str  # 공고 상세 링크 selector
    limit: int = 30


def build_jobs_section(
    sources: List[CompetitorJobSource],
) -> str:
    """
    Slack/Markdown용 섹션 문자열 생성.
    실패해도 전체 리포트를 깨지 않도록, 각 경쟁사는 best-effort로 처리.
    """
    lines: List[str] = []
    lines.append("*[공고 샘플 기반 직무군 분포(경쟁사별)]*")
    lines.append("_※ 샘플 기반(목록 페이지에서 수집한 최근 공고 제목 N개). HTML 변경/차단 시 누락될 수 있음._")
    lines.append("")

    for src in sources:
        try:
            posts: List[JobPosting] = scrape_list_page(
                source=src.name,
                list_url=src.list_url,
                link_css=src.link_css,
                limit=src.limit,
                sleep_sec=1.0,
            )
            if not posts:
                lines.append(f"*■ {src.name}*")
                lines.append("- 수집 실패 또는 공고 없음")
                lines.append("")
                continue

            buckets: Dict[str, int] = analyze_titles_basic(posts)
            total = sum(buckets.values()) or 1

            # 보기 좋은 순서
            order: List[Tuple[str, int]] = [
                ("개발", buckets.get("개발", 0)),
                ("데이터/AI", buckets.get("데이터/AI", 0)),
                ("영업", buckets.get("영업", 0)),
                ("마케팅", buckets.get("마케팅", 0)),
                ("디자인", buckets.get("디자인", 0)),
                ("기타", buckets.get("기타", 0)),
            ]

            lines.append(f"*■ {src.name}* (샘플 {len(posts)}개)")
            # 예: 개발 12(40%), 데이터/AI 5(17%) ...
            parts = []
            for k, v in order:
                pct = round(v * 100 / total)
                parts.append(f"{k} {v}({pct}%)")
            lines.append("- " + " / ".join(parts))

            # 상위 5개 제목 예시(옵션)
            lines.append("  - 예시(상위 5개):")
            for p in posts[:5]:
                lines.append(f"    - {p.title}")

            lines.append("")
        except Exception as e:
            lines.append(f"*■ {src.name}*")
            lines.append(f"- 수집/분석 오류: {type(e).__name__}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"

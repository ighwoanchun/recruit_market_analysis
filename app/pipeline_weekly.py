from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from .config import Settings
from .collector_rss import Item, collect_news_for_competitor
from .report_generator import build_draft_report, to_markdown
from .slack_sender import send_to_slack

# Vertex / Fact cache mode dependencies
from .vertex_llm import VertexLLM
from .fact_extractor_vertex import FactExtractor
from .storage_fact import FactStore
from .dedup import dedup_by_url


def _collect_all(settings: Settings) -> Dict[str, List[Item]]:
    collected: Dict[str, List[Item]] = {}
    for c in settings.competitors:
        try:
            collected[c] = collect_news_for_competitor(c)
        except Exception as e:
            collected[c] = []
            print(f"[WARN] collector failed for {c}: {type(e).__name__}: {e}")
    return collected


def _flatten(collected: Dict[str, List[Item]]) -> List[Item]:
    out: List[Item] = []
    for _, items in collected.items():
        out.extend(items)
    return out


def run_fact_cache_mode(settings: Settings, collected: Dict[str, List[Item]]) -> None:
    """
    FACT_CACHE_MODE=true 일 때:
    - 수집한 기사들을 URL 기준으로 중복 제거
    - 최대 MAX_FACT_ITEMS 개까지 Vertex AI로 Fact 추출
    - data/facts/YYYY-MM-DD/<hash>.json 로 저장
    - Slack에 요약(저장/스킵/실패) 전송
    """
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite").strip()
    max_items = int(os.environ.get("MAX_FACT_ITEMS", "8"))

    # Vertex LLM init (ADC credentials are expected to be set by GitHub Action auth)
    llm = VertexLLM(
        project_id=os.environ["GCP_PROJECT_ID"],
        region=os.environ["GCP_REGION"],
        model_name=model_name,
    )
    extractor = FactExtractor(llm=llm)
    store = FactStore()

    all_items = dedup_by_url(_flatten(collected), lambda x: x.url)

    saved = 0
    skipped = 0
    failed = 0

    for it in all_items[:max_items]:
        # published date (best-effort)
        published_date = it.published_at.strftime("%Y-%m-%d") if it.published_at else None

        # Skip if already cached for "today(UTC)" bucket
        if store.exists(url=it.url):
            skipped += 1
            continue

        # RSS item may not include full article text; for now use summary/title for smoke+cache
        raw_text = it.raw_summary or it.title

        try:
            fact_json = extractor.extract(
                source=it.source,
                url=it.url,
                title=it.title,
                raw_text=raw_text,
            )
            store.save(
                url=it.url,
                source=it.source,
                title=it.title,
                published_date=published_date,
                fact_json=fact_json,
            )
            saved += 1
        except Exception as e:
            failed += 1
            print(f"[WARN] Fact extract failed: {it.url} / {type(e).__name__}: {e}")

    msg = (
        "*Fact Cache Mode 완료*\n"
        f"- Model: `{model_name}`\n"
        f"- 최대 처리: {max_items}\n"
        f"- 저장: {saved}\n"
        f"- 스킵(중복): {skipped}\n"
        f"- 실패: {failed}\n"
        "\n"
        "※ data/facts/ 아래에 JSON이 생성됩니다. (GitHub Actions에서는 artifact 업로드 설정 필요)"
    )
    send_to_slack(settings.slack_webhook_url, msg)


def run_default_weekly_report(settings: Settings, collected: Dict[str, List[Item]]) -> None:
    """
    기본 모드:
    - 기존처럼 기사 링크 중심 '초안' 리포트를 생성
    - reports/weekly_report.md 저장
    - Slack 전송
    """
    report = build_draft_report(collected, days=settings.report_days)
    md = to_markdown(report)

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weekly_report.md").write_text(md, encoding="utf-8")

    send_to_slack(settings.slack_webhook_url, md)


def main() -> None:
    settings = Settings.from_env()
    collected = _collect_all(settings)

    # Mode switch
    fact_cache_mode = os.environ.get("FACT_CACHE_MODE", "").lower() in ("1", "true", "yes")
    if fact_cache_mode:
        run_fact_cache_mode(settings, collected)
        return

    # default
    run_default_weekly_report(settings, collected)


if __name__ == "__main__":
    main()

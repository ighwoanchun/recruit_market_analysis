from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from .config import Settings
from .collector_rss import Item, collect_news_for_competitor
from .report_generator import build_draft_report, to_markdown
from .slack_sender import send_to_slack

# NEW
from .vertex_llm import VertexLLM
from .fact_extractor_vertex import FactExtractor


def pick_first_item(collected: Dict[str, List[Item]]) -> Item | None:
    for _, items in collected.items():
        for it in items:
            if it.title and it.url:
                return it
    return None


def main() -> None:
    settings = Settings.from_env()

    collected: Dict[str, List[Item]] = {}
    for c in settings.competitors:
        try:
            collected[c] = collect_news_for_competitor(c)
        except Exception as e:
            collected[c] = []
            print(f"[WARN] collector failed for {c}: {e}")

    # ---- Smoke test mode: 1 article -> Vertex Fact Extraction ----
    if os.environ.get("VERTEX_SMOKE_TEST", "").lower() in ("1", "true", "yes"):
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite").strip()
        llm = VertexLLM(
            project_id=os.environ["GCP_PROJECT_ID"],
            region=os.environ["GCP_REGION"],
            model_name=model_name,
        )
        extractor = FactExtractor(llm=llm)

        item = pick_first_item(collected)
        if item is None:
            send_to_slack(settings.slack_webhook_url, "Vertex Smoke Test: 수집된 기사 없음")
            return

        # RSS는 전문이 없을 수 있어 summary라도 넣음(초기 검증 목적)
        raw_text = item.raw_summary or item.title

        try:
            fact_json = extractor.extract(
                source=item.source,
                url=item.url,
                title=item.title,
                raw_text=raw_text,
            )

            reports_dir = Path("reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "fact_smoke_test.json").write_text(
                json.dumps(fact_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            msg = (
                "*Vertex Smoke Test 성공*\n"
                f"- Model: `{model_name}`\n"
                f"- Input: {item.title}\n"
                f"- URL: {item.url}\n"
                "- Output: `reports/fact_smoke_test.json` (artifact로 확인)\n"
            )
            send_to_slack(settings.slack_webhook_url, msg)
            return

        except Exception as e:
            msg = (
                "*Vertex Smoke Test 실패*\n"
                f"- Model: `{model_name}`\n"
                f"- Input: {item.title}\n"
                f"- URL: {item.url}\n"
                f"- Error: `{type(e).__name__}: {e}`\n"
            )
            send_to_slack(settings.slack_webhook_url, msg)
            raise

    # ---- 기존 초안 리포트 로직 ----
    report = build_draft_report(collected, days=settings.report_days)
    md = to_markdown(report)

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weekly_report.md").write_text(md, encoding="utf-8")

    send_to_slack(settings.slack_webhook_url, md)


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from .config import Settings
from .collector_rss import Item, collect_news_for_competitor
from .report_generator import build_draft_report, to_markdown
from .slack_sender import send_to_slack

from .vertex_llm import VertexLLM
from .fact_extractor_vertex import FactExtractor
from .storage_fact import FactStore
from .dedup import dedup_by_url

from .facts_read import read_fact_payloads
from .report_strategy_renderer import group_payloads_by_company, render_strategy_report

from .signal_classifier_vertex import SignalClassifier
from .strategy_hypothesis_vertex import StrategyHypothesis
from .wanted_response_vertex import WantedResponse


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


def _vertex_llm_from_env() -> VertexLLM:
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite").strip()
    return VertexLLM(
        project_id=os.environ["GCP_PROJECT_ID"],
        region=os.environ["GCP_REGION"],
        model_name=model_name,
    )


def run_fact_cache_mode(settings: Settings, collected: Dict[str, List[Item]]) -> None:
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite").strip()
    max_items = int(os.environ.get("MAX_FACT_ITEMS", "15"))

    llm = _vertex_llm_from_env()
    extractor = FactExtractor(llm=llm)
    store = FactStore()

    all_items = dedup_by_url(_flatten(collected), lambda x: x.url)

    saved = 0
    skipped = 0
    failed = 0

    for it in all_items[:max_items]:
        published_date = it.published_at.strftime("%Y-%m-%d") if it.published_at else None

        if store.exists(url=it.url):
            skipped += 1
            continue

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
    )
    send_to_slack(settings.slack_webhook_url, msg)


def run_weekly_strategy_report(settings: Settings) -> None:
    """
    data/facts/에 저장된 Fact payload들을 읽어
    - Signal(A/B/C) 분류 → A/B만 사용
    - 경쟁사별 가설 → 원티드 대응 도출
    - Slack 1페이지 리포트 전송
    """
    llm = _vertex_llm_from_env()

    # Load facts
    payloads = read_fact_payloads("data/facts")
    if not payloads:
        send_to_slack(settings.slack_webhook_url, "*전략 리포트 생성 실패*: data/facts에 Fact가 없습니다.")
        return

    payloads_by_company = group_payloads_by_company(payloads)

    classifier = SignalClassifier(llm=llm)
    hypothesizer = StrategyHypothesis(llm=llm)
    responder = WantedResponse(llm=llm)

    hypothesis_by_company: Dict[str, dict] = {}
    response_by_company: Dict[str, dict] = {}

    for company, plist in payloads_by_company.items():
        # Extract only Fact JSON objects
        facts = [p.get("fact", {}) for p in plist if isinstance(p.get("fact", {}), dict)]

        # Signal classification per fact, keep A/B
        ab_facts = []
        for f in facts:
            try:
                sig = classifier.classify(f)
                level = (sig.get("signal_level") or "").strip()
                if level in ("A", "B"):
                    # keep fact with signal meta (optional)
                    f2 = dict(f)
                    f2["_signal"] = sig
                    ab_facts.append(f2)
            except Exception as e:
                print(f"[WARN] signal classify failed for {company}: {type(e).__name__}: {e}")

        # If no A/B facts, skip company (or keep minimal)
        if not ab_facts:
            continue

        # Hypothesis + response
        hyp = hypothesizer.infer(ab_facts[:8])  # cap to reduce tokens
        resp = responder.propose(hyp)

        hypothesis_by_company[company] = hyp
        response_by_company[company] = resp

    if not hypothesis_by_company:
        send_to_slack(settings.slack_webhook_url, "*전략 리포트 생성 실패*: A/B 신호 Fact가 없습니다.")
        return

    report_text = render_strategy_report(
        hypothesis_by_company=hypothesis_by_company,
        response_by_company=response_by_company,
        payloads_by_company=payloads_by_company,
    )

    # Save as artifact-friendly
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weekly_strategy_report.md").write_text(report_text, encoding="utf-8")

    send_to_slack(settings.slack_webhook_url, report_text)


def run_default_weekly_report(settings: Settings, collected: Dict[str, List[Item]]) -> None:
    report = build_draft_report(collected, days=settings.report_days)
    md = to_markdown(report)

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weekly_report.md").write_text(md, encoding="utf-8")

    send_to_slack(settings.slack_webhook_url, md)


def main() -> None:
    settings = Settings.from_env()
    collected = _collect_all(settings)

    fact_cache_mode = os.environ.get("FACT_CACHE_MODE", "").lower() in ("1", "true", "yes")
    weekly_strategy_mode = os.environ.get("WEEKLY_STRATEGY_REPORT_MODE", "").lower() in ("1", "true", "yes")

    # 1) optionally cache facts in same run
    if fact_cache_mode:
        run_fact_cache_mode(settings, collected)

    # 2) strategy report mode
    if weekly_strategy_mode:
        run_weekly_strategy_report(settings)
        return

    # 3) default weekly draft report
    if not fact_cache_mode:
        run_default_weekly_report(settings, collected)


if __name__ == "__main__":
    main()

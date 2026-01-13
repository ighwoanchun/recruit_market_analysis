from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .company_map import CompanyMapper
from .config import Settings
from .collector_rss import Item, collect_news_for_competitor
from .dedup import dedup_by_url
from .fact_extractor_vertex import FactExtractor
from .facts_read import read_fact_payloads
from .job_section_builder import CompetitorJobSource, build_jobs_section
from .report_generator import build_draft_report, to_markdown
from .report_strategy_renderer import render_strategy_report
from .signal_classifier_vertex import SignalClassifier
from .slack_sender import send_to_slack
from .storage_fact import FactStore
from .strategy_hypothesis_vertex import StrategyHypothesis
from .vertex_llm import VertexLLM
from .wanted_response_vertex import WantedResponse


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


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


def _infer_group_key(payload: dict, mapper: CompanyMapper) -> str:
    """
    그룹 키 결정:
    1) fact.company가 있으면 사용
    2) 없으면 title+url 키워드 매칭
    3) 복수 경쟁사 키워드면 '비교기사'
    4) 아니면 '미분류'
    """
    fact = payload.get("fact", {}) or {}
    meta = payload.get("meta", {}) or {}

    company = fact.get("company")
    if company:
        return str(company).strip()

    title = str(meta.get("title", "") or "")
    url = str(meta.get("url", "") or "")
    combined = f"{title} {url}"

    hits = []
    for kw, comp in mapper.keyword_to_company.items():
        if kw.lower() in combined.lower():
            hits.append(comp)
    hits_unique = list(dict.fromkeys(hits))

    if len(hits_unique) >= 2:
        return "비교기사"

    inferred = mapper.infer(combined)
    return inferred if inferred else "미분류"


def _payload_is_recent_enough(payload: dict, cutoff_utc: datetime) -> bool:
    """
    전략 리포트 단계에서 facts payload를 필터링:
    - meta.published_date(YYYY-MM-DD)가 있으면 그 날짜 기준
    - 없으면 meta.collected_at_utc 기준
    """
    meta = payload.get("meta", {}) or {}

    pub = meta.get("published_date")
    if isinstance(pub, str) and len(pub) >= 10:
        try:
            dt = datetime.strptime(pub[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt >= cutoff_utc
        except Exception:
            pass

    collected_at = meta.get("collected_at_utc")
    if isinstance(collected_at, str) and collected_at:
        try:
            dt = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
            dt = _to_utc(dt)
            if dt is None:
                return False
            return dt >= cutoff_utc
        except Exception:
            return False

    return False


def run_fact_cache_mode(settings: Settings, collected: Dict[str, List[Item]]) -> None:
    """
    FACT_CACHE_MODE=true 일 때:
    - LOOKBACK_DAYS 이내 기사만 처리
    - (ALLOW_UNDATED_ITEMS=false면) published_at 없는 건 제외
    - URL 중복 제거 후 최대 MAX_FACT_ITEMS 개 Fact 추출
    """
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite").strip()
    max_items = _env_int("MAX_FACT_ITEMS", 15)

    lookback_days = _env_int("LOOKBACK_DAYS", 14)
    allow_undated = _env_bool("ALLOW_UNDATED_ITEMS", False)

    cutoff_utc = _now_utc() - timedelta(days=lookback_days)

    llm = _vertex_llm_from_env()
    extractor = FactExtractor(llm=llm)
    store = FactStore()

    all_items = dedup_by_url(_flatten(collected), lambda x: x.url)

    filtered: List[Item] = []
    skipped_old = 0
    skipped_undated = 0

    for it in all_items:
        pub = _to_utc(getattr(it, "published_at", None))
        if pub is None:
            if allow_undated:
                filtered.append(it)
            else:
                skipped_undated += 1
            continue

        if pub < cutoff_utc:
            skipped_old += 1
            continue

        filtered.append(it)

    saved = 0
    skipped_dup = 0
    failed = 0

    for it in filtered[:max_items]:
        published_date = it.published_at.strftime("%Y-%m-%d") if it.published_at else None

        if store.exists(url=it.url):
            skipped_dup += 1
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
        f"- LOOKBACK_DAYS: {lookback_days} (cutoff_utc={cutoff_utc.date()})\n"
        f"- 최대 처리: {max_items}\n"
        f"- 저장: {saved}\n"
        f"- 스킵(중복): {skipped_dup}\n"
        f"- 스킵(오래됨): {skipped_old}\n"
        f"- 스킵(날짜없음): {skipped_undated}\n"
        f"- 실패: {failed}\n"
    )
    send_to_slack(settings.slack_webhook_url, msg)


def run_weekly_strategy_report(settings: Settings) -> None:
    """
    data/facts/에 저장된 Fact payload들을 읽어
    - LOOKBACK_DAYS 이내 payload만 사용
    - company 보정 + 비교기사 분리
    - Signal(A/B/C) 분류 → A/B만 사용
    - '미분류'/'비교기사'는 가설 생성 제외
    - 경쟁사별 가설 → 원티드 대응 도출
    - 공고 샘플 기반 직무군 분포 섹션을 맨 아래에 추가
    - Slack 1페이지 리포트 전송
    """
    llm = _vertex_llm_from_env()

    lookback_days = _env_int("LOOKBACK_DAYS", 14)
    cutoff_utc = _now_utc() - timedelta(days=lookback_days)

    payloads = read_fact_payloads("data/facts")
    if not payloads:
        send_to_slack(settings.slack_webhook_url, "*전략 리포트 생성 실패*: data/facts에 Fact가 없습니다.")
        return

    payloads = [p for p in payloads if _payload_is_recent_enough(p, cutoff_utc)]
    if not payloads:
        send_to_slack(
            settings.slack_webhook_url,
            f"*전략 리포트 생성 실패*: LOOKBACK_DAYS={lookback_days} 기준으로 남는 Fact가 없습니다.",
        )
        return

    mapper = CompanyMapper.default()

    payloads_by_key: Dict[str, List[dict]] = {}
    for p in payloads:
        key = _infer_group_key(p, mapper)
        payloads_by_key.setdefault(key, []).append(p)

    classifier = SignalClassifier(llm=llm)
    hypothesizer = StrategyHypothesis(llm=llm)
    responder = WantedResponse(llm=llm)

    hypothesis_by_company: Dict[str, dict] = {}
    response_by_company: Dict[str, dict] = {}

    for key, plist in payloads_by_key.items():
        if key in ("미분류", "비교기사"):
            continue

        facts = [p.get("fact", {}) for p in plist if isinstance(p.get("fact", {}), dict)]

        ab_facts = []
        for f in facts:
            try:
                sig = classifier.classify(f)
                level = (sig.get("signal_level") or "").strip()
                if level in ("A", "B"):
                    f2 = dict(f)
                    f2["_signal"] = sig
                    ab_facts.append(f2)
            except Exception as e:
                print(f"[WARN] signal classify failed for {key}: {type(e).__name__}: {e}")

        if not ab_facts:
            continue

        hyp = hypothesizer.infer(ab_facts[:8])
        resp = responder.propose(hyp)

        hypothesis_by_company[key] = hyp
        response_by_company[key] = resp

    if not hypothesis_by_company:
        send_to_slack(settings.slack_webhook_url, "*전략 리포트 생성 실패*: A/B 신호 Fact가 없습니다.")
        return

    report_text = render_strategy_report(
        hypothesis_by_company=hypothesis_by_company,
        response_by_company=response_by_company,
        payloads_by_company=payloads_by_key,
    )

    # ---- Append Job Posting Analysis Section (Prototype) ----
    # URL/selector는 env로 주입 (없으면 섹션은 '스킵' 표기)
    job_sources = [
        CompetitorJobSource(
            name="사람인",
            list_url=os.environ.get("SARMIN_JOB_LIST_URL", "").strip(),
            link_css=os.environ.get("SARMIN_JOB_LINK_CSS", "a").strip(),
            limit=_env_int("JOB_SAMPLE_LIMIT", 30),
        ),
        CompetitorJobSource(
            name="잡코리아",
            list_url=os.environ.get("JOBKOREA_JOB_LIST_URL", "").strip(),
            link_css=os.environ.get("JOBKOREA_JOB_LINK_CSS", "a").strip(),
            limit=_env_int("JOB_SAMPLE_LIMIT", 30),
        ),
        CompetitorJobSource(
            name="리멤버",
            list_url=os.environ.get("REMEMBER_JOB_LIST_URL", "").strip(),
            link_css=os.environ.get("REMEMBER_JOB_LINK_CSS", "a").strip(),
            limit=_env_int("JOB_SAMPLE_LIMIT", 30),
        ),
    ]
    job_sources = [s for s in job_sources if s.list_url]

    if job_sources:
        jobs_section = build_jobs_section(job_sources)
        report_text = report_text.rstrip() + "\n\n" + jobs_section
    else:
        report_text = report_text.rstrip() + "\n\n" + "*[공고 샘플 기반 직무군 분포(경쟁사별)]*\n- (설정된 리스트 URL이 없어 스킵)\n"

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

    fact_cache_mode = _env_bool("FACT_CACHE_MODE", False)
    weekly_strategy_mode = _env_bool("WEEKLY_STRATEGY_REPORT_MODE", False)

    if fact_cache_mode:
        run_fact_cache_mode(settings, collected)

    if weekly_strategy_mode:
        run_weekly_strategy_report(settings)
        return

    if not fact_cache_mode:
        run_default_weekly_report(settings, collected)


if __name__ == "__main__":
    main()

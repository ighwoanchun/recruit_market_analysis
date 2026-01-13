FACT_EXTRACTION_PROMPT = """
너는 채용 플랫폼 산업 분석을 위한 리서치 어시스턴트다.
아래 입력에서 사실(Fact)만 추출하라. 해석/평가/추론 금지.
출력은 JSON으로만.

필드:
- source
- url
- date (원문에 있으면)
- company
- actions (list)
- new_or_change
- metrics (list of {name, value})
- uncertain (list)

입력:
"""

SIGNAL_CLASSIFICATION_PROMPT = """
아래 Fact(JSON)를 A/B/C로 분류하라.
A: 가격/BM/조직/투자/핵심상품 변화
B: 기능업데이트/제휴/타겟확장
C: 캠페인/인터뷰/메시지
출력은 JSON: {signal_level, reason, is_event_like, needs_followup}
입력:
"""

STRATEGY_HYPOTHESIS_PROMPT = """
너는 채용 플랫폼 전략 분석가다.
아래 Fact 목록을 바탕으로 '가설'만 도출하라(단정 금지).
출력은 JSON:
{
  "hypothesis": "...",
  "evidence": ["..."],
  "alt_hypothesis": ["..."],
  "falsifiers": ["..."]
}
입력:
"""

TREND_CONSISTENCY_PROMPT = """
아래 타임라인 Fact로 전략적 일관성(높음/중간/낮음)을 평가하라.
출력 JSON: {consistency, supporting_points, conflicting_points, observe_period_months}
입력:
"""

WANTED_RESPONSE_PROMPT = """
너는 원티드랩의 채용사업개발 전략 담당자다.
아래 경쟁사 전략 가설을 바탕으로 대응 옵션 3가지를 제시하라.
출력 JSON:
{
 "do_nothing": {"why": "...", "risks": ["..."]},
 "defensive": {"actions": ["..."], "impact": "...", "risks": ["..."]},
 "offensive": {"actions": ["..."], "impact": "...", "risks": ["..."]}
}
입력:
"""

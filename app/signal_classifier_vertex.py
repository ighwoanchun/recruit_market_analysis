from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .vertex_llm import VertexLLM


SYSTEM = """
너는 채용 플랫폼 시장 분석을 위한 분류기다.
입력 Fact(JSON)를 전략 신호 강도에 따라 A/B/C로 분류하라.
추측 금지, 입력 Fact에 근거해서만 판단하라.
출력은 반드시 JSON 하나만 반환한다.
"""

USER = """
다음 Fact(JSON)를 분류하라.

[분류 기준]
- A: 가격/수익모델(BM)/조직개편/투자/핵심상품 변화
- B: 기능 업데이트/제휴/타겟 확장/상품 실험
- C: 캠페인/인터뷰/홍보성 메시지(전략 근거 약함)

[출력 포맷(JSON)]
{{
  "signal_level": "A" | "B" | "C",
  "reason": string,
  "is_event_like": "high" | "medium" | "low",
  "needs_followup": true | false
}}

[입력 Fact]
{fact_json}
"""


@dataclass(frozen=True)
class SignalClassifier:
    llm: VertexLLM

    def classify(self, fact_json: Dict[str, Any]) -> Dict[str, Any]:
        prompt = USER.format(fact_json=fact_json)
        return self.llm.generate_json(system_instruction=SYSTEM.strip(), user_input=prompt, temperature=0.0)

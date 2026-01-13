from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from .vertex_llm import VertexLLM


SYSTEM = """
너는 채용 플랫폼 시장의 전략 분석가다.
입력된 Fact들만 근거로 '가설'을 만든다. 단정 금지.
출력은 반드시 JSON 하나만 반환한다.
"""

USER = """
아래 Fact 목록을 바탕으로 경쟁사의 전략적 의도를 '가설'로 도출하라.

[규칙]
- 단정 금지: "가능성이 높다/낮다" 같은 표현 사용
- 근거는 Fact에서만 인용
- 반증 가능성(falsifiers)을 반드시 포함
- 출력은 JSON만

[출력(JSON)]
{{
  "hypothesis": string,
  "evidence": [string],
  "alt_hypothesis": [string],
  "falsifiers": [string]
}}

[Fact 목록(JSON 배열)]
{facts}
"""


@dataclass(frozen=True)
class StrategyHypothesis:
    llm: VertexLLM

    def infer(self, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = USER.format(facts=json.dumps(facts, ensure_ascii=False))
        return self.llm.generate_json(system_instruction=SYSTEM.strip(), user_input=prompt, temperature=0.0)

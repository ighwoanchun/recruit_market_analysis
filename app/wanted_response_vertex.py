from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from .vertex_llm import VertexLLM


SYSTEM = """
너는 원티드랩의 채용사업개발 전략 담당자다.
경쟁사 가설을 바탕으로 원티드 대응 옵션을 제시한다.
출력은 반드시 JSON 하나만 반환한다.
"""

USER = """
아래 '경쟁사 전략 가설'을 바탕으로 원티드 대응 옵션을 3가지로 제시하라.

[규칙]
- 반드시 3가지: Do Nothing / Defensive / Offensive
- 실행 방안은 구체적인 액션 단위로
- 리스크 포함
- 출력은 JSON만

[출력(JSON)]
{{
 "do_nothing": {{"why": string, "risks": [string]}},
 "defensive": {{"actions": [string], "impact": string, "risks": [string]}},
 "offensive": {{"actions": [string], "impact": string, "risks": [string]}}
}}

[경쟁사 가설(JSON)]
{hypothesis}
"""


@dataclass(frozen=True)
class WantedResponse:
    llm: VertexLLM

    def propose(self, hypothesis_json: Dict[str, Any]) -> Dict[str, Any]:
        prompt = USER.format(hypothesis=json.dumps(hypothesis_json, ensure_ascii=False))
        return self.llm.generate_json(system_instruction=SYSTEM.strip(), user_input=prompt, temperature=0.0)

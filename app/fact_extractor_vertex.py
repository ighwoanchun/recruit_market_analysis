from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .vertex_llm import VertexLLM


SYSTEM_INSTRUCTION = """
너는 채용 플랫폼 산업 분석을 위한 리서치 어시스턴트다.
해석/평가/추론 없이, 입력 텍스트에서 '검증 가능한 사실(Fact)'만 구조화한다.
입력에 없는 정보는 절대 만들어내지 말고 "확인 불가"로 표시한다.
출력은 반드시 JSON 하나만 반환한다.
"""

USER_TEMPLATE = """
아래 자료에서 사실(Fact)만 추출해줘.

[출력 JSON 스키마]
{
  "source": string,
  "url": string,
  "date_in_text": string | null,
  "company": string | null,
  "facts": [
    {
      "what_happened": string,
      "is_new_or_change": "new" | "change" | "unknown",
      "related_area": string | null,
      "numbers": [{"name": string, "value": string}] 
    }
  ],
  "uncertain": [string]
}

[규칙]
- 기사/공지에 명시된 내용만. 추측 금지.
- company는 텍스트에서 특정 가능하면 넣고, 아니면 null.
- 숫자/지표는 원문 표현 그대로 value에 저장.
- date_in_text는 텍스트에 '명시된 날짜'가 있으면 넣고, 없으면 null.

[입력]
SOURCE: {source}
URL: {url}
TITLE: {title}
TEXT:
{raw_text}
"""


@dataclass(frozen=True)
class FactExtractor:
    llm: VertexLLM

    def extract(self, *, source: str, url: str, title: str, raw_text: str) -> Dict[str, Any]:
        prompt = USER_TEMPLATE.format(
            source=source,
            url=url,
            title=title,
            raw_text=raw_text,
        )
        return self.llm.generate_json(
            system_instruction=SYSTEM_INSTRUCTION.strip(),
            user_input=prompt,
            temperature=0.0,
            max_output_tokens=2048,
        )

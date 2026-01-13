from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class CompanyMapper:
    """
    회사명 보정 규칙:
    - Fact에 company가 없으면 (title + url)을 기준으로 키워드 매칭
    - 가장 먼저 매칭되는 회사로 할당
    """
    keyword_to_company: Dict[str, str]

    @staticmethod
    def default() -> "CompanyMapper":
        # 필요 시 키워드 계속 추가하면 됨
        return CompanyMapper(
            keyword_to_company={
                "사람인": "사람인",
                "saramin": "사람인",
                "잡코리아": "잡코리아",
                "jobkorea": "잡코리아",
                "리멤버": "리멤버",
                "remember": "리멤버",
                "원티드": "원티드",
                "wanted": "원티드",
            }
        )

    def infer(self, text: str) -> Optional[str]:
        t = (text or "").lower()
        for k, company in self.keyword_to_company.items():
            if k.lower() in t:
                return company
        return None

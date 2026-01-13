from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


def group_by_company(facts_payloads: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups = defaultdict(list)
    for payload in facts_payloads:
        fact = payload.get("fact", {})
        company = fact.get("company") or "미분류"
        groups[company].append(payload)
    return dict(groups)


def render_weekly_strategy_report(
    *,
    hypothesis_by_company: Dict[str, Dict[str, Any]],
    response_by_company: Dict[str, Dict[str, Any]],
    evidence_payloads_by_company: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines = []
    lines.append("*[주간 경쟁사 전략 리포트]*")
    lines.append("")

    for company, hyp in hypothesis_by_company.items():
        lines.append(f"## {company}")

        # 가설
        lines.append(f"- ※ 가설: {hyp.get('hypothesis', '확인 불가')}")
        ev = hyp.get("evidence", []) or []
        if ev:
            lines.append("  - 근거(Fact):")
            for e in ev[:5]:
                lines.append(f"    - {e}")

        # 근거 링크(최근 3개)
        evid_payloads = evidence_payloads_by_company.get(company, [])
        if evid_payloads:
            lines.append("  - 관련 링크:")
            for p in evid_payloads[:3]:
                meta = p.get("meta", {})
                title = meta.get("title", "제목 확인 불가")
                url = meta.get("url", "")
                lines.append(f"    - {title} — {url}")

        # 원티드 대응
        resp = response_by_company.get(company, {})
        lines.append("")
        lines.append("- → 대응 옵션:")
        dn = resp.get("do_nothing", {})
        df = resp.get("defensive", {})
        of = resp.get("offensive", {})
        lines.append(f"  - Do Nothing: {dn.get('why','')}")
        lines.append(f"  - Defensive: {', '.join(df.get('actions', []) or [])}")
        lines.append(f"  - Offensive: {', '.join(of.get('actions', []) or [])}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"

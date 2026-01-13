from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple


def group_payloads_by_company(payloads: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups = defaultdict(list)
    for p in payloads:
        fact = p.get("fact", {})
        company = fact.get("company") or "미분류"
        groups[company].append(p)
    return dict(groups)


def extract_evidence_links(payloads: List[Dict[str, Any]], limit: int = 3) -> List[Tuple[str, str]]:
    links = []
    for p in payloads:
        meta = p.get("meta", {})
        title = meta.get("title", "제목 확인 불가")
        url = meta.get("url", "")
        if url:
            links.append((title, url))
        if len(links) >= limit:
            break
    return links


def render_strategy_report(
    *,
    hypothesis_by_company: Dict[str, Dict[str, Any]],
    response_by_company: Dict[str, Dict[str, Any]],
    payloads_by_company: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines: List[str] = []
    lines.append("*[주간 경쟁사 전략 리포트]*")
    lines.append("")

    for company in sorted(hypothesis_by_company.keys()):
        hyp = hypothesis_by_company[company]
        resp = response_by_company.get(company, {})
        payloads = payloads_by_company.get(company, [])

        lines.append(f"*■ {company}*")

        # hypothesis
        lines.append(f"- ※ 가설: {hyp.get('hypothesis', '확인 불가')}")
        ev = hyp.get("evidence", []) or []
        if ev:
            lines.append("  - 근거(Fact):")
            for e in ev[:4]:
                lines.append(f"    - {e}")

        # links
        links = extract_evidence_links(payloads, limit=3)
        if links:
            lines.append("  - 출처 링크:")
            for t, u in links:
                lines.append(f"    - {t} — {u}")

        # response
        lines.append("- → 원티드 대응 옵션:")
        dn = resp.get("do_nothing", {})
        df = resp.get("defensive", {})
        of = resp.get("offensive", {})

        if dn:
            lines.append(f"  - Do Nothing: {dn.get('why','')}")
        if df:
            actions = ", ".join(df.get("actions", []) or [])
            lines.append(f"  - Defensive: {actions}")
        if of:
            actions = ", ".join(of.get("actions", []) or [])
            lines.append(f"  - Offensive: {actions}")

        lines.append("")

    return "\n".join(lines).strip() + "\n"

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple


def group_payloads_by_company(payloads: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    우선순위:
    1) fact.company가 있으면 사용
    2) 없으면 meta.title + meta.url에서 키워드 매칭으로 보정
    3) 그래도 없으면 '미분류'

    추가 규칙(섞임 최소화):
    - title/url에서 2개 이상 경쟁사 키워드가 동시에 강하게 잡히는 경우(예: '잡코리아, 사람인 ...')
      -> '미분류'로 보내지 말고, 그냥 '비교기사' 그룹으로 따로 분리
    """
    mapper = CompanyMapper.default()
    groups = defaultdict(list)

    for p in payloads:
        fact = p.get("fact", {}) or {}
        meta = p.get("meta", {}) or {}

        company = fact.get("company")
        if company:
            key = str(company).strip()
        else:
            title = str(meta.get("title", "") or "")
            url = str(meta.get("url", "") or "")
            combined = f"{title} {url}"

            # 간단한 "복수 경쟁사 언급" 감지: 기본 키워드 중 몇 개가 들어가나
            hits = []
            for kw, comp in mapper.keyword_to_company.items():
                if kw.lower() in combined.lower():
                    hits.append(comp)
            hits_unique = list(dict.fromkeys(hits))  # preserve order unique

            if len(hits_unique) >= 2:
                key = "비교기사"
            else:
                inferred = mapper.infer(combined)
                key = inferred if inferred else "미분류"

        groups[key].append(p)

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

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class JobPosting:
    source: str
    url: str
    title: str


def fetch_html(url: str, timeout: int = 20) -> str:
    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; wanted-competitor-monitor/0.1)",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.text


def scrape_list_page_by_href(
    *,
    source: str,
    list_url: str,
    href_contains: str,
    limit: int = 30,
    sleep_sec: float = 1.0,
) -> List[JobPosting]:
    """
    list_url 페이지에서 <a>들을 훑어,
    href에 href_contains 문자열이 포함된 링크만 공고로 간주해 수집한다.
    (CSS selector보다 페이지 변경에 강함)

    예:
      href_contains="/job/posting/"
      href_contains="Recruit/GI_Read"
      href_contains="job-search/view?cn=theme"
    """
    html = fetch_html(list_url)
    soup = BeautifulSoup(html, "html.parser")

    out: List[JobPosting] = []

    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue

        href_str = str(href)
        if href_contains not in href_str:
            continue

        url = href_str if href_str.startswith("http") else urljoin(list_url, href_str)
        title = (a.get_text() or "").strip()

        # 제목이 너무 짧거나 공백이면 제외(노이즈 링크 방지)
        if len(title) < 2:
            continue

        out.append(JobPosting(source=source, url=url, title=title))
        if len(out) >= limit:
            break

    time.sleep(sleep_sec)
    return out


def analyze_titles_basic(posts: List[JobPosting]) -> Dict[str, int]:
    """
    매우 단순한 키워드 기반 직무군 분류(샘플 N개 기준).
    '직군별 공고 수'를 빠르게 보기 위한 MVP.
    """
    buckets = {"개발": 0, "데이터/AI": 0, "영업": 0, "마케팅": 0, "디자인": 0, "기타": 0}
    for p in posts:
        t = p.title.lower()

        if any(k in t for k in ["backend", "front", "fullstack", "engineer", "developer", "개발", "서버", "프론트", "백엔드"]):
            buckets["개발"] += 1
        elif any(k in t for k in ["data", "ml", "ai", "분석", "데이터", "머신러닝", "모델"]):
            buckets["데이터/AI"] += 1
        elif any(k in t for k in ["sales", "영업", "bd", "bizdev", "ae", "am"]):
            buckets["영업"] += 1
        elif any(k in t for k in ["marketing", "마케팅", "growth", "그로스", "브랜딩", "퍼포먼스"]):
            buckets["마케팅"] += 1
        elif any(k in t for k in ["design", "designer", "디자인", "ui", "ux", "product designer"]):
            buckets["디자인"] += 1
        else:
            buckets["기타"] += 1

    return buckets

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Dict
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
        headers={"User-Agent": "Mozilla/5.0 (compatible; wanted-competitor-monitor/0.1)"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.text


def scrape_list_page(source: str, list_url: str, link_css: str, limit: int = 30, sleep_sec: float = 1.0) -> List[JobPosting]:
    """
    list_url: 공고 리스트 페이지
    link_css: 공고 상세로 가는 <a> selector (예: 'a.job-link')
    """
    html = fetch_html(list_url)
    soup = BeautifulSoup(html, "html.parser")

    out: List[JobPosting] = []
    for a in soup.select(link_css):
        href = a.get("href")
        if not href:
            continue
        url = href if href.startswith("http") else urljoin(list_url, href)
        title = (a.get_text() or "").strip()
        if not title:
            continue
        out.append(JobPosting(source=source, url=url, title=title))
        if len(out) >= limit:
            break

    time.sleep(sleep_sec)
    return out


def analyze_titles_basic(posts: List[JobPosting]) -> Dict[str, int]:
    """
    매우 단순한 키워드 기반 직무군 분류(프로토타입).
    """
    buckets = {"개발": 0, "데이터/AI": 0, "영업": 0, "마케팅": 0, "디자인": 0, "기타": 0}
    for p in posts:
        t = p.title.lower()
        if any(k in t for k in ["backend", "front", "software", "engineer", "개발", "서버", "프론트", "백엔드"]):
            buckets["개발"] += 1
        elif any(k in t for k in ["data", "ml", "ai", "분석", "데이터", "머신러닝"]):
            buckets["데이터/AI"] += 1
        elif any(k in t for k in ["sales", "영업", "bd", "bizdev"]):
            buckets["영업"] += 1
        elif any(k in t for k in ["marketing", "마케팅", "growth", "그로스"]):
            buckets["마케팅"] += 1
        elif any(k in t for k in ["design", "designer", "디자인", "ui", "ux"]):
            buckets["디자인"] += 1
        else:
            buckets["기타"] += 1
    return buckets

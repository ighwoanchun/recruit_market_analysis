from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import feedparser


@dataclass
class Item:
    title: str
    url: str
    published_at: Optional[datetime]
    source: str
    raw_summary: str


def google_news_rss_url(query: str, hl: str = "ko", gl: str = "KR", ceid: str = "KR:ko") -> str:
    # Example: https://news.google.com/rss/search?q=...&hl=ko&gl=KR&ceid=KR:ko
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def fetch_rss(url: str, source_name: str) -> List[Item]:
    feed = feedparser.parse(url)
    items: List[Item] = []

    for e in feed.entries:
        published_at = None
        # feedparser may expose 'published_parsed'
        if getattr(e, "published_parsed", None):
            published_at = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)

        items.append(
            Item(
                title=getattr(e, "title", "").strip(),
                url=getattr(e, "link", "").strip(),
                published_at=published_at,
                source=source_name,
                raw_summary=getattr(e, "summary", "").strip(),
            )
        )
    return items


def collect_news_for_competitor(competitor_name: str) -> List[Item]:
    # You can refine queries per competitor.
    query = f"{competitor_name} 채용 플랫폼 OR 채용서비스 OR 공고 OR 업데이트 OR 투자 OR 제휴"
    url = google_news_rss_url(query)
    return fetch_rss(url, source_name="Google News RSS")

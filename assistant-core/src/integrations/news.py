from __future__ import annotations

import email.utils
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


class NewsService:
    def __init__(self, providers_config: dict[str, Any]) -> None:
        self.config = providers_config.get("news", {})
        self.enabled = bool(self.config.get("enabled", False))
        self.language = str(self.config.get("language", "ru")).strip() or "ru"
        self.region = str(self.config.get("region", "RU")).strip() or "RU"
        self.default_topics = [str(item).strip() for item in self.config.get("default_topics", []) if str(item).strip()]
        self.top_rss_url = str(
            self.config.get("top_rss_url", "https://news.google.com/rss")
        ).rstrip("/")
        self.search_rss_url = str(
            self.config.get("search_rss_url", "https://news.google.com/rss/search")
        ).rstrip("/")

    def healthcheck(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": "google-news-rss",
            "default_topics": self.default_topics,
        }

    def get_news(self, topic: str | None = None, limit: int = 5) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "message": "News provider disabled"}
        limit = max(1, min(int(limit), 10))
        query_topic = (topic or "").strip()
        try:
            items = self._fetch_feed(query_topic=query_topic, limit=limit)
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "message": f"News lookup failed: {exc}"}
        if not items:
            return {"ok": False, "message": "No news items found"}
        return {
            "ok": True,
            "message": f"Fetched {len(items)} news items",
            "data": {
                "topic": query_topic or ", ".join(self.default_topics),
                "items": items,
            },
        }

    def _fetch_feed(self, query_topic: str, limit: int) -> list[dict[str, Any]]:
        params = {
            "hl": self.language,
            "gl": self.region,
            "ceid": f"{self.region}:{self.language}",
        }
        if query_topic:
            params["q"] = query_topic
            url = f"{self.search_rss_url}?{urllib.parse.urlencode(params)}"
        else:
            url = f"{self.top_rss_url}?{urllib.parse.urlencode(params)}"

        with urllib.request.urlopen(url, timeout=15) as response:
            payload = response.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(payload)
        items: list[dict[str, Any]] = []
        for item in root.findall("./channel/item")[:limit]:
            pub_date = item.findtext("pubDate", default="")
            parsed_date = email.utils.parsedate_to_datetime(pub_date).isoformat() if pub_date else ""
            items.append(
                {
                    "title": self._clean_text(item.findtext("title", default="")),
                    "link": item.findtext("link", default=""),
                    "published_at": parsed_date,
                    "source": self._clean_text(item.findtext("source", default="")),
                    "description": self._clean_text(item.findtext("description", default="")),
                }
            )
        return items

    def _clean_text(self, value: str) -> str:
        text = html.unescape(value or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from news_models import NewsItem
from utils import parse_datetime, read_json, strip_html, to_iso, within_period

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; AAPP-Political-NotesBot/2.0; +https://www.bbva.com)"
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def _fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _retry_after_seconds(exc: urllib.error.HTTPError, default: float) -> float:
    raw = exc.headers.get("Retry-After") if exc.headers else None
    if raw:
        try:
            return max(default, float(raw))
        except ValueError:
            return default
    return default


def _safe_fetch_text(url: str, label: str, timeout: int = 25, max_retries: int = 1, backoff_seconds: float = 2.0) -> str:
    for attempt in range(max_retries + 1):
        try:
            return _fetch_text(url, timeout=timeout)
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", None)
            if code in RETRYABLE_HTTP_CODES and attempt < max_retries:
                wait = _retry_after_seconds(exc, backoff_seconds * (2 ** attempt))
                logger.warning(
                    "event=fetch_retry label=%s status=%s attempt=%s/%s wait_seconds=%.1f url=%s",
                    label,
                    code,
                    attempt + 1,
                    max_retries,
                    wait,
                    url,
                )
                time.sleep(wait)
                continue
            logger.warning("event=fetch_failed label=%s status=%s reason=%s url=%s", label, code, exc.reason, url)
            return ""
        except Exception as exc:  # network instability should not break the whole report
            if attempt < max_retries:
                wait = backoff_seconds * (2 ** attempt)
                logger.warning("event=fetch_retry label=%s attempt=%s/%s wait_seconds=%.1f reason=%s", label, attempt + 1, max_retries, wait, exc)
                time.sleep(wait)
                continue
            logger.warning("event=fetch_failed label=%s reason=%s url=%s", label, exc, url)
            return ""
    return ""


def _xml_text(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return strip_html(node.text)


def parse_rss(xml_text: str, source_name: str, collector: str, query: str = "") -> list[NewsItem]:
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
        logger.warning("event=rss_parse_failed source=%s reason=%s", source_name, exc)
        return []

    items: list[NewsItem] = []
    for item in root.findall(".//item"):
        title = _xml_text(item.find("title"))
        link = _xml_text(item.find("link"))
        pub_date = _xml_text(item.find("pubDate")) or _xml_text(item.find("published"))
        description = _xml_text(item.find("description"))
        source = _xml_text(item.find("source")) or source_name
        if not title and not link:
            continue
        dt = parse_datetime(pub_date)
        items.append(
            NewsItem(
                title=title,
                url=link,
                source=source,
                published_at=to_iso(dt) if dt else pub_date,
                summary=description,
                collector=collector,
                query=query,
            )
        )
    return items


def build_google_news_url(query: str, period_days: int, locale: dict[str, str]) -> str:
    hl = locale.get("hl", "es-419")
    gl = locale.get("gl", "AR")
    ceid = locale.get("ceid", "AR:es-419")
    q = f"{query} when:{period_days}d"
    params = urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid})
    return f"https://news.google.com/rss/search?{params}"


def collect_google_news(config: dict[str, Any], start: datetime, end: datetime, period_days: int) -> list[NewsItem]:
    google_cfg = config.get("google_news", {})
    if not google_cfg.get("enabled", True):
        return []
    locale = google_cfg.get("locale", {})
    delay = float(google_cfg.get("request_delay_seconds", 0.8))
    max_retries = int(google_cfg.get("max_retries", 1))
    backoff = float(google_cfg.get("backoff_seconds", 2.0))
    items: list[NewsItem] = []
    for idx, query in enumerate(google_cfg.get("queries", [])):
        url = build_google_news_url(query, period_days=period_days, locale=locale)
        xml_text = _safe_fetch_text(url, label="google_news", max_retries=max_retries, backoff_seconds=backoff)
        parsed = parse_rss(xml_text, source_name="Google News", collector="google_news", query=query)
        items.extend([item for item in parsed if within_period(item.published_at, start, end)])
        if idx < len(google_cfg.get("queries", [])) - 1:
            time.sleep(delay)
    return items


def build_gdelt_url(query: str, start: datetime, end: datetime, max_records: int) -> str:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "hybridrel",
        "startdatetime": start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
    }
    return "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)


def collect_gdelt(config: dict[str, Any], start: datetime, end: datetime) -> list[NewsItem]:
    gdelt_cfg = config.get("gdelt", {})
    if not gdelt_cfg.get("enabled", True):
        return []
    max_records = int(gdelt_cfg.get("max_records_per_query", 10))
    delay = float(gdelt_cfg.get("request_delay_seconds", 8.0))
    max_retries = int(gdelt_cfg.get("max_retries", 1))
    backoff = float(gdelt_cfg.get("backoff_seconds", 5.0))
    items: list[NewsItem] = []
    queries = gdelt_cfg.get("queries", [])
    for idx, query in enumerate(queries):
        url = build_gdelt_url(query, start=start, end=end, max_records=max_records)
        text = _safe_fetch_text(url, label="gdelt", max_retries=max_retries, backoff_seconds=backoff)
        if text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                logger.warning("event=gdelt_json_failed query=%s reason=%s", query, exc)
                payload = {}
            for article in payload.get("articles", []):
                title = article.get("title") or ""
                link = article.get("url") or ""
                if not title and not link:
                    continue
                dt = parse_datetime(article.get("seendate") or article.get("publishedAt"))
                source = article.get("sourceCommonName") or article.get("domain") or "GDELT"
                items.append(
                    NewsItem(
                        title=title,
                        url=link,
                        source=source,
                        published_at=to_iso(dt) if dt else str(article.get("seendate") or ""),
                        summary=strip_html(article.get("snippet") or article.get("description") or ""),
                        collector="gdelt",
                        query=query,
                        metadata={
                            "domain": article.get("domain"),
                            "language": article.get("language"),
                            "source_country": article.get("sourceCountry"),
                        },
                    )
                )
        if idx < len(queries) - 1:
            time.sleep(delay)
    return [item for item in items if within_period(item.published_at, start, end)]


def collect_rss_feeds(config: dict[str, Any], start: datetime, end: datetime) -> list[NewsItem]:
    items: list[NewsItem] = []
    for idx, feed in enumerate(config.get("rss_feeds", [])):
        if not feed.get("enabled", False):
            continue
        url = feed.get("url") or ""
        if not url:
            continue
        delay = float(feed.get("request_delay_seconds", 1.0))
        xml_text = _safe_fetch_text(url, label="rss_feed", max_retries=int(feed.get("max_retries", 1)), backoff_seconds=float(feed.get("backoff_seconds", 2.0)))
        parsed = parse_rss(xml_text, source_name=feed.get("name", "RSS"), collector="rss_feed", query=feed.get("category", ""))
        items.extend([item for item in parsed if within_period(item.published_at, start, end)])
        if idx < len(config.get("rss_feeds", [])) - 1:
            time.sleep(delay)
    return items


def collect_news(config_path: Path, start: datetime, end: datetime, period_days: int) -> list[NewsItem]:
    config = read_json(config_path, default={}) or {}
    items: list[NewsItem] = []
    items.extend(collect_google_news(config, start=start, end=end, period_days=period_days))
    items.extend(collect_gdelt(config, start=start, end=end))
    items.extend(collect_rss_feeds(config, start=start, end=end))
    return items

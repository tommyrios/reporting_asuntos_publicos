from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from news_models import NewsItem
from utils import read_json, write_json

DEFAULT_HISTORY = {"used_urls": [], "used_fingerprints": [], "reports": []}


def load_history(path: Path) -> dict[str, Any]:
    history = read_json(path, default=DEFAULT_HISTORY.copy()) or DEFAULT_HISTORY.copy()
    history.setdefault("used_urls", [])
    history.setdefault("used_fingerprints", [])
    history.setdefault("reports", [])
    return history


def filter_used_news(items: list[NewsItem], history: dict[str, Any]) -> tuple[list[NewsItem], list[NewsItem]]:
    used_urls = set(history.get("used_urls", []))
    used_fingerprints = set(history.get("used_fingerprints", []))
    fresh: list[NewsItem] = []
    removed: list[NewsItem] = []
    for item in items:
        already_used = bool(item.canonical_url and item.canonical_url in used_urls) or item.fingerprint in used_fingerprints
        if already_used:
            removed.append(item)
        else:
            fresh.append(item)
    return fresh, removed


def update_history(path: Path, report_id: str, selected_items: list[NewsItem], metadata: dict[str, Any]) -> None:
    history = load_history(path)
    used_urls = set(history.get("used_urls", []))
    used_fingerprints = set(history.get("used_fingerprints", []))
    for item in selected_items:
        if item.canonical_url:
            used_urls.add(item.canonical_url)
        if item.fingerprint:
            used_fingerprints.add(item.fingerprint)

    history["used_urls"] = sorted(used_urls)
    history["used_fingerprints"] = sorted(used_fingerprints)
    history.setdefault("reports", []).append(
        {
            "report_id": report_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "selected_count": len(selected_items),
            "selected_fingerprints": [item.fingerprint for item in selected_items],
            "metadata": metadata,
        }
    )
    write_json(path, history)

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from news_models import NewsItem
from utils import compact_hash, normalize_text


def title_similarity(a: str, b: str) -> float:
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    if not a_n or not b_n:
        return 0.0
    return SequenceMatcher(None, a_n, b_n).ratio()


def deduplicate_news(
    items: Iterable[NewsItem],
    title_similarity_threshold: float = 0.88,
) -> tuple[list[NewsItem], list[NewsItem]]:
    unique: list[NewsItem] = []
    duplicates: list[NewsItem] = []

    for item in items:
        if not item.title and not item.url:
            continue
        matched: NewsItem | None = None
        for existing in unique:
            same_url = bool(item.canonical_url and item.canonical_url == existing.canonical_url)
            similar_title = title_similarity(item.title, existing.title) >= title_similarity_threshold
            if same_url or similar_title:
                matched = existing
                break
        if matched:
            item.duplicate_of = matched.fingerprint
            duplicates.append(item)
            continue
        item.cluster_id = f"cluster_{compact_hash(item.normalized_title or item.canonical_url, 10)}"
        unique.append(item)

    return unique, duplicates


def group_by_cluster(items: Iterable[NewsItem]) -> dict[str, list[NewsItem]]:
    clusters: dict[str, list[NewsItem]] = {}
    for item in items:
        clusters.setdefault(item.cluster_id, []).append(item)
    return clusters

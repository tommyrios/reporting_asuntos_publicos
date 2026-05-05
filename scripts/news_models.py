from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from utils import canonicalize_url, compact_hash, normalize_text


@dataclass
class NewsItem:
    title: str
    url: str
    source: str = ""
    published_at: str = ""
    summary: str = ""
    collector: str = ""
    query: str = ""
    canonical_url: str = ""
    normalized_title: str = ""
    fingerprint: str = ""
    topics: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    relevance_score: int = 0
    impact_level: str = "bajo"
    bbva_relevance: str = ""
    cluster_id: str = ""
    duplicate_of: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.canonical_url:
            self.canonical_url = canonicalize_url(self.url)
        if not self.normalized_title:
            self.normalized_title = normalize_text(self.title)
        if not self.fingerprint:
            base = self.normalized_title or self.canonical_url or self.url
            self.fingerprint = compact_hash(base, 16)
        if not self.cluster_id:
            self.cluster_id = f"cluster_{self.fingerprint[:10]}"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NewsItem":
        allowed = cls.__dataclass_fields__.keys()
        data = {key: payload.get(key) for key in allowed if key in payload}
        data.setdefault("title", payload.get("title", ""))
        data.setdefault("url", payload.get("url", ""))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def news_from_dicts(payloads: list[dict[str, Any]]) -> list[NewsItem]:
    return [NewsItem.from_dict(item) for item in payloads if item.get("title") or item.get("url")]


def news_to_dicts(items: list[NewsItem]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]

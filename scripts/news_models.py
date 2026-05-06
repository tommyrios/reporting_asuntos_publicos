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
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.canonical_url = self.canonical_url or canonicalize_url(self.url)
        self.normalized_title = self.normalized_title or normalize_text(self.title)
        self.fingerprint = self.fingerprint or compact_hash(self.normalized_title or self.canonical_url or self.url, 16)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NewsItem":
        allowed = cls.__dataclass_fields__.keys()
        data = {key: payload.get(key) for key in allowed if key in payload}
        data.setdefault("title", payload.get("title", ""))
        data.setdefault("url", payload.get("url", ""))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NewsCluster:
    cluster_id: str
    title: str
    summary: str = ""
    items: list[NewsItem] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    score: float = 0.0
    source_count: int = 0
    article_count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    representative_titles: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["items"] = [item.to_dict() for item in self.items]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NewsCluster":
        items = [NewsItem.from_dict(item) for item in payload.get("items", [])]
        data = dict(payload)
        data["items"] = items
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def news_from_dicts(payloads: list[dict[str, Any]]) -> list[NewsItem]:
    return [NewsItem.from_dict(item) for item in payloads if item.get("title") or item.get("url")]


def news_to_dicts(items: list[NewsItem]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


def clusters_to_dicts(clusters: list[NewsCluster]) -> list[dict[str, Any]]:
    return [cluster.to_dict() for cluster in clusters]

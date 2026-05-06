from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

from news_models import NewsCluster, NewsItem
from editorial_guard import strip_media_terms, sanitize_final_text
from utils import compact_hash, normalize_text, parse_datetime, truncate

STOPWORDS = {
    "argentina", "argentino", "argentina", "gobierno", "nacion", "nacional", "politica", "politico", "politicos",
    "tras", "ante", "segun", "para", "sobre", "entre", "desde", "hasta", "como", "pero", "este", "esta", "esta", "estos",
    "estas", "nuevo", "nueva", "nuevos", "nuevas", "dijo", "afirmo", "aseguro", "analiza", "busca", "anticipa",
    "ultimas", "ultima", "minuto", "vivo", "hoy", "ayer", "manana", "semana", "quincena",
}

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "congreso": ["congreso", "diputados", "senado", "comision", "sesion", "ley", "dictamen", "quorum", "jefe de gabinete"],
    "gobernabilidad": ["gobierno", "casa rosada", "presidente", "gabinete", "oficialismo", "gobernabilidad", "decreto", "veto"],
    "oposicion": ["oposicion", "peronismo", "kicillof", "ucr", "pro", "bloques", "kirchnerismo", "coalicion"],
    "protesta_social": ["cgt", "sindicato", "gremio", "paro", "marcha", "movilizacion", "protesta", "calle", "conflictividad"],
    "opinion_publica": ["encuesta", "imagen", "desaprobacion", "aprobacion", "opinion publica", "humor social"],
    "economia_politica": ["inflacion", "empleo", "salarios", "tarifas", "actividad", "recesion", "consumo", "fmi", "deuda"],
    "judicial_corrupcion": ["corrupcion", "justicia", "causa", "denuncia", "investigacion", "corte", "jueces"],
}

ACTOR_KEYWORDS: dict[str, list[str]] = {
    "Poder Ejecutivo": ["gobierno", "casa rosada", "presidente", "jefe de gabinete", "gabinete"],
    "Congreso": ["congreso", "diputados", "senado", "comision", "sesion"],
    "Gobernadores": ["gobernadores", "provincias", "mandatarios"],
    "Oposición": ["oposicion", "peronismo", "ucr", "pro", "kirchnerismo", "bloques"],
    "Sindicatos": ["cgt", "sindicato", "gremio", "paro", "movilizacion"],
    "Opinión pública": ["encuesta", "imagen", "desaprobacion", "opinion publica"],
}

TOPIC_WEIGHTS = {
    "congreso": 18,
    "gobernabilidad": 18,
    "oposicion": 14,
    "protesta_social": 14,
    "opinion_publica": 12,
    "economia_politica": 14,
    "judicial_corrupcion": 10,
}


# Editorial buckets: broader than the raw similarity clusters. They are used to
# merge many small clusters that actually describe the same political issue.
# Example: three different headlines about PASO / Ficha Limpia / reforma
# electoral must become one development, not three repeated bullets.
THEME_BUCKETS: dict[str, list[str]] = {
    "reforma_electoral": [
        "reforma electoral", "paso", "ficha limpia", "maniobra electoral", "boleta", "calendario electoral",
    ],
    "congreso_jefatura_gabinete": [
        "jefe de gabinete", "adorni", "informe de gestion", "informe de gestión", "diputados",
        "congreso", "camara", "cámara", "sesion", "sesión", "renunciar", "interpelacion", "interpelación",
    ],
    "gobernadores_provincias": [
        "gobernadores", "provincias", "patagon", "patagón", "patagonia", "zonas frias", "zonas frías",
        "subsidios", "transferencias", "adelanto", "coparticipacion", "coparticipación",
    ],
    "opinion_publica": [
        "encuesta", "imagen", "desaprobacion", "desaprobación", "aprobacion", "aprobación",
        "opinion publica", "opinión pública", "humor social", "desgaste social", "malestar",
    ],
    "conflictividad_social": [
        "cgt", "sindicato", "gremio", "paro", "marcha", "movilizacion", "movilización",
        "protesta", "calle", "conflictividad",
    ],
    "economia_politica": [
        "inflacion", "inflación", "recesion", "recesión", "empleo", "desempleo", "salarios",
        "tarifas", "consumo", "prepagas", "ingresos", "fmi", "deuda",
    ],
    "oposicion_reordenamiento": [
        "oposicion", "oposición", "peronismo", "kicillof", "ucr", "pro", "kirchnerismo",
        "bloques opositores", "alternativa politica", "alternativa política",
    ],
    "integridad_gestion": [
        "corrupcion", "corrupción", "denuncia", "investigacion", "investigación", "causa",
        "integridad", "nucleoelectrica", "nucleoeléctrica", "reidel",
    ],
}

BUCKET_PRIORITY = {
    "reforma_electoral": 8,
    "congreso_jefatura_gabinete": 7,
    "gobernadores_provincias": 7,
    "opinion_publica": 6,
    "conflictividad_social": 6,
    "economia_politica": 6,
    "oposicion_reordenamiento": 5,
    "integridad_gestion": 5,
}


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host.replace("www.", "")
    except Exception:
        return ""


def _tokens(text: str) -> set[str]:
    normalized = normalize_text(text)
    words = [w for w in re.split(r"\s+", normalized) if len(w) >= 4 and w not in STOPWORDS]
    return set(words)


def _text_for_item(item: NewsItem) -> str:
    return " ".join([item.title, item.summary, item.query])


def _similarity(a: NewsItem, b: NewsItem) -> float:
    ta = _tokens(_text_for_item(a))
    tb = _tokens(_text_for_item(b))
    if not ta or not tb:
        return 0.0
    shared = ta & tb
    if len(shared) < 3:
        return 0.0
    jaccard = len(shared) / max(1, len(ta | tb))
    overlap_ratio = len(shared) / max(1, min(len(ta), len(tb)))
    # SequenceMatcher can overestimate unrelated Spanish headlines with similar sentence shape.
    # Use it only as secondary lift after shared-token validation.
    seq = SequenceMatcher(None, a.normalized_title, b.normalized_title).ratio()
    return max(jaccard, overlap_ratio, seq * 0.35)


def detect_topics(text: str) -> list[str]:
    normalized = normalize_text(text)
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(normalize_text(keyword) in normalized for keyword in keywords):
            topics.append(topic)
    return topics


def detect_actors(text: str) -> list[str]:
    normalized = normalize_text(text)
    actors = []
    for actor, keywords in ACTOR_KEYWORDS.items():
        if any(normalize_text(keyword) in normalized for keyword in keywords):
            actors.append(actor)
    return actors


def _latest_first(items: list[NewsItem]) -> list[NewsItem]:
    def key(item: NewsItem) -> datetime:
        return parse_datetime(item.published_at) or datetime.min.replace(tzinfo=timezone.utc)
    return sorted(items, key=key, reverse=True)


def _representative_title(items: list[NewsItem]) -> str:
    titles = [strip_media_terms(item.title).strip() for item in items if item.title.strip()]
    if not titles:
        return "Hecho político sin título"
    # Prefer the title with more overlap with the rest of the cluster.
    token_sets = [_tokens(title) for title in titles]
    scores = []
    for idx, title_tokens in enumerate(token_sets):
        overlap = sum(len(title_tokens & other) for j, other in enumerate(token_sets) if j != idx)
        scores.append((overlap, len(titles[idx]), titles[idx]))
    scores.sort(reverse=True)
    return scores[0][2]


def _cluster_summary(items: list[NewsItem], max_chars: int = 900) -> str:
    snippets = []
    for item in _latest_first(items)[:6]:
        if item.summary:
            snippets.append(strip_media_terms(item.summary))
        elif item.title:
            snippets.append(strip_media_terms(item.title))
    return sanitize_final_text(" ".join(snippets), max_chars=max_chars)


def _score_cluster(cluster: NewsCluster, reference: datetime | None = None) -> float:
    score = 0.0
    # Centrality: the same information appearing repeatedly across media has priority.
    score += min(cluster.article_count, 18) * 7
    score += min(cluster.source_count, 10) * 12
    for topic in cluster.topics:
        score += TOPIC_WEIGHTS.get(topic, 0)
    score += min(len(cluster.actors), 5) * 4
    latest = parse_datetime(cluster.last_seen)
    reference = reference or datetime.now(timezone.utc)
    if latest:
        days = max(0, (reference.astimezone(timezone.utc) - latest.astimezone(timezone.utc)).days)
        if days <= 2:
            score += 12
        elif days <= 7:
            score += 8
        elif days <= 15:
            score += 4
    return round(score, 2)


def _cluster_text(cluster: NewsCluster) -> str:
    return " ".join(
        [
            cluster.title,
            cluster.summary,
            " ".join(cluster.representative_titles),
            " ".join(_text_for_item(item) for item in cluster.items[:8]),
        ]
    )


def _theme_bucket_for_cluster(cluster: NewsCluster) -> str:
    text = normalize_text(_cluster_text(cluster))
    hits: list[tuple[int, int, str]] = []
    for bucket, keywords in THEME_BUCKETS.items():
        count = 0
        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword and normalized_keyword in text:
                count += 1
        if count:
            hits.append((count, BUCKET_PRIORITY.get(bucket, 0), bucket))
    if not hits:
        return "misc_" + compact_hash(" ".join(sorted(_tokens(_cluster_text(cluster))))[:220], 8)
    hits.sort(reverse=True)
    return hits[0][2]


def _merge_cluster_group(group: list[NewsCluster], reference: datetime | None = None) -> NewsCluster:
    if len(group) == 1:
        single = group[0]
        single.score = _score_cluster(single, reference=reference)
        return single

    items: list[NewsItem] = []
    for cluster in group:
        items.extend(cluster.items)
    items = _latest_first(items)

    all_text = " ".join(_text_for_item(item) for item in items)
    topics = detect_topics(all_text)
    actors = detect_actors(all_text)
    domains = {_domain(item.url) or normalize_text(item.source) for item in items if item.url or item.source}
    dates = [parse_datetime(item.published_at) for item in items if parse_datetime(item.published_at)]
    first_seen = min(dates).isoformat() if dates else ""
    last_seen = max(dates).isoformat() if dates else ""
    title = _representative_title(items)
    representative_titles = []
    seen_titles: set[str] = set()
    for item in items:
        cleaned_title = strip_media_terms(item.title).strip()
        key = normalize_text(cleaned_title)
        if cleaned_title and key not in seen_titles:
            representative_titles.append(cleaned_title)
            seen_titles.add(key)
        if len(representative_titles) >= 8:
            break

    cluster = NewsCluster(
        cluster_id="theme_" + compact_hash(_theme_bucket_for_cluster(group[0]) + normalize_text(title) + str(len(items)), 12),
        title=title,
        summary=_cluster_summary(items, max_chars=1200),
        items=items,
        topics=topics,
        actors=actors,
        source_count=len(domains),
        article_count=len(items),
        first_seen=first_seen,
        last_seen=last_seen,
        representative_titles=representative_titles,
        urls=[item.url for item in items[:14] if item.url],
    )
    cluster.score = _score_cluster(cluster, reference=reference)
    return cluster


def merge_related_clusters(clusters: list[NewsCluster], reference: datetime | None = None) -> list[NewsCluster]:
    """Merge clusters that are distinct by wording but identical by editorial theme.

    Raw feeds often produce many clusters for the same issue because outlets use
    different headlines. The report must prioritize issues, not headlines. This
    function turns repeated coverage into a single, higher-scored theme.
    """
    buckets: dict[str, list[NewsCluster]] = {}
    for cluster in clusters:
        bucket = _theme_bucket_for_cluster(cluster)
        buckets.setdefault(bucket, []).append(cluster)

    merged = [_merge_cluster_group(group, reference=reference) for group in buckets.values()]
    merged.sort(key=lambda c: (c.score, c.article_count, c.source_count), reverse=True)
    return merged


def cluster_news(items: list[NewsItem], similarity_threshold: float = 0.20, reference: datetime | None = None) -> list[NewsCluster]:
    clusters_items: list[list[NewsItem]] = []
    for item in _latest_first(items):
        if not item.title:
            continue
        best_idx = None
        best_score = 0.0
        for idx, cluster in enumerate(clusters_items):
            # Compare against up to first 4 representatives to keep it cheap.
            score = max((_similarity(item, other) for other in cluster[:4]), default=0.0)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is not None and best_score >= similarity_threshold:
            clusters_items[best_idx].append(item)
        else:
            clusters_items.append([item])

    clusters: list[NewsCluster] = []
    for group in clusters_items:
        group = _latest_first(group)
        all_text = " ".join(_text_for_item(item) for item in group)
        topics = detect_topics(all_text)
        actors = detect_actors(all_text)
        domains = {_domain(item.url) or normalize_text(item.source) for item in group if item.url or item.source}
        dates = [parse_datetime(item.published_at) for item in group if parse_datetime(item.published_at)]
        first_seen = min(dates).isoformat() if dates else ""
        last_seen = max(dates).isoformat() if dates else ""
        title = _representative_title(group)
        cluster = NewsCluster(
            cluster_id="cluster_" + compact_hash(normalize_text(title) + str(len(group)), 12),
            title=title,
            summary=_cluster_summary(group),
            items=group,
            topics=topics,
            actors=actors,
            source_count=len(domains),
            article_count=len(group),
            first_seen=first_seen,
            last_seen=last_seen,
            representative_titles=[strip_media_terms(item.title) for item in group[:6]],
            urls=[item.url for item in group[:10] if item.url],
        )
        cluster.score = _score_cluster(cluster, reference=reference)
        clusters.append(cluster)

    clusters = merge_related_clusters(clusters, reference=reference)
    clusters.sort(key=lambda c: (c.score, c.article_count, c.source_count), reverse=True)
    return clusters


def select_top_clusters(clusters: list[NewsCluster], min_clusters: int = 4, max_clusters: int = 8) -> list[NewsCluster]:
    if not clusters:
        return []
    # Keep high-signal clusters; guarantee at least min_clusters when available.
    selected = [cluster for cluster in clusters if cluster.source_count >= 2 or cluster.article_count >= 2 or cluster.score >= 45]
    if len(selected) < min_clusters:
        selected = clusters[:min_clusters]
    # More-covered themes must appear earlier in the report. Score already
    # includes centrality, but keep article/source count as explicit tie-breakers.
    selected.sort(key=lambda c: (c.score, c.article_count, c.source_count), reverse=True)
    return selected[:max_clusters]

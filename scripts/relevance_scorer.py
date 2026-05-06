from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from news_models import NewsItem
from utils import normalize_text, parse_datetime

# Scoring orientado a actualidad política. Se mantiene el tópico financiero como contexto,
# pero con menor peso para que no domine la selección.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "politica_gobernabilidad": [
        "gobierno",
        "casa rosada",
        "presidente",
        "jefatura de gabinete",
        "gabinete",
        "gobernadores",
        "oposicion",
        "oposición",
        "alianzas",
        "acuerdo político",
        "bloques",
        "coalicion",
        "coalición",
        "oficialismo",
        "peronismo",
        "kirchnerismo",
        "ucr",
        "pro",
        "libertad avanza",
        "lla",
    ],
    "congreso": [
        "congreso",
        "senado",
        "diputados",
        "comision",
        "comisión",
        "sesiones extraordinarias",
        "ley",
        "proyecto de ley",
        "dictamen",
        "quorum",
        "quórum",
        "media sanción",
        "sanción",
        "bloque",
        "interbloque",
    ],
    "provincias": [
        "gobernador",
        "gobernadores",
        "provincias",
        "mandatarios provinciales",
        "coparticipación",
        "coparticipacion",
        "pacto fiscal",
        "liga de gobernadores",
    ],
    "elecciones": [
        "elecciones",
        "campaña",
        "candidato",
        "candidata",
        "encuesta",
        "voto",
        "electoral",
        "comicios",
    ],
    "laboral_social": [
        "sindicatos",
        "gremios",
        "paritarias",
        "huelga",
        "conflicto social",
        "movilización",
        "movilizacion",
        "protesta",
        "cgt",
        "cta",
    ],
    "economia_macro": [
        "economia",
        "economía",
        "inflacion",
        "inflación",
        "dolar",
        "dólar",
        "fmi",
        "reservas",
        "presupuesto",
        "deuda",
        "superavit",
        "superávit",
        "riesgo país",
    ],
    "fiscal_tributario": [
        "impuestos",
        "arca",
        "afip",
        "ganancias",
        "iva",
        "tributario",
        "retenciones",
        "blanqueo",
        "moratoria",
    ],
    "regulatorio_financiero": [
        "bcra",
        "banco central",
        "cnv",
        "uif",
        "bancos",
        "sistema financiero",
        "fintech",
        "credito",
        "crédito",
        "tasas",
        "mercado de capitales",
        "normativa",
        "regulacion",
        "regulación",
    ],
}

ACTOR_KEYWORDS: dict[str, list[str]] = {
    "Poder Ejecutivo": ["gobierno", "casa rosada", "presidente", "gabinete", "ministerio", "jefatura de gabinete"],
    "Congreso": ["congreso", "senado", "diputados", "comisión", "comision", "bloques", "dictamen", "quórum", "quorum"],
    "Provincias": ["gobernadores", "gobernador", "provincias", "mandatarios provinciales"],
    "Oposición": ["oposición", "oposicion", "bloques opositores", "peronismo", "ucr", "pro", "kirchnerismo"],
    "Oficialismo": ["oficialismo", "la libertad avanza", "lla", "bloque libertario"],
    "Sindicatos": ["sindicatos", "gremios", "paritarias", "huelga", "cgt", "cta"],
    "Reguladores": ["bcra", "banco central", "cnv", "uif", "arca"],
}

SOURCE_BONUS_DOMAINS = [
    "argentina.gob.ar",
    "boletinoficial.gob.ar",
    "diputados.gob.ar",
    "senado.gob.ar",
    "casarosada.gob.ar",
]

TOPIC_WEIGHTS = {
    "politica_gobernabilidad": 36,
    "congreso": 34,
    "provincias": 28,
    "elecciones": 24,
    "laboral_social": 20,
    "economia_macro": 14,
    "fiscal_tributario": 12,
    "regulatorio_financiero": 8,
}


def _combined_text(item: NewsItem) -> str:
    return normalize_text(" ".join([item.title, item.summary, item.source, item.url]))


def detect_topics(item: NewsItem) -> list[str]:
    text = _combined_text(item)
    topics: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(normalize_text(keyword) in text for keyword in keywords):
            topics.append(topic)
    return topics


def detect_actors(item: NewsItem) -> list[str]:
    text = _combined_text(item)
    actors: list[str] = []
    for actor, keywords in ACTOR_KEYWORDS.items():
        if any(normalize_text(keyword) in text for keyword in keywords):
            actors.append(actor)
    return actors


def _recency_bonus(item: NewsItem, reference: datetime | None = None) -> int:
    dt = parse_datetime(item.published_at)
    if not dt:
        return 0
    reference = reference or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    days = max(0, (reference - dt.astimezone(timezone.utc)).days)
    if days <= 3:
        return 8
    if days <= 7:
        return 5
    if days <= 15:
        return 2
    return 0


def _source_bonus(item: NewsItem) -> int:
    text = normalize_text(" ".join([item.source, item.url]))
    if any(domain in text for domain in SOURCE_BONUS_DOMAINS):
        return 10
    if item.collector in {"rss_feed", "gdelt", "google_news"}:
        return 2
    return 0


def bbva_relevance(item: NewsItem, topics: list[str]) -> str:
    # Nombre de campo heredado. El contenido se usa como lectura política, no comercial.
    if "politica_gobernabilidad" in topics or "congreso" in topics:
        return "Alta: tema central para lectura de gobernabilidad, acuerdos y agenda legislativa."
    if "provincias" in topics or "elecciones" in topics:
        return "Media: tema relevante para seguimiento territorial y dinámica de actores políticos."
    if "laboral_social" in topics:
        return "Media: tema relevante para monitoreo de conflictividad y reacción social."
    if "economia_macro" in topics or "fiscal_tributario" in topics:
        return "Media: tema económico con impacto político sobre prioridades de gobierno y Congreso."
    return "Baja: relevancia contextual, sin centralidad política identificada."


def score_news_item(item: NewsItem, reference: datetime | None = None) -> NewsItem:
    topics = detect_topics(item)
    actors = detect_actors(item)
    score = 0
    for topic in topics:
        score += TOPIC_WEIGHTS.get(topic, 0)
    score += min(len(actors) * 4, 16)
    score += _recency_bonus(item, reference=reference)
    score += _source_bonus(item)
    score = min(score, 100)

    item.topics = topics
    item.actors = actors
    item.relevance_score = score
    if score >= 70:
        item.impact_level = "alto"
    elif score >= 40:
        item.impact_level = "medio"
    else:
        item.impact_level = "bajo"
    item.bbva_relevance = bbva_relevance(item, topics)
    return item


def score_news(items: Iterable[NewsItem], reference: datetime | None = None) -> list[NewsItem]:
    scored = [score_news_item(item, reference=reference) for item in items]
    return sorted(scored, key=lambda item: (item.relevance_score, item.published_at), reverse=True)


def select_relevant_news(
    items: Iterable[NewsItem],
    max_items: int = 4,
    min_score: int = 20,
) -> list[NewsItem]:
    selected: list[NewsItem] = []
    seen_clusters: set[str] = set()
    for item in items:
        if item.relevance_score < min_score:
            continue
        if item.cluster_id in seen_clusters:
            continue
        selected.append(item)
        seen_clusters.add(item.cluster_id)
        if len(selected) >= max_items:
            break
    return selected

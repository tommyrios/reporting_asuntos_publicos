from __future__ import annotations

import json
import logging
import os
from typing import Any

from llm_client import call_gemini_for_json, load_prompt
from news_models import NewsItem, news_to_dicts
from utils import parse_bool, truncate

logger = logging.getLogger(__name__)

REQUIRED_ANALYSIS_KEYS = [
    "headline",
    "executive_vision",
    "key_developments",
    "bbva_implications",
    "watchlist",
    "risk_level",
    "editorial_notes",
]


def _analysis_payload(selected_news: list[NewsItem], period: dict[str, str]) -> dict[str, Any]:
    compact_news = []
    for item in selected_news:
        compact_news.append(
            {
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at,
                "summary": item.summary,
                "topics": item.topics,
                "actors": item.actors,
                "impact_level": item.impact_level,
                "bbva_relevance": item.bbva_relevance,
                "url": item.url,
            }
        )
    return {"period": period, "selected_news": compact_news}


def _fallback_analysis(selected_news: list[NewsItem], period: dict[str, str]) -> dict[str, Any]:
    top_titles = [truncate(item.title, 120) for item in selected_news[:5]]
    topic_counts: dict[str, int] = {}
    for item in selected_news:
        for topic in item.topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    top_topics = [topic for topic, _ in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    topic_label = ", ".join(top_topics).replace("_", " ") if top_topics else "agenda política y económica"

    if selected_news:
        executive_vision = (
            f"Durante el período {period.get('label', '')}, la agenda relevada se concentró en {topic_label}. "
            "El set seleccionado muestra una combinación de discusión política, actividad parlamentaria y temas regulatorios o macroeconómicos con impacto potencial sobre el entorno de negocios. "
            "La lectura ejecutiva debe validarse editorialmente con el equipo antes de su circulación, especialmente en aquellos puntos donde la cobertura proviene de medios y no de fuentes institucionales."
        )
    else:
        executive_vision = (
            f"Durante el período {period.get('label', '')}, el pipeline no identificó noticias suficientes para construir una lectura ejecutiva robusta. "
            "Se recomienda revisar la configuración de fuentes y complementar con curaduría manual."
        )

    key_developments = top_titles[:3] or ["No se identificaron hitos suficientes con la configuración actual."]
    bbva_implications = [
        "Monitorear potenciales impactos regulatorios, fiscales o macroeconómicos sobre el sistema financiero.",
        "Validar si alguno de los temas relevados requiere posicionamiento institucional o seguimiento con stakeholders.",
    ]
    watchlist = [
        "Tratamiento legislativo de iniciativas económicas o regulatorias.",
        "Comunicaciones de organismos regulatorios y autoridades económicas.",
        "Reacción de actores políticos, empresariales y sindicales relevantes.",
    ]
    return {
        "headline": "Contexto político y regulatorio de la quincena",
        "executive_vision": executive_vision,
        "key_developments": key_developments,
        "bbva_implications": bbva_implications,
        "watchlist": watchlist,
        "risk_level": "medio" if selected_news else "bajo",
        "editorial_notes": "Análisis generado en modo fallback determinístico; requiere revisión editorial.",
    }


def _validate_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    for key in REQUIRED_ANALYSIS_KEYS:
        payload.setdefault(key, "" if key not in {"key_developments", "bbva_implications", "watchlist"} else [])
    for key in ["key_developments", "bbva_implications", "watchlist"]:
        if not isinstance(payload.get(key), list):
            payload[key] = [str(payload[key])]
        payload[key] = [truncate(str(item), 180) for item in payload[key] if str(item).strip()]
    payload["headline"] = truncate(str(payload.get("headline") or "Contexto político quincenal"), 90)
    payload["executive_vision"] = truncate(str(payload.get("executive_vision") or ""), 900)
    payload["editorial_notes"] = truncate(str(payload.get("editorial_notes") or ""), 240)
    risk = str(payload.get("risk_level") or "medio").lower().strip()
    payload["risk_level"] = risk if risk in {"alto", "medio", "bajo"} else "medio"
    return payload


def generate_political_analysis(
    selected_news: list[NewsItem],
    period: dict[str, str],
    disable_gemini: bool | None = None,
    strict_llm: bool | None = None,
) -> dict[str, Any]:
    disable_gemini = parse_bool(os.environ.get("AAPP_DISABLE_GEMINI"), False) if disable_gemini is None else disable_gemini
    strict_llm = parse_bool(os.environ.get("AAPP_STRICT_LLM"), False) if strict_llm is None else strict_llm

    if disable_gemini:
        return _validate_analysis(_fallback_analysis(selected_news, period))

    try:
        base_prompt = load_prompt("political_analysis.txt")
        style_prompt = load_prompt("style_gonza.txt")
        payload = _analysis_payload(selected_news, period)
        contents = [
            base_prompt,
            "\nGuía de estilo:\n" + style_prompt,
            "\nPayload JSON:\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
        analysis = call_gemini_for_json(contents)
        return _validate_analysis(analysis)
    except Exception as exc:
        logger.warning("event=gemini_analysis_failed fallback=true reason=%s", exc)
        if strict_llm:
            raise
        fallback = _fallback_analysis(selected_news, period)
        fallback["editorial_notes"] = f"Gemini no disponible; se usó fallback determinístico. Motivo: {truncate(str(exc), 120)}"
        return _validate_analysis(fallback)


def analysis_sources(selected_news: list[NewsItem]) -> list[dict[str, Any]]:
    return news_to_dicts(selected_news)

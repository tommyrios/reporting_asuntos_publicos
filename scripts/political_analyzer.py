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

SLIDE_LIMITS = {
    "headline": 78,
    "executive_vision": 560,
    "key_developments": 118,
    "bbva_implications": 112,
    "watchlist": 105,
    "editorial_notes": 180,
}

EXPECTED_COUNTS = {
    "key_developments": 3,
    "bbva_implications": 2,
    "watchlist": 3,
}

TOPIC_LABELS = {
    "regulatorio_financiero": "agenda regulatoria financiera",
    "politica_gobernabilidad": "gobernabilidad pol\u00edtica",
    "congreso": "actividad parlamentaria",
    "economia_macro": "contexto macroecon\u00f3mico",
    "fiscal_tributario": "agenda fiscal y tributaria",
    "laboral_social": "agenda laboral y social",
}


def _analysis_payload(selected_news: list[NewsItem], period: dict[str, str]) -> dict[str, Any]:
    compact_news = []
    for item in selected_news:
        compact_news.append(
            {
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at,
                "summary": truncate(item.summary, 360),
                "topics": item.topics,
                "actors": item.actors,
                "impact_level": item.impact_level,
                "bbva_relevance": item.bbva_relevance,
                "url": item.url,
            }
        )
    return {"period": period, "selected_news": compact_news}


def _fallback_analysis(selected_news: list[NewsItem], period: dict[str, str]) -> dict[str, Any]:
    top_titles = [truncate(item.title, 105) for item in selected_news[:5]]
    topic_counts: dict[str, int] = {}
    for item in selected_news:
        for topic in item.topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    top_topics = [topic for topic, _ in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    topic_label = ", ".join(TOPIC_LABELS.get(topic, topic.replace("_", " ")) for topic in top_topics) if top_topics else "agenda pol\u00edtica y econ\u00f3mica"

    if selected_news:
        executive_vision = (
            f"Durante el per\u00edodo {period.get('label', '')}, la agenda relevada se concentr\u00f3 en {topic_label}. "
            "El set seleccionado combina discusi\u00f3n pol\u00edtica, actividad parlamentaria y temas regulatorios o macroecon\u00f3micos con impacto potencial sobre el entorno de negocios. "
            "La lectura debe validarse editorialmente antes de su circulaci\u00f3n, especialmente cuando la cobertura proviene de medios y no de fuentes institucionales."
        )
    else:
        executive_vision = (
            f"Durante el per\u00edodo {period.get('label', '')}, el pipeline no identific\u00f3 noticias suficientes para construir una lectura ejecutiva robusta. "
            "Se recomienda revisar la configuraci\u00f3n de fuentes y complementar con curadur\u00eda manual."
        )

    key_developments = top_titles[:3] or ["No se identificaron hitos suficientes con la configuraci\u00f3n actual."]
    bbva_implications = [
        "Monitorear impactos regulatorios, fiscales o macroecon\u00f3micos sobre el sistema financiero.",
        "Validar si alg\u00fan tema requiere posicionamiento institucional o seguimiento con stakeholders.",
    ]
    watchlist = [
        "Tratamiento legislativo de iniciativas econ\u00f3micas o regulatorias.",
        "Comunicaciones de organismos regulatorios y autoridades econ\u00f3micas.",
        "Reacci\u00f3n de actores pol\u00edticos, empresariales y sindicales relevantes.",
    ]
    return {
        "headline": "Contexto pol\u00edtico y regulatorio de la quincena",
        "executive_vision": executive_vision,
        "key_developments": key_developments,
        "bbva_implications": bbva_implications,
        "watchlist": watchlist,
        "risk_level": "medio" if selected_news else "bajo",
        "editorial_notes": "An\u00e1lisis generado en modo fallback determin\u00edstico; requiere revisi\u00f3n editorial.",
    }


def _clean_list(value: Any, key: str, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        value = [str(value)] if value else []
    cleaned = [truncate(str(item).strip(), SLIDE_LIMITS[key]) for item in value if str(item).strip()]
    expected = EXPECTED_COUNTS[key]
    if len(cleaned) < expected:
        cleaned.extend(fallback[len(cleaned):expected])
    return cleaned[:expected]


def _validate_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    for key in REQUIRED_ANALYSIS_KEYS:
        payload.setdefault(key, "" if key not in EXPECTED_COUNTS else [])

    payload["key_developments"] = _clean_list(
        payload.get("key_developments"),
        "key_developments",
        ["No se identificaron hitos adicionales con suficiente relevancia."] * 3,
    )
    payload["bbva_implications"] = _clean_list(
        payload.get("bbva_implications"),
        "bbva_implications",
        ["Sin implicancia directa adicional para destacar en esta quincena."] * 2,
    )
    payload["watchlist"] = _clean_list(
        payload.get("watchlist"),
        "watchlist",
        ["Seguimiento de agenda pol\u00edtica, regulatoria y macroecon\u00f3mica."] * 3,
    )

    payload["headline"] = truncate(str(payload.get("headline") or "Contexto pol\u00edtico quincenal"), SLIDE_LIMITS["headline"])
    payload["executive_vision"] = truncate(str(payload.get("executive_vision") or ""), SLIDE_LIMITS["executive_vision"])
    payload["editorial_notes"] = truncate(str(payload.get("editorial_notes") or ""), SLIDE_LIMITS["editorial_notes"])
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
            "\nGu\u00eda de estilo:\n" + style_prompt,
            "\nPayload JSON:\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
        analysis = call_gemini_for_json(contents)
        return _validate_analysis(analysis)
    except Exception as exc:
        logger.warning("event=gemini_analysis_failed fallback=true reason=%s", exc)
        if strict_llm:
            raise
        fallback = _fallback_analysis(selected_news, period)
        fallback["editorial_notes"] = f"Gemini no disponible; se us\u00f3 fallback determin\u00edstico. Motivo: {truncate(str(exc), 120)}"
        return _validate_analysis(fallback)


def analysis_sources(selected_news: list[NewsItem]) -> list[dict[str, Any]]:
    return news_to_dicts(selected_news)

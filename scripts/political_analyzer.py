from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from llm_client import call_gemini_for_json, load_prompt
from news_models import NewsItem, news_to_dicts
from utils import parse_bool, strip_html

logger = logging.getLogger(__name__)

REQUIRED_ANALYSIS_KEYS = [
    "headline",
    "executive_vision",
    "top_political_news",
    "key_developments",
    "bbva_implications",  # legacy key kept for report_contract compatibility; not rendered in the deck.
    "watchlist",
    "risk_level",  # legacy key kept for compatibility; not rendered in the deck.
    "editorial_notes",
]

SLIDE_LIMITS = {
    "headline": 86,
    "executive_vision": 430,
    "news_title": 82,
    "news_summary": 190,
    "key_developments": 115,
    "bbva_implications": 105,
    "watchlist": 105,
    "editorial_notes": 180,
}

EXPECTED_COUNTS = {
    "top_political_news": 4,
    "key_developments": 4,
    "bbva_implications": 2,
    "watchlist": 3,
}

TOPIC_LABELS = {
    "politica_gobernabilidad": "gobernabilidad política",
    "congreso": "actividad parlamentaria",
    "elecciones": "dinámica electoral",
    "provincias": "relación Nación-provincias",
    "economia_macro": "agenda económica con impacto político",
    "fiscal_tributario": "agenda fiscal con impacto político",
    "laboral_social": "conflictividad social y laboral",
    "regulatorio_financiero": "agenda regulatoria",
}


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", strip_html(str(value or ""))).strip()


def _safe_clip(value: Any, max_chars: int) -> str:
    text = _normalize_text(value)
    if len(text) <= max_chars:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    size = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = size + len(sentence) + (1 if kept else 0)
        if candidate <= max_chars:
            kept.append(sentence)
            size = candidate
        else:
            break
    if kept:
        return " ".join(kept)

    clipped = text[:max_chars].rsplit(" ", 1)[0].strip()
    if clipped and clipped[-1] not in ".!?:;":
        clipped += "."
    return clipped


def _analysis_payload(selected_news: list[NewsItem], period: dict[str, str]) -> dict[str, Any]:
    compact_news = []
    for item in selected_news[:8]:
        compact_news.append(
            {
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at,
                "summary": _safe_clip(item.summary, 320),
                "topics": item.topics,
                "actors": item.actors,
                "impact_level": item.impact_level,
                "political_relevance_score": item.relevance_score,
                "url": item.url,
            }
        )
    return {"period": period, "selected_news": compact_news}


def _topic_label(selected_news: list[NewsItem]) -> str:
    topic_counts: dict[str, int] = {}
    for item in selected_news:
        for topic in item.topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    top_topics = [topic for topic, _ in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    return ", ".join(TOPIC_LABELS.get(topic, topic.replace("_", " ")) for topic in top_topics) if top_topics else "agenda política nacional"


def _fallback_top_news(selected_news: list[NewsItem]) -> list[dict[str, str]]:
    top_news: list[dict[str, str]] = []
    for item in selected_news[:4]:
        top_news.append(
            {
                "title": _safe_clip(item.title, SLIDE_LIMITS["news_title"]),
                "source": _safe_clip(item.source, 40),
                "date": item.published_at,
                "why_it_matters": _safe_clip(
                    item.summary or "Tema relevante para seguir la evolución del contexto político nacional.",
                    SLIDE_LIMITS["news_summary"],
                ),
            }
        )
    while len(top_news) < 4:
        top_news.append(
            {
                "title": "Noticia pendiente de validación editorial",
                "source": "",
                "date": "",
                "why_it_matters": "La cobertura automática no identificó información suficiente para completar este punto con robustez.",
            }
        )
    return top_news


def _fallback_analysis(selected_news: list[NewsItem], period: dict[str, str]) -> dict[str, Any]:
    topic_label = _topic_label(selected_news)
    if selected_news:
        executive_vision = (
            f"Durante el período {period.get('label', '')}, la agenda política se concentró en {topic_label}. "
            "El relevamiento muestra una dinámica marcada por la relación entre el Poder Ejecutivo, el Congreso y los actores territoriales, "
            "con foco en gobernabilidad, construcción de acuerdos y evolución de la agenda legislativa. "
            "La lectura debe ser validada editorialmente antes de su circulación."
        )
    else:
        executive_vision = (
            f"Durante el período {period.get('label', '')}, el pipeline no identificó noticias suficientes para construir una lectura política robusta. "
            "Se recomienda revisar fuentes, criterios de búsqueda y complementar con curaduría manual."
        )

    top_news = _fallback_top_news(selected_news)
    key_developments = [item["title"] for item in top_news]
    return {
        "headline": "Cuatro claves políticas de la quincena",
        "executive_vision": _safe_clip(executive_vision, SLIDE_LIMITS["executive_vision"]),
        "top_political_news": top_news,
        "key_developments": key_developments,
        "bbva_implications": [
            "Lectura de gobernabilidad: seguir capacidad de articulación política del Ejecutivo.",
            "Lectura legislativa: monitorear bloques, quórum y acuerdos parlamentarios.",
        ],
        "watchlist": [
            "Movimientos del Poder Ejecutivo y prioridades de agenda pública.",
            "Tratamiento legislativo de proyectos relevantes y posicionamiento de bloques.",
            "Reacción de gobernadores, oposición, sindicatos y actores sociales.",
        ],
        "risk_level": "medio",
        "editorial_notes": "Análisis generado en modo fallback determinístico; requiere revisión editorial.",
    }


def _clean_list(value: Any, key: str, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        value = [str(value)] if value else []
    cleaned = [_safe_clip(item, SLIDE_LIMITS[key]) for item in value if str(item).strip()]
    expected = EXPECTED_COUNTS[key]
    if len(cleaned) < expected:
        cleaned.extend(fallback[len(cleaned):expected])
    return cleaned[:expected]


def _clean_top_news(value: Any, selected_news: list[NewsItem]) -> list[dict[str, str]]:
    fallback = _fallback_top_news(selected_news)
    if not isinstance(value, list):
        return fallback

    cleaned: list[dict[str, str]] = []
    for raw in value[:4]:
        if isinstance(raw, dict):
            cleaned.append(
                {
                    "title": _safe_clip(raw.get("title", ""), SLIDE_LIMITS["news_title"]),
                    "source": _safe_clip(raw.get("source", ""), 40),
                    "date": _normalize_text(raw.get("date") or raw.get("published_at") or ""),
                    "why_it_matters": _safe_clip(
                        raw.get("why_it_matters") or raw.get("summary") or raw.get("reading") or "",
                        SLIDE_LIMITS["news_summary"],
                    ),
                }
            )
        elif raw:
            cleaned.append(
                {
                    "title": _safe_clip(raw, SLIDE_LIMITS["news_title"]),
                    "source": "",
                    "date": "",
                    "why_it_matters": "Tema seleccionado por relevancia política durante la quincena.",
                }
            )
    if len(cleaned) < 4:
        cleaned.extend(fallback[len(cleaned):4])
    return cleaned[:4]


def _validate_analysis(payload: dict[str, Any], selected_news: list[NewsItem] | None = None) -> dict[str, Any]:
    selected_news = selected_news or []
    for key in REQUIRED_ANALYSIS_KEYS:
        payload.setdefault(key, [] if key in EXPECTED_COUNTS else "")

    payload["top_political_news"] = _clean_top_news(payload.get("top_political_news"), selected_news)
    payload["key_developments"] = _clean_list(
        payload.get("key_developments") or [item["title"] for item in payload["top_political_news"]],
        "key_developments",
        ["No se identificaron hitos adicionales con suficiente relevancia."] * 4,
    )
    payload["bbva_implications"] = _clean_list(
        payload.get("bbva_implications"),
        "bbva_implications",
        ["Sin lectura adicional para destacar en esta quincena."] * 2,
    )
    payload["watchlist"] = _clean_list(
        payload.get("watchlist"),
        "watchlist",
        ["Seguimiento de agenda política, parlamentaria y territorial."] * 3,
    )

    payload["headline"] = _safe_clip(payload.get("headline") or "Cuatro claves políticas de la quincena", SLIDE_LIMITS["headline"])
    payload["executive_vision"] = _safe_clip(payload.get("executive_vision") or "", SLIDE_LIMITS["executive_vision"])
    payload["editorial_notes"] = _safe_clip(payload.get("editorial_notes") or "", SLIDE_LIMITS["editorial_notes"])
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
        return _validate_analysis(_fallback_analysis(selected_news, period), selected_news)

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
        return _validate_analysis(analysis, selected_news)
    except Exception as exc:
        logger.warning("event=gemini_analysis_failed fallback=true reason=%s", exc)
        if strict_llm:
            raise
        fallback = _fallback_analysis(selected_news, period)
        fallback["editorial_notes"] = f"Gemini no disponible; se usó fallback determinístico. Motivo: {_safe_clip(str(exc), 120)}"
        return _validate_analysis(fallback, selected_news)


def analysis_sources(selected_news: list[NewsItem]) -> list[dict[str, Any]]:
    return news_to_dicts(selected_news)

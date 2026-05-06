from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from llm_client import call_gemini_for_json, load_prompt
from news_models import NewsCluster
from utils import parse_bool, truncate

logger = logging.getLogger(__name__)


def _cluster_payload(clusters: list[NewsCluster]) -> list[dict[str, Any]]:
    payload = []
    for cluster in clusters:
        payload.append(
            {
                "cluster_id": cluster.cluster_id,
                "representative_title": cluster.title,
                "cluster_summary": truncate(cluster.summary, 1100),
                "article_count": cluster.article_count,
                "source_count": cluster.source_count,
                "topics": cluster.topics,
                "actors": cluster.actors,
                "score": cluster.score,
                "period_coverage": {"first_seen": cluster.first_seen, "last_seen": cluster.last_seen},
                "representative_titles": cluster.representative_titles[:6],
                "evidence_urls": cluster.urls[:8],
            }
        )
    return payload


def _default_issue_number(period: dict[str, str]) -> str:
    env_value = os.getenv("REPORT_ISSUE_NUMBER", "").strip()
    if env_value:
        return env_value
    # Stable, non-historical fallback: week number of report end date.
    try:
        end_dt = datetime.fromisoformat(period["end"])
        return str(end_dt.isocalendar().week)
    except Exception:
        return ""


def _fallback_report(clusters: list[NewsCluster], period: dict[str, str]) -> dict[str, Any]:
    selected = clusters[: max(4, min(len(clusters), 8))]
    developments = []
    for cluster in selected:
        headline = truncate(cluster.title, 140)
        body = truncate(
            cluster.summary
            or "El tema concentró cobertura durante el período y requiere lectura editorial para precisar su alcance político.",
            560,
        )
        developments.append(
            {
                "headline": headline,
                "analysis": body,
                "cluster_id": cluster.cluster_id,
            }
        )
    if not developments:
        developments.append(
            {
                "headline": "No se identificaron hechos políticos suficientes con las fuentes configuradas",
                "analysis": "El pipeline no encontró clusters con densidad informativa suficiente para construir un informe robusto. Se recomienda ampliar fuentes o complementar con curaduría manual.",
                "cluster_id": "fallback_empty",
            }
        )

    lead = (
        f"La actividad política del período {period.get('label', '')} mostró una agenda dominada por los principales hechos relevados en medios y fuentes institucionales. "
        "El informe se organiza a partir de piezas de información agrupadas por recurrencia, no por medio, y prioriza los hechos con mayor centralidad en la conversación pública. "
        "La lectura requiere revisión editorial final para ajustar matices, jerarquías y proyección política."
    )
    return {
        "title": f"{os.getenv('REPORT_TITLE_PREFIX', 'Apuntes políticos')} #{_default_issue_number(period)}".strip(),
        "date_label": period.get("date_label", ""),
        "lead": lead,
        "developments": developments,
        "prospective_keys": [
            "Evolución del vínculo entre Poder Ejecutivo, Congreso y bloques opositores.",
            "Capacidad del oficialismo para sostener la iniciativa política en un escenario de mayor disputa.",
            "Nivel de organización de la conflictividad social y sindical.",
            "Trayectoria del clima de opinión pública y su impacto sobre la gobernabilidad.",
        ],
        "editorial_notes": "Generado con fallback determinístico por indisponibilidad o desactivación de Gemini.",
    }


def _validate_report(payload: dict[str, Any], clusters: list[NewsCluster], period: dict[str, str]) -> dict[str, Any]:
    fallback = _fallback_report(clusters, period)
    title = str(payload.get("title") or fallback["title"]).strip()
    date_label = str(payload.get("date_label") or period.get("date_label") or fallback["date_label"]).strip()
    lead = truncate(str(payload.get("lead") or fallback["lead"]).strip(), 1350)

    developments = payload.get("developments")
    if not isinstance(developments, list):
        developments = fallback["developments"]
    cleaned_developments = []
    for idx, item in enumerate(developments[:8]):
        if not isinstance(item, dict):
            continue
        headline = truncate(str(item.get("headline") or "").strip(), 170)
        analysis = truncate(str(item.get("analysis") or "").strip(), 850)
        if headline and analysis:
            cleaned_developments.append(
                {
                    "headline": headline,
                    "analysis": analysis,
                    "cluster_id": str(item.get("cluster_id") or (clusters[idx].cluster_id if idx < len(clusters) else "")),
                }
            )
    if len(cleaned_developments) < 4 and len(fallback["developments"]) >= len(cleaned_developments):
        for item in fallback["developments"][len(cleaned_developments):4]:
            cleaned_developments.append(item)

    keys = payload.get("prospective_keys")
    if not isinstance(keys, list):
        keys = fallback["prospective_keys"]
    keys = [truncate(str(key).strip(), 220) for key in keys if str(key).strip()][:6]
    if len(keys) < 4:
        keys.extend(fallback["prospective_keys"][len(keys):4])

    return {
        "title": title,
        "date_label": date_label,
        "lead": lead,
        "developments": cleaned_developments[:8],
        "prospective_keys": keys[:6],
        "editorial_notes": truncate(str(payload.get("editorial_notes") or "").strip(), 300),
    }


def generate_political_report(clusters: list[NewsCluster], period: dict[str, str], disable_gemini: bool | None = None, strict_llm: bool | None = None) -> dict[str, Any]:
    disable_gemini = parse_bool(os.getenv("AAPP_DISABLE_GEMINI"), False) if disable_gemini is None else disable_gemini
    strict_llm = parse_bool(os.getenv("AAPP_STRICT_LLM"), False) if strict_llm is None else strict_llm
    if disable_gemini:
        return _validate_report(_fallback_report(clusters, period), clusters, period)

    try:
        prompt = load_prompt("political_report.txt")
        style = load_prompt("style_apuntes_politicos.txt")
        payload = {"period": period, "clusters": _cluster_payload(clusters)}
        response = call_gemini_for_json(
            [
                prompt,
                "\nGuía de tono y formato:\n" + style,
                "\nClusters de información política:\n" + json.dumps(payload, ensure_ascii=False, indent=2),
            ]
        )
        return _validate_report(response, clusters, period)
    except Exception as exc:
        logger.warning("event=political_report_gemini_failed fallback=true reason=%s", exc)
        if strict_llm:
            raise
        fallback = _fallback_report(clusters, period)
        fallback["editorial_notes"] = f"Gemini no disponible; se usó fallback determinístico. Motivo: {truncate(str(exc), 160)}"
        return _validate_report(fallback, clusters, period)

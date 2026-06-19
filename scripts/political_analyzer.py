from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from editorial_guard import (
    media_terms_from_clusters,
    sanitize_final_text,
    strip_media_terms,
    validate_no_media_references,
)
from llm_client import call_gemini_for_json, load_prompt
from news_models import NewsCluster
from report_numbering import resolve_issue_number
from utils import normalize_text, parse_bool, truncate

logger = logging.getLogger(__name__)


def _cluster_payload(clusters: list[NewsCluster]) -> list[dict[str, Any]]:
    """Payload sent to the LLM.

    Deliberately excludes source names and URLs. The model only receives the
    political fact density, not media attribution, so it cannot copy-paste outlet
    names into the final report.
    """
    payload = []
    media_terms = media_terms_from_clusters(clusters)

    for idx, cluster in enumerate(clusters):
        payload.append(
            {
                "cluster_id": cluster.cluster_id,
                "editorial_priority": idx + 1,
                "representative_title": sanitize_final_text(cluster.title, media_terms, max_chars=220),
                "cluster_summary": sanitize_final_text(cluster.summary, media_terms, max_chars=1000),
                "article_count": cluster.article_count,
                "source_count": cluster.source_count,
                "topics": cluster.topics,
                "actors": cluster.actors,
                "score": cluster.score,
                "period_coverage": {
                    "first_seen": cluster.first_seen,
                    "last_seen": cluster.last_seen,
                },
                "fact_sheet": _fact_sheet_for_cluster(cluster, media_terms),
                "representative_titles": [
                    sanitize_final_text(title, media_terms, max_chars=220)
                    for title in cluster.representative_titles[:6]
                    if sanitize_final_text(title, media_terms, max_chars=220)
                ],
            }
        )

    return payload


def _default_issue_number(period: dict[str, str]) -> str:
    return resolve_issue_number(period)

NUMBER_PATTERN = re.compile(
    r"""
    (?:
        (?:\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\b\d+(?:[.,]\d+)?)
        \s*
        (?:%|puntos?|millones?|mil|votos?|bancas?|diputados?|senadores?|proyectos?|leyes?|d[ií]as?|mes(?:es)?|a[nñ]os?|ARS|USD|US\$|\$)
    )
    |
    (?:
        (?:ARS|USD|US\$|\$)\s*
        (?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

PROJECT_OR_MEASURE_KEYWORDS = [
    "Ficha Limpia",
    "PASO",
    "reforma electoral",
    "ley de discapacidad",
    "subsidios",
    "zonas frías",
    "transferencias",
    "inflación",
    "prepagas",
    "jubilaciones",
    "paritarias",
    "paro",
    "movilización",
    "decreto",
    "veto",
    "dictamen",
    "media sanción",
    "sesión",
    "quórum",
    "reforma laboral",
    "reforma previsional",
    "reforma tributaria",
]


def _cluster_candidate_texts(cluster: NewsCluster, media_terms: set[str]) -> list[str]:
    candidates: list[str] = []

    raw_values = [
        cluster.title,
        cluster.summary,
        *cluster.representative_titles[:8],
    ]

    for item in cluster.items[:10]:
        raw_values.append(item.title)
        raw_values.append(item.summary)

    seen: set[str] = set()
    for value in raw_values:
        cleaned = sanitize_final_text(str(value or ""), media_terms, max_chars=420)
        key = normalize_text(cleaned)
        if cleaned and len(key) >= 20 and key not in seen:
            seen.add(key)
            candidates.append(cleaned)

    return candidates


def _extract_numbers_or_metrics(texts: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for text in texts:
        for match in NUMBER_PATTERN.findall(text):
            value = re.sub(r"\s+", " ", match).strip()
            key = normalize_text(value)
            if value and key not in seen:
                seen.add(key)
                found.append(value)
            if len(found) >= 8:
                return found

    return found


def _extract_projects_or_measures(texts: list[str]) -> list[str]:
    joined = normalize_text(" ".join(texts))
    found: list[str] = []

    for keyword in PROJECT_OR_MEASURE_KEYWORDS:
        if normalize_text(keyword) in joined:
            found.append(keyword)

    return found[:8]


def _extract_concrete_facts(texts: list[str], max_facts: int = 5) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()

    useful_terms = [
        "busca",
        "impulsa",
        "rechaza",
        "presiona",
        "tratar",
        "aprobar",
        "eliminar",
        "aument",
        "cay",
        "caída",
        "suba",
        "recorte",
        "transferencias",
        "subsidios",
        "congreso",
        "diputados",
        "senado",
        "gobernadores",
        "oposición",
        "oficialismo",
        "inflación",
        "desaprobación",
        "imagen",
        "paro",
        "movilización",
    ]

    for text in texts:
        chunks = re.split(r"(?<=[.!?])\s+", text)
        for chunk in chunks:
            sentence = chunk.strip()
            normalized = normalize_text(sentence)

            if len(normalized) < 45:
                continue

            if not any(term in normalized for term in useful_terms):
                continue

            if normalized in seen:
                continue

            seen.add(normalized)
            facts.append(sentence)

            if len(facts) >= max_facts:
                return facts

    return facts


def _fact_sheet_for_cluster(cluster: NewsCluster, media_terms: set[str]) -> dict[str, Any]:
    texts = _cluster_candidate_texts(cluster, media_terms)

    projects_or_measures = _extract_projects_or_measures(texts)
    numbers_or_metrics = _extract_numbers_or_metrics(texts)
    concrete_facts = _extract_concrete_facts(texts)

    editorial_hint = (
        f"Este tema reúne {cluster.article_count} menciones y {cluster.source_count} fuentes distintas. "
        "Debe priorizarse si combina recurrencia, actores institucionales e impacto político concreto."
    )

    return {
        "main_actors": cluster.actors[:8],
        "projects_or_measures": projects_or_measures,
        "numbers_or_metrics": numbers_or_metrics,
        "concrete_facts": concrete_facts,
        "editorial_hint": editorial_hint,
    }

def _topic_headline(cluster: NewsCluster) -> str:
    text = normalize_text(" ".join([cluster.title, cluster.summary, " ".join(cluster.topics), " ".join(cluster.actors)]))

    if "paso" in text or "ficha limpia" in text or "reforma electoral" in text:
        return "La reforma electoral abre una nueva pulseada entre el oficialismo y la oposición"
    if "kicillof" in text or "peronismo" in text or "kirchnerismo" in text:
        return "La oposición muestra mayor movimiento, aunque todavía sin síntesis definitiva"
    if "gobernador" in text or "provincias" in text or "subsidios" in text or "transferencias" in text:
        return "El vínculo con los gobernadores condiciona la agenda de reformas"
    if "jefe de gabinete" in text or "adorni" in text or "diputados" in text or "congreso" in text:
        return "El Congreso vuelve a ocupar el centro de la disputa política"
    if "cgt" in text or "paro" in text or "movilizacion" in text or "sindical" in text:
        return "La conflictividad social recupera visibilidad como factor de presión"
    if "encuesta" in text or "imagen" in text or "desaprobacion" in text or "opinion publica" in text:
        return "La opinión pública introduce un límite más exigente para el oficialismo"
    if "inflacion" in text or "recesion" in text or "empleo" in text or "salarios" in text or "consumo" in text:
        return "La economía sigue ordenando el clima político de la quincena"
    if "oposicion" in text:
        return "La oposición muestra mayor movimiento, aunque todavía sin síntesis definitiva"
    if "corrupcion" in text or "denuncia" in text or "investigacion" in text:
        return "Los cuestionamientos a la integridad de la gestión ganan peso político"

    cleaned = sanitize_final_text(cluster.title, media_terms_from_clusters([cluster]), max_chars=145).rstrip(".")
    return cleaned or "La agenda política suma un nuevo foco de tensión institucional"


def _cluster_fact_sentence(cluster: NewsCluster, media_terms: set[str]) -> str:
    candidates: list[str] = []
    if cluster.summary:
        candidates.append(cluster.summary)
    candidates.extend(cluster.representative_titles[:4])
    for item in cluster.items[:4]:
        if item.summary:
            candidates.append(item.summary)
        if item.title:
            candidates.append(item.title)

    cleaned_sentences: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = strip_media_terms(candidate, media_terms)
        for part in re_split_sentences(cleaned):
            sentence = sanitize_final_text(part, media_terms, max_chars=230)
            key = normalize_text(sentence)
            if len(key) < 35 or key in seen:
                continue
            seen.add(key)
            cleaned_sentences.append(sentence)
        if len(cleaned_sentences) >= 3:
            break

    return " ".join(cleaned_sentences[:2]).strip()


def re_split_sentences(text: str) -> list[str]:
    value = (text or "").replace("\n", " ")
    # Split on punctuation, but keep each fragment as a complete-looking sentence later.
    parts = []
    start = 0
    for idx, char in enumerate(value):
        if char in ".!?":
            parts.append(value[start : idx + 1])
            start = idx + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts or [value]


def _merge_development_analyses(existing: str, new: str, media_terms: set[str], max_chars: int = 1100) -> str:
    """Combine duplicated developments without repeating the same sentence.

    This is a final editorial safety net. Even if Gemini returns the same theme
    more than once, the report must publish one integrated block with the full
    analytical treatment.
    """
    sentences: list[str] = []
    seen: set[str] = set()
    for text in [existing, new]:
        for sentence in re_split_sentences(text):
            cleaned = sanitize_final_text(sentence, media_terms, max_chars=360)
            key = normalize_text(cleaned)
            if len(key) < 35 or key in seen:
                continue
            seen.add(key)
            sentences.append(cleaned)
    return sanitize_final_text(" ".join(sentences), media_terms, max_chars=max_chars)


def _merge_duplicate_developments(developments: list[dict[str, str]], media_terms: set[str]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    by_headline: dict[str, int] = {}
    for item in developments:
        headline = str(item.get("headline") or "").strip()
        analysis = str(item.get("analysis") or "").strip()
        if not headline or not analysis:
            continue
        key = normalize_text(headline)
        if key in by_headline:
            idx = by_headline[key]
            merged[idx]["analysis"] = _merge_development_analyses(merged[idx]["analysis"], analysis, media_terms)
            if item.get("cluster_id") and item["cluster_id"] not in merged[idx].get("cluster_id", ""):
                merged[idx]["cluster_id"] = ",".join(filter(None, [merged[idx].get("cluster_id", ""), item.get("cluster_id", "")]))
        else:
            by_headline[key] = len(merged)
            merged.append(item)
    return merged


def _fallback_analysis(cluster: NewsCluster, media_terms: set[str]) -> str:
    headline = _topic_headline(cluster)
    topics = set(cluster.topics)
    actors = cluster.actors or ["los principales actores políticos"]
    fact = _cluster_fact_sentence(cluster, media_terms)

    if "congreso" in topics:
        frame = "El dato central no es solo legislativo: expresa un aumento de la confrontación y vuelve a colocar al Congreso como espacio de ordenamiento, negociación y desgaste para el oficialismo."
    elif "protesta_social" in topics:
        frame = "El movimiento incorpora presión desde la calle y obliga al Gobierno a administrar simultáneamente agenda económica, conflictividad social y control político."
    elif "opinion_publica" in topics:
        frame = "La relevancia política está en la acumulación del malestar: el apoyo social deja de depender de un único indicador y comienza a medirse también por ingresos, expectativas y capacidad de respuesta."
    elif "economia_politica" in topics:
        frame = "El eje económico sigue funcionando como ordenador del clima social y condiciona la lectura de gobernabilidad, aun cuando no derive por sí solo en una crisis política inmediata."
    elif "oposicion" in topics:
        frame = "El movimiento opositor todavía no configura una alternativa cerrada, pero sí muestra mayor disposición a intervenir sobre la agenda y disputar iniciativa."
    elif "gobernabilidad" in topics:
        frame = "El episodio muestra que la gobernabilidad depende cada vez más de acuerdos parciales, administración de tensiones territoriales y capacidad de sostener cohesión interna."
    else:
        actor_text = ", ".join(actors[:3])
        frame = f"El hecho involucra a {actor_text} y suma densidad a una agenda política más disputada, donde la iniciativa oficial convive con límites institucionales y sociales."

    if fact:
        analysis = f"{fact} {frame}"
    else:
        analysis = f"{headline}. {frame}"
    return sanitize_final_text(analysis, media_terms, max_chars=820)


def _fallback_report(clusters: list[NewsCluster], period: dict[str, str]) -> dict[str, Any]:
    selected = clusters[: max(4, min(len(clusters), 8))]
    media_terms = media_terms_from_clusters(selected)
    developments = []
    for cluster in selected:
        headline = sanitize_final_text(_topic_headline(cluster), media_terms, max_chars=170).rstrip(".")
        analysis = _fallback_analysis(cluster, media_terms)
        developments.append(
            {
                "headline": headline,
                "analysis": analysis,
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

    slot = (period.get("slot_label") or "la quincena").strip()
    slot_text = slot[0].lower() + slot[1:] if slot and slot != "la quincena" else slot
    preposition = "de" if slot_text.startswith("la ") else "de la"
    lead = (
        f"La actividad política {preposition} {slot_text} mostró una agenda más disputada, con foco en la relación entre Poder Ejecutivo, Congreso, actores territoriales y clima social. "
        "El oficialismo conserva capacidad de iniciativa, pero enfrenta mayores costos de negociación y una conversación pública menos ordenada. "
        "La lectura del período exige mirar menos la sucesión de episodios y más la acumulación de tensiones: gobernabilidad legislativa, conflictividad social, opinión pública y economía política comienzan a operar de manera simultánea."
    )
    return {
        "title": f"{os.getenv('REPORT_TITLE_PREFIX', 'Insumos para apuntes políticos')} #{_default_issue_number(period)}".strip(),
        "date_label": period.get("date_label", ""),
        "lead": sanitize_final_text(lead, media_terms, max_chars=1350),
        "developments": developments,
        "prospective_keys": [
            "Evolución del vínculo entre Poder Ejecutivo, Congreso y bloques opositores.",
            "Capacidad del oficialismo para sostener la iniciativa política en un escenario de mayor disputa.",
            "Nivel de organización de la conflictividad social y sindical.",
            "Trayectoria del clima de opinión pública y su impacto sobre la gobernabilidad.",
        ],
        "editorial_notes": "Generado con fallback determinístico por indisponibilidad o desactivación de Gemini.",
    }


def _sanitize_report(payload: dict[str, Any], clusters: list[NewsCluster], period: dict[str, str]) -> dict[str, Any]:
    media_terms = media_terms_from_clusters(clusters)
    fallback = _fallback_report(clusters, period)

    title = str(payload.get("title") or fallback["title"]).strip()
    # The numbering is owned by the deterministic calendar, not by the model.
    title_prefix = os.getenv("REPORT_TITLE_PREFIX", "Insumos para apuntes políticos")
    title = f"{title_prefix} #{_default_issue_number(period)}".strip()

    date_label = str(payload.get("date_label") or period.get("date_label") or fallback["date_label"]).strip()
    lead = sanitize_final_text(str(payload.get("lead") or fallback["lead"]).strip(), media_terms, max_chars=1350)

    developments = payload.get("developments")
    if not isinstance(developments, list):
        developments = fallback["developments"]
    cleaned_developments = []
    for idx, item in enumerate(developments[:8]):
        if not isinstance(item, dict):
            continue
        headline = sanitize_final_text(str(item.get("headline") or "").strip(), media_terms, max_chars=170).rstrip(".")
        analysis = sanitize_final_text(str(item.get("analysis") or "").strip(), media_terms, max_chars=850)
        if headline and analysis:
            cleaned_developments.append(
                {
                    "headline": headline,
                    "analysis": analysis,
                    "cluster_id": str(item.get("cluster_id") or (clusters[idx].cluster_id if idx < len(clusters) else "")),
                }
            )
    cleaned_developments = _merge_duplicate_developments(cleaned_developments, media_terms)

    if len(cleaned_developments) < 4 and len(fallback["developments"]) >= len(cleaned_developments):
        for item in fallback["developments"][len(cleaned_developments):4]:
            cleaned_developments.append(item)
        cleaned_developments = _merge_duplicate_developments(cleaned_developments, media_terms)

    keys = payload.get("prospective_keys")
    if not isinstance(keys, list):
        keys = fallback["prospective_keys"]
    keys = [sanitize_final_text(str(key).strip(), media_terms, max_chars=220) for key in keys if str(key).strip()][:6]
    keys = [key for key in keys if key]
    if len(keys) < 4:
        keys.extend(fallback["prospective_keys"][len(keys):4])

    editorial_notes = sanitize_final_text(str(payload.get("editorial_notes") or "").strip(), media_terms, max_chars=300)

    return {
        "title": title,
        "date_label": date_label,
        "lead": lead,
        "developments": cleaned_developments[:8],
        "prospective_keys": keys[:6],
        "editorial_notes": editorial_notes,
    }


def _validate_report(payload: dict[str, Any], clusters: list[NewsCluster], period: dict[str, str]) -> dict[str, Any]:
    report = _sanitize_report(payload, clusters, period)
    violations = validate_no_media_references(report, clusters)
    if violations:
        raise RuntimeError(f"El informe contiene referencias a medios o URLs en campos finales: {', '.join(violations)}")
    for idx, item in enumerate(report.get("developments", [])):
        if not str(item.get("analysis", "")).strip().endswith((".", "?", "!")):
            raise RuntimeError(f"El desarrollo {idx + 1} quedó incompleto o sin puntuación final")
    return report


def generate_political_report(clusters: list[NewsCluster], period: dict[str, str], disable_gemini: bool | None = None, strict_llm: bool | None = None) -> dict[str, Any]:
    disable_gemini = parse_bool(os.getenv("AAPP_DISABLE_GEMINI"), False) if disable_gemini is None else disable_gemini
    strict_llm = parse_bool(os.getenv("AAPP_STRICT_LLM"), False) if strict_llm is None else strict_llm
    if disable_gemini:
        return _validate_report(_fallback_report(clusters, period), clusters, period)

    try:
        prompt = load_prompt("political_report.txt")
        style = load_prompt("style_insumos_para_apuntes_politicos.txt")
        payload = {"period": period, "clusters": _cluster_payload(clusters)}
        response = call_gemini_for_json(
            [
                prompt,
                "\nGuía de tono y formato:\n" + style,
                "\nClusters de información política, sin nombres de medios ni URLs:\n" + json.dumps(payload, ensure_ascii=False, indent=2),
            ]
        )
        try:
            return _validate_report(response, clusters, period)
        except Exception as validation_exc:
            logger.warning("event=political_report_validation_failed fallback=true reason=%s", validation_exc)
            if strict_llm:
                raise
            fallback = _fallback_report(clusters, period)
            fallback["editorial_notes"] = "Gemini produjo una salida que no cumplía el contrato editorial; se usó fallback determinístico."
            return _validate_report(fallback, clusters, period)
    except Exception as exc:
        logger.warning("event=political_report_gemini_failed fallback=true reason=%s", exc)
        if strict_llm:
            raise
        fallback = _fallback_report(clusters, period)
        fallback["editorial_notes"] = f"Gemini no disponible; se usó fallback determinístico. Motivo: {truncate(str(exc), 160)}"
        return _validate_report(fallback, clusters, period)

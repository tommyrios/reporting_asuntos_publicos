from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Iterable

from news_models import NewsCluster
from utils import normalize_text, truncate

# The final report must never use media outlets as source attribution. These
# terms are removed unless an editor later decides to add them manually because
# the outlet itself is part of the political fact.
CURATED_MEDIA_TERMS = {
    "A24",
    "Ambito",
    "Clarín", "Clarin",
    "Diario Río Negro", "Diario Rio Negro",
    "Diario La Vanguardia", "diariolavanguardia",
    "Dos Florines",
    "El Cronista",
    "El Destape",
    "El Litoral",
    "El Observador",
    "El Ojo Digital",
    "EL PAÍS", "El País", "El Pais",
    "El Tribuno",
    "Infobae",
    "Identidad Correntina",
    "La Gaceta",
    "La Nación", "La Nacion",
    "La Política Online", "La Politica Online",
    "La Trocha",
    "La Voz del Interior",
    "LA17",
    "MDZ Online",
    "MinutoUno",
    "Nexofin",
    "NewsDigitales",
    "Noticias Argentinas",
    "Noticias Urbanas",
    "Página/12", "Pagina/12", "Página 12", "Pagina 12",
    "Perfil",
    "Política del Sur", "Politica del Sur",
    "Radio Mitre",
    "Reuters",
    "Télam", "Telam",
    "TN",
    "visionpolitica.com.ar", "Visión Política", "Vision Politica",
}

ATTRIBUTION_PATTERNS = [
    r"\bseg[uú]n\s+(?:el\s+diario\s+|el\s+portal\s+|el\s+sitio\s+)?[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.&/ -]{2,35}",
    r"\bpublic[oó]\s+(?:el\s+diario\s+|el\s+portal\s+)?[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.&/ -]{2,35}",
    r"\binform[oó]\s+(?:el\s+diario\s+|el\s+portal\s+)?[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.&/ -]{2,35}",
    r"\bde\s+acuerdo\s+con\s+(?:el\s+diario\s+|el\s+portal\s+)?[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.&/ -]{2,35}",
]

TRAILING_BAD_WORDS = {
    "a", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante", "en", "entre", "hacia",
    "hasta", "mediante", "para", "por", "segun", "según", "sin", "sobre", "tras", "y", "o", "que",
    "busca", "intenta", "considera", "analiza", "quiere", "puede", "debe", "tras el", "tras la",
}

GENERIC_SOURCE_PHRASES = [
    "relevados en medios y fuentes institucionales",
    "relevado en medios y fuentes institucionales",
    "según medios",
    "en medios",
    "fuentes periodísticas",
    "resumen de medios",
]


def _domain_to_terms(url: str) -> set[str]:
    terms: set[str] = set()
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return terms
    if not host:
        return terms
    stem = host.split(":", 1)[0]
    parts = [part for part in stem.split(".") if part not in {"com", "ar", "net", "org", "news", "www"}]
    if parts:
        terms.add(parts[0])
    return terms


def media_terms_from_clusters(clusters: Iterable[NewsCluster]) -> set[str]:
    terms = set(CURATED_MEDIA_TERMS)
    for cluster in clusters:
        for item in cluster.items:
            if item.source:
                terms.add(item.source.strip())
            if item.url:
                terms.update(_domain_to_terms(item.url))
    return {term for term in terms if term and len(term.strip()) >= 2}


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\wÁÉÍÓÚÑáéíóúñ]){escaped}(?![\wÁÉÍÓÚÑáéíóúñ])", re.IGNORECASE)


def strip_media_terms(text: str, media_terms: Iterable[str] | None = None) -> str:
    value = text or ""
    if not value:
        return ""
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\s+[-–—|]\s+(?=[A-ZÁÉÍÓÚÑ])", ". ", value)
    terms = sorted(set(media_terms or CURATED_MEDIA_TERMS), key=len, reverse=True)
    for term in terms:
        if not term or normalize_text(term) in {"a", "el", "la", "los", "las"}:
            continue
        pattern = _term_pattern(term)
        # When a source name appears between two copied headlines, use it as a
        # boundary instead of simply gluing both fragments together.
        value = pattern.sub(lambda m: ". " if re.match(r"\s*[A-ZÁÉÍÓÚÑ¿¡]", value[m.end():]) else " ", value)
    for pattern in ATTRIBUTION_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    for phrase in GENERIC_SOURCE_PHRASES:
        value = re.sub(re.escape(phrase), "hechos registrados durante el período", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    value = re.sub(r"([,;:])\s*([.;])", r"\2", value)
    value = re.sub(r"\.{2,}", ".", value)
    value = re.sub(r"\s+", " ", value).strip(" -–—|,;:")
    return value.strip()


def complete_sentence(text: str, max_chars: int | None = None) -> str:
    value = re.sub(r"\s+", " ", (text or "")).strip()
    if max_chars:
        value = truncate(value, max_chars)
    value = value.strip(" ,;:-–—")
    if not value:
        return ""

    normalized_tail = normalize_text(value.split(".")[-1])
    words = normalized_tail.split()
    if words and (words[-1] in TRAILING_BAD_WORDS or " ".join(words[-2:]) in TRAILING_BAD_WORDS):
        # Drop the unfinished last sentence/fragment.
        last_stop = max(value.rfind("."), value.rfind(";"), value.rfind("!"), value.rfind("?"))
        value = value[:last_stop + 1].strip() if last_stop > 20 else ""
    if value and not value.endswith((".", "?", "!")):
        value += "."
    return value


def sanitize_final_text(text: str, media_terms: Iterable[str] | None = None, max_chars: int | None = None) -> str:
    value = strip_media_terms(text, media_terms)
    return complete_sentence(value, max_chars=max_chars)


def contains_media_reference(text: str, media_terms: Iterable[str] | None = None) -> bool:
    value = text or ""
    for term in sorted(set(media_terms or CURATED_MEDIA_TERMS), key=len, reverse=True):
        if not term or len(term) < 2:
            continue
        if _term_pattern(term).search(value):
            return True
    if re.search(r"https?://|www\.|\.com\.ar|\.com\b", value, flags=re.IGNORECASE):
        return True
    return False


def validate_no_media_references(report: dict, clusters: Iterable[NewsCluster]) -> list[str]:
    terms = media_terms_from_clusters(clusters)
    violations: list[str] = []
    fields = [
        ("title", report.get("title", "")),
        ("lead", report.get("lead", "")),
        ("editorial_notes", report.get("editorial_notes", "")),
    ]
    for idx, dev in enumerate(report.get("developments", []) or []):
        fields.append((f"developments[{idx}].headline", dev.get("headline", "")))
        fields.append((f"developments[{idx}].analysis", dev.get("analysis", "")))
    for idx, key in enumerate(report.get("prospective_keys", []) or []):
        fields.append((f"prospective_keys[{idx}]", key))

    for field, value in fields:
        if contains_media_reference(str(value), terms):
            violations.append(field)
    return violations

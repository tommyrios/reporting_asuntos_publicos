from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from config import PROMPTS_DIR

logger = logging.getLogger(__name__)


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").strip()


def clean_json_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _candidate_models() -> list[str]:
    primary = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
    fallback_enabled = (os.environ.get("GEMINI_ENABLE_MODEL_FALLBACK") or "true").strip().lower() not in ("0", "false", "no")
    models = [primary]
    if fallback_enabled:
        models.extend([m.strip() for m in (os.environ.get("GEMINI_FALLBACK_MODELS") or "").split(",") if m.strip()])
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _read_env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Valor inválido para {name}: {raw}") from exc


def _read_env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or str(default)).strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Valor inválido para {name}: {raw}") from exc


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in ("429", "500", "502", "503", "504", "timeout", "temporarily", "unavailable", "rate limit", "connection"))


def build_genai_client() -> Any:
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY")
    try:
        from google import genai
    except Exception as exc:
        raise RuntimeError("No está instalado google-genai. Ejecutar pip install -r requirements.txt") from exc
    return genai.Client(api_key=api_key)


def call_gemini_for_json(contents: list[Any]) -> dict[str, Any]:
    client = build_genai_client()
    max_retries = max(1, _read_env_int("GEMINI_MAX_RETRIES_PER_MODEL", 3))
    initial_backoff = max(0.0, _read_env_float("GEMINI_INITIAL_BACKOFF_SECONDS", 3.0))
    max_backoff = max(initial_backoff, _read_env_float("GEMINI_MAX_BACKOFF_SECONDS", 30.0))
    models = _candidate_models()
    last_error: Exception | None = None

    for model_index, model_name in enumerate(models, start=1):
        backoff = initial_backoff
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("event=gemini_attempt model=%s attempt=%s/%s", model_name, attempt, max_retries)
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config={"response_mime_type": "application/json"},
                )
                text = getattr(response, "text", "") or ""
                return json.loads(clean_json_response(text))
            except Exception as exc:
                last_error = exc
                if not _is_retryable_error(exc):
                    raise
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)
        logger.warning("event=gemini_model_exhausted model=%s index=%s/%s", model_name, model_index, len(models))

    raise RuntimeError(f"Gemini agotó modelos configurados. Último error: {last_error}")

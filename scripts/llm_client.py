from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from config import PROMPTS_DIR
from utils import parse_bool

logger = logging.getLogger(__name__)


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt no encontrado: {path}")
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _models() -> list[str]:
    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    fallbacks = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash").split(",") if m.strip()]
    if not parse_bool(os.getenv("GEMINI_ENABLE_MODEL_FALLBACK"), True):
        return [primary]
    ordered = []
    for model in [primary, *fallbacks]:
        if model not in ordered:
            ordered.append(model)
    return ordered


def call_gemini_for_json(contents: list[str]) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY")

    from google import genai

    client = genai.Client(api_key=api_key)
    max_retries = int(os.getenv("GEMINI_MAX_RETRIES_PER_MODEL", "3"))
    initial_backoff = float(os.getenv("GEMINI_INITIAL_BACKOFF_SECONDS", "3"))
    max_backoff = float(os.getenv("GEMINI_MAX_BACKOFF_SECONDS", "30"))
    last_error: Exception | None = None

    for model_idx, model in enumerate(_models(), start=1):
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("event=gemini_attempt model=%s attempt=%s/%s", model, attempt, max_retries)
                response = client.models.generate_content(
                    model=model,
                    contents="\n\n".join(contents),
                    config={
                        "temperature": 0.25,
                        "response_mime_type": "application/json",
                    },
                )
                return _extract_json(response.text or "{}")
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    wait = min(max_backoff, initial_backoff * (2 ** (attempt - 1)))
                    time.sleep(wait)
        logger.warning("event=gemini_model_exhausted model=%s index=%s/%s", model, model_idx, len(_models()))
    raise RuntimeError(f"Gemini agotó modelos configurados. Último error: {last_error}")

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = strip_html(value).lower()
    value = re.sub(r"[^a-záéíóúüñ0-9 ]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def compact_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = []
    blocked_prefixes = ("utm_",)
    blocked_keys = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
    for key, value in parse_qsl(parts.query, keep_blank_values=False):
        key_l = key.lower()
        if key_l in blocked_keys or any(key_l.startswith(prefix) for prefix in blocked_prefixes):
            continue
        query.append((key, value))
    cleaned_path = re.sub(r"/+$", "", parts.path or "")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), cleaned_path, urlencode(query), ""))


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    candidates = [raw]
    if raw.endswith("Z"):
        candidates.append(raw[:-1] + "+00:00")

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def to_iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def within_period(value: str | None, start: datetime, end: datetime) -> bool:
    dt = parse_datetime(value)
    if not dt:
        return True
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return start <= dt <= end


def truncate(value: str, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"

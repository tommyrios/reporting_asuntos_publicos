from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

# OAuth scopes used only for Google Docs + Drive.
# Email delivery is intentionally handled via SMTP in scripts/send_email.py.
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta variable de entorno requerida: {name}")
    return value


@lru_cache(maxsize=1)
def get_credentials() -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=_required("GOOGLE_REFRESH_TOKEN"),
        token_uri=os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
        client_id=_required("GOOGLE_CLIENT_ID"),
        client_secret=_required("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )


def _build_service(name: str, version: str):
    from googleapiclient.discovery import build

    return build(name, version, credentials=get_credentials(), cache_discovery=False)


def docs_service():
    return _build_service("docs", "v1")


def drive_service():
    return _build_service("drive", "v3")

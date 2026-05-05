from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def _split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def _build_credentials():
    try:
        from google.oauth2.credentials import Credentials
    except Exception as exc:
        raise RuntimeError("No están instaladas las dependencias de Google. Ejecutar pip install -r requirements.txt") from exc

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    token_uri = os.environ.get("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token").strip()
    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError("Faltan credenciales Gmail API: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET o GOOGLE_REFRESH_TOKEN")
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )


def _gmail_service():
    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError("No está instalado google-api-python-client") from exc
    return build("gmail", "v1", credentials=_build_credentials(), cache_discovery=False)


def build_message(
    subject: str,
    body: str,
    to: Iterable[str],
    sender: str | None = None,
    cc: Iterable[str] | None = None,
    bcc: Iterable[str] | None = None,
    attachments: Iterable[Path] | None = None,
) -> EmailMessage:
    to_list = list(to)
    if not to_list:
        raise RuntimeError("No hay destinatarios. Configurar EMAIL_DESTINATARIO")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_list)
    if sender:
        msg["From"] = sender
    cc_list = list(cc or [])
    bcc_list = list(bcc or [])
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if bcc_list:
        msg["Bcc"] = ", ".join(bcc_list)
    msg.set_content(body)

    for attachment in attachments or []:
        attachment = Path(attachment)
        ctype, encoding = mimetypes.guess_type(str(attachment))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name)
    return msg


def send_email_with_attachments(
    subject: str,
    body: str,
    attachments: Iterable[Path],
    to: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    sender: str | None = None,
) -> dict:
    sender = sender or os.environ.get("EMAIL_FROM", "").strip() or None
    to = to or _split_recipients(os.environ.get("EMAIL_DESTINATARIO"))
    cc = cc or _split_recipients(os.environ.get("EMAIL_CC"))
    bcc = bcc or _split_recipients(os.environ.get("EMAIL_BCC"))
    msg = build_message(subject, body, to=to, sender=sender, cc=cc, bcc=bcc, attachments=attachments)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service = _gmail_service()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()

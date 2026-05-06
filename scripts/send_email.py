from __future__ import annotations

import base64
import os
import smtplib
from email.message import EmailMessage
from typing import Any

from google_services import gmail_service
from utils import split_emails


def _build_message(subject: str, body: str) -> tuple[EmailMessage, list[str]]:
    email_from = os.getenv("EMAIL_FROM") or os.getenv("EMAIL_USER") or "me"
    email_to = os.getenv("EMAIL_DESTINATARIO", "")
    email_cc = os.getenv("EMAIL_CC", "")
    email_bcc = os.getenv("EMAIL_BCC", "")
    recipients = split_emails(email_to) + split_emails(email_cc) + split_emails(email_bcc)
    if not recipients:
        raise ValueError("Falta EMAIL_DESTINATARIO")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(split_emails(email_to))
    if email_cc:
        msg["Cc"] = ", ".join(split_emails(email_cc))
    msg.set_content(body)
    return msg, recipients


def send_email(subject: str, body: str) -> dict[str, Any]:
    mode = os.getenv("EMAIL_DELIVERY_MODE", "gmail_api").strip().lower()
    if mode in {"none", "false", "disabled"}:
        return {"status": "skipped", "mode": mode}

    msg, recipients = _build_message(subject, body)

    if mode == "smtp":
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASSWORD")
        if not user or not password:
            raise ValueError("Para SMTP faltan EMAIL_USER o EMAIL_PASSWORD")
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg, from_addr=msg["From"], to_addrs=recipients)
        return {"status": "sent", "mode": "smtp", "recipients": recipients}

    if mode == "gmail_api":
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        result = gmail_service().users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"status": "sent", "mode": "gmail_api", "recipients": recipients, "gmail_result": result}

    raise ValueError(f"EMAIL_DELIVERY_MODE no soportado: {mode}")

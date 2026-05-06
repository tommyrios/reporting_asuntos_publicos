from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

from utils import split_emails


def _build_message(subject: str, body: str) -> tuple[EmailMessage, list[str]]:
    email_user = os.getenv("EMAIL_USER")
    email_from = os.getenv("EMAIL_FROM") or email_user
    email_to = os.getenv("EMAIL_DESTINATARIO", "")
    email_cc = os.getenv("EMAIL_CC", "")
    email_bcc = os.getenv("EMAIL_BCC", "")

    recipients = split_emails(email_to) + split_emails(email_cc) + split_emails(email_bcc)

    if not email_from:
        raise ValueError("Falta EMAIL_FROM o EMAIL_USER")
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
    """Send the report link by SMTP only.

    Gmail API is intentionally not supported in this project. Google OAuth is used only
    to create/edit/share Google Docs via Docs API and Drive API.
    """
    disabled = os.getenv("EMAIL_DELIVERY_DISABLED", "false").strip().lower()
    if disabled in {"1", "true", "yes", "y", "disabled", "none"}:
        return {"status": "skipped", "mode": "smtp_disabled"}

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")

    if not user or not password:
        raise ValueError("Para SMTP faltan EMAIL_USER o EMAIL_PASSWORD")

    msg, recipients = _build_message(subject, body)

    with smtplib.SMTP(host, port, timeout=60) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg, from_addr=msg["From"], to_addrs=recipients)

    return {"status": "sent", "mode": "smtp", "recipients": recipients}

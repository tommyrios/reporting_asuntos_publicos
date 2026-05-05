import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_email_with_attachments(subject: str, body: str, attachments: list[Path]):
    smtp_host = os.getenv("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_from = os.getenv("EMAIL_FROM", email_user)
    email_to = os.getenv("EMAIL_DESTINATARIO")
    email_cc = os.getenv("EMAIL_CC", "")
    email_bcc = os.getenv("EMAIL_BCC", "")

    if not email_user or not email_password or not email_to:
        raise ValueError("Faltan EMAIL_USER, EMAIL_PASSWORD o EMAIL_DESTINATARIO")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    if email_cc:
        msg["Cc"] = email_cc

    msg.set_content(body)

    for attachment in attachments:
        path = Path(attachment)
        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=path.name,
            )

    recipients = []
    recipients += [x.strip() for x in email_to.split(",") if x.strip()]
    recipients += [x.strip() for x in email_cc.split(",") if x.strip()]
    recipients += [x.strip() for x in email_bcc.split(",") if x.strip()]

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg, from_addr=email_from, to_addrs=recipients)

    return {"status": "sent", "recipients": recipients}
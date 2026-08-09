from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class MailerError(RuntimeError):
    pass


def send_html(
    recipients: list[str], subject: str, html: str, *, require_compliance: bool = True,
) -> None:
    if len(recipients) != 1:
        raise MailerError(
            "l'invio SMTP diretto è consentito soltanto a un destinatario; "
            "per una lista usare una campagna Brevo"
        )
    host = os.getenv("SIRACUSA_SMTP_HOST")
    sender = os.getenv("SIRACUSA_EMAIL_FROM")
    if not host or not sender:
        raise MailerError("configurare SIRACUSA_SMTP_HOST e SIRACUSA_EMAIL_FROM")
    unsubscribe_url = os.getenv("SIRACUSA_UNSUBSCRIBE_URL")
    publisher_address = os.getenv("SIRACUSA_PUBLISHER_ADDRESS")
    if require_compliance and (not unsubscribe_url or not publisher_address):
        raise MailerError("configurare SIRACUSA_UNSUBSCRIBE_URL e SIRACUSA_PUBLISHER_ADDRESS")
    port = int(os.getenv("SIRACUSA_SMTP_PORT", "587"))
    username = os.getenv("SIRACUSA_SMTP_USERNAME")
    password = os.getenv("SIRACUSA_SMTP_PASSWORD")
    use_tls = os.getenv("SIRACUSA_SMTP_TLS", "true").lower() not in {"0", "false", "no"}

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    if unsubscribe_url:
        message["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content("Questa newsletter richiede un client email compatibile con HTML.")
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=30) as client:
            if use_tls:
                client.starttls()
            if username:
                client.login(username, password or "")
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailerError(f"invio email non riuscito: {exc}") from exc

"""Best-effort SMTP email helpers for Tomb of Light auth flows.

SMTP settings are read from app.config.settings.  If SMTP is not configured
the helpers log silently and return without raising so that auth flows are
never blocked by email delivery failures.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_SENDER = "admin@tomboflight.com"


def _smtp_enabled() -> bool:
    host = str(settings.smtp_host or "").strip()
    port = int(settings.smtp_port or 0)
    return bool(host) and port > 0


def _send_email(*, to_email: str, subject: str, text_body: str) -> None:
    """Internal best-effort email sender. Never raises."""
    to_email = str(to_email or "").strip().lower()
    if not to_email:
        return

    if not _smtp_enabled():
        logger.debug("SMTP not configured; skipping email to %s", to_email)
        return

    msg = EmailMessage()
    msg["From"] = str(settings.email_sender or _DEFAULT_SENDER).strip() or _DEFAULT_SENDER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)

    host = str(settings.smtp_host).strip()
    port = int(settings.smtp_port)

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()

            username = str(settings.smtp_username or "").strip()
            password = str(settings.smtp_password or "").strip()
            if username and password:
                server.login(username, password)

            server.send_message(msg)
    except Exception:
        logger.exception("Failed to send email to %s", to_email)


def send_password_reset_email(*, to_email: str, reset_url: str, expires_at: str) -> None:
    """Send a password-reset link email to *to_email*."""
    subject = "Reset your Tomb of Light password"
    body = (
        "Hello,\n\n"
        "We received a request to reset the password for your Tomb of Light account.\n\n"
        f"Reset your password using this secure link (expires at {expires_at}):\n"
        f"{reset_url}\n\n"
        "If you did not request this reset, you can safely ignore this email.\n"
        "Someone may have entered your email address by mistake.\n"
        "If you believe this was unauthorized activity, please contact support immediately.\n\n"
        "— Tomb of Light Security\n"
    )
    _send_email(to_email=to_email, subject=subject, text_body=body)


def send_password_changed_email(*, to_email: str) -> None:
    """Send a password-change confirmation email to *to_email*."""
    subject = "Your Tomb of Light password was changed"
    body = (
        "Hello,\n\n"
        "This is a confirmation that the password for your Tomb of Light account "
        "was successfully changed.\n\n"
        "If you did not perform this action, please reset your password immediately "
        "and contact support.\n\n"
        "— Tomb of Light Security\n"
    )
    _send_email(to_email=to_email, subject=subject, text_body=body)

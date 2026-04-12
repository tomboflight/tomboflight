"""Postmark API email helpers for Tomb of Light auth flows."""

import logging
from datetime import UTC, datetime
from email.utils import formataddr
from html import escape

import requests
from requests import RequestException

from app.config import settings

logger = logging.getLogger(__name__)

POSTMARK_EMAIL_ENDPOINT = "https://api.postmarkapp.com/email"
POSTMARK_TIMEOUT_SECONDS = 10
DEFAULT_MESSAGE_STREAM = "outbound"


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_email(value: object) -> str:
    return _normalize_text(value).lower()


def _postmark_token() -> str:
    return _normalize_text(settings.postmark_server_token)


def _postmark_from_email() -> str:
    return _normalize_email(settings.postmark_from_email) or "admin@tomboflight.com"


def _postmark_from_name() -> str:
    return _normalize_text(settings.postmark_from_name) or "Tomb of Light Security"


def _postmark_message_stream() -> str:
    return _normalize_text(settings.postmark_message_stream) or DEFAULT_MESSAGE_STREAM


def _postmark_from_header() -> str:
    return formataddr((_postmark_from_name(), _postmark_from_email()))


def _send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    """Send one transactional email through Postmark. Never raises."""
    normalized_to_email = _normalize_email(to_email)
    if not normalized_to_email:
        return

    token = _postmark_token()
    if not token:
        logger.warning(
            "Postmark is not configured; skipping email to %s",
            normalized_to_email,
        )
        return

    payload = {
        "From": _postmark_from_header(),
        "To": normalized_to_email,
        "Subject": subject,
        "TextBody": text_body,
        "MessageStream": _postmark_message_stream(),
    }
    if html_body:
        payload["HtmlBody"] = html_body

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": token,
    }

    try:
        response = requests.post(
            POSTMARK_EMAIL_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=POSTMARK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except RequestException as exc:
        response = getattr(exc, "response", None)
        response_body = getattr(response, "text", "")
        logger.exception(
            "Failed to send Postmark email to %s. Response: %s",
            normalized_to_email,
            response_body,
        )


def send_password_reset_email(
    *,
    to_email: str,
    reset_url: str,
    expires_at: str,
) -> None:
    """Send a password-reset link email to *to_email*."""
    safe_reset_url = escape(_normalize_text(reset_url), quote=True)
    safe_expires_at = escape(_normalize_text(expires_at), quote=True)

    subject = "Reset your Tomb of Light password"
    text_body = (
        "Hello,\n\n"
        "We received a request to reset the password for your Tomb of Light account.\n\n"
        f"Reset your password using this secure link:\n{reset_url}\n\n"
        f"This link expires at {expires_at}.\n\n"
        "If you did not request this reset, you can safely ignore this email.\n"
        "If you believe this was unauthorized activity, please contact support immediately.\n\n"
        "Tomb of Light Security\n"
    )
    html_body = (
        "<p>Hello,</p>"
        "<p>We received a request to reset the password for your Tomb of Light "
        "account.</p>"
        f'<p><a href="{safe_reset_url}">Reset your password</a></p>'
        f"<p>This link expires at {safe_expires_at}.</p>"
        "<p>If you did not request this reset, you can safely ignore this email. "
        "If you believe this was unauthorized activity, please contact support "
        "immediately.</p>"
        "<p>Tomb of Light Security</p>"
    )

    _send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_password_changed_email(*, to_email: str) -> None:
    """Send a password-change confirmation email to *to_email*."""
    changed_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    safe_changed_at = escape(changed_at, quote=True)

    subject = "Your Tomb of Light password was changed"
    text_body = (
        "Hello,\n\n"
        "This is a confirmation that the password for your Tomb of Light account "
        "was successfully changed.\n\n"
        f"Security notice time: {changed_at}.\n\n"
        "If you made this change, no further action is needed. If you did not "
        "perform this action, reset your password immediately and contact support.\n\n"
        "Tomb of Light Security\n"
    )
    html_body = (
        "<p>Hello,</p>"
        "<p>This is a confirmation that the password for your Tomb of Light account "
        "was successfully changed.</p>"
        f"<p><strong>Security notice time:</strong> {safe_changed_at}.</p>"
        "<p>If you made this change, no further action is needed. If you did not "
        "perform this action, reset your password immediately and contact support.</p>"
        "<p>Tomb of Light Security</p>"
    )

    _send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

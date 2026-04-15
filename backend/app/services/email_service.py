"""Postmark API email helpers for Tomb of Light auth flows."""

import logging
from datetime import UTC, datetime
from email.utils import formataddr
from html import escape
from typing import Any
from urllib.parse import quote_plus, urlsplit, urlunsplit

import requests
from requests import RequestException

from app.config import settings

logger = logging.getLogger(__name__)

POSTMARK_EMAIL_ENDPOINT = "https://api.postmarkapp.com/email"
POSTMARK_TIMEOUT_SECONDS = 10
DEFAULT_MESSAGE_STREAM = "outbound"
MAX_POSTMARK_MESSAGE_LOG_LENGTH = 500


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


def _truncate_log_value(
    value: object,
    *,
    max_length: int = MAX_POSTMARK_MESSAGE_LOG_LENGTH,
) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length]}..."


def _postmark_response_details(response: requests.Response | None) -> dict[str, Any]:
    if response is None:
        return {
            "postmark_status_code": "request_error",
            "postmark_reason": None,
            "postmark_response_json": None,
            "postmark_error_code": None,
            "postmark_error_message": None,
            "postmark_message_id": None,
        }

    details: dict[str, Any] = {
        "postmark_status_code": response.status_code,
        "postmark_reason": _truncate_log_value(getattr(response, "reason", "")) or None,
        "postmark_response_json": None,
        "postmark_error_code": None,
        "postmark_error_message": None,
        "postmark_message_id": None,
    }

    try:
        payload = response.json()
    except ValueError:
        details["postmark_response_json"] = False
        details["postmark_response_content_type"] = _truncate_log_value(
            response.headers.get("Content-Type", "")
        ) or None
        return details

    details["postmark_response_json"] = True
    if not isinstance(payload, dict):
        details["postmark_response_shape"] = type(payload).__name__
        return details

    details.update(
        {
            "postmark_error_code": payload.get("ErrorCode"),
            "postmark_error_message": _truncate_log_value(payload.get("Message")) or None,
            "postmark_message_id": _truncate_log_value(payload.get("MessageID")) or None,
        }
    )
    return details


def _postmark_log_context(
    *,
    email_type: str,
    to_email: str,
    subject: str,
    response: requests.Response | None = None,
) -> dict[str, Any]:
    return {
        "event": "postmark_email_send_failed",
        "email_provider": "postmark",
        "email_type": _normalize_text(email_type) or "transactional",
        "recipient_email": _normalize_email(to_email),
        "sender_email": _postmark_from_email(),
        "message_stream": _postmark_message_stream(),
        "subject": _truncate_log_value(subject),
        **_postmark_response_details(response),
    }


def _send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    email_type: str = "transactional",
) -> None:
    """Send one transactional email through Postmark. Never raises."""
    normalized_to_email = _normalize_email(to_email)
    if not normalized_to_email:
        return

    token = _postmark_token()
    if not token:
        context = {
            "event": "postmark_email_not_configured",
            "email_provider": "postmark",
            "email_type": _normalize_text(email_type) or "transactional",
            "recipient_email": normalized_to_email,
            "sender_email": _postmark_from_email(),
            "message_stream": _postmark_message_stream(),
            "subject": _truncate_log_value(subject),
        }
        logger.warning(
            "Postmark email skipped because server token is not configured: "
            "email_type=%s recipient=%s message_stream=%s",
            context["email_type"],
            normalized_to_email,
            context["message_stream"],
            extra=context,
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
        logger.debug(
            "Sending Postmark email: recipient=%s subject=%r",
            normalized_to_email,
            subject,
        )
        response = requests.post(
            POSTMARK_EMAIL_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=POSTMARK_TIMEOUT_SECONDS,
        )
        logger.debug(
            "Postmark email response: recipient=%s subject=%r status_code=%s "
            "message_stream=%s",
            normalized_to_email,
            subject,
            response.status_code,
            payload["MessageStream"],
        )
        response.raise_for_status()
    except RequestException as exc:
        response = getattr(exc, "response", None)
        context = _postmark_log_context(
            email_type=email_type,
            to_email=normalized_to_email,
            subject=subject,
            response=response,
        )
        logger.error(
            "Postmark email send failed: email_type=%s recipient=%s "
            "status_code=%s error_code=%s error_message=%s message_stream=%s",
            context["email_type"],
            normalized_to_email,
            context["postmark_status_code"],
            context["postmark_error_code"],
            context["postmark_error_message"] or type(exc).__name__,
            context["message_stream"],
            extra=context,
            exc_info=True,
        )
    except Exception:
        context = _postmark_log_context(
            email_type=email_type,
            to_email=normalized_to_email,
            subject=subject,
        )
        logger.error(
            "Unexpected Postmark email send failure: email_type=%s recipient=%s "
            "status_code=%s message_stream=%s",
            context["email_type"],
            normalized_to_email,
            context["postmark_status_code"],
            context["message_stream"],
            extra=context,
            exc_info=True,
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
        email_type="password_reset",
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
        email_type="password_changed",
    )


def _public_app_base_url() -> str:
    source = (
        _normalize_text(settings.password_reset_base_url_clean)
        or _normalize_text(settings.stripe_billing_portal_return_url_clean)
        or "https://tomboflight.com"
    )
    parsed = urlsplit(source)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "tomboflight.com"
    return urlunsplit((scheme, netloc, "", "", "")).rstrip("/")


def send_household_invite_email(
    *,
    to_email: str,
    invite_key: str,
    project_id: str,
    member_role: str,
    inviter_email: str = "",
    is_resend: bool = False,
) -> None:
    safe_invite_key = quote_plus(_normalize_text(invite_key))
    safe_project_id = quote_plus(_normalize_text(project_id))
    safe_member_role = escape(_normalize_text(member_role), quote=True)
    safe_inviter_email = escape(_normalize_text(inviter_email), quote=True)
    app_base_url = _public_app_base_url()
    accept_url = (
        f"{app_base_url}/household-access.html"
        f"?invite_key={safe_invite_key}&project_id={safe_project_id}"
    )
    signup_url = (
        f"{app_base_url}/signup.html"
        f"?invite_key={safe_invite_key}&project_id={safe_project_id}"
    )
    signin_url = (
        f"{app_base_url}/signin.html"
        f"?invite_key={safe_invite_key}&project_id={safe_project_id}"
    )

    invite_action = "reminder to join" if is_resend else "invitation to join"
    subject = f"Tomb of Light {invite_action} your household workspace"
    invited_by_line = (
        f"Invited by: {inviter_email}\n\n" if _normalize_text(inviter_email) else ""
    )
    invited_by_html = (
        f"<p><strong>Invited by:</strong> {safe_inviter_email}</p>"
        if _normalize_text(inviter_email)
        else ""
    )
    text_body = (
        "Hello,\n\n"
        f"You have been invited to join a Tomb of Light household workspace as a {member_role}.\n\n"
        f"{invited_by_line}"
        "Use your own account credentials (do not share passwords).\n\n"
        f"Accept invite: {accept_url}\n"
        f"Sign in: {signin_url}\n"
        f"Create account: {signup_url}\n\n"
        "If you did not expect this invite, you can ignore this message.\n"
    )
    html_body = (
        "<p>Hello,</p>"
        f"<p>You have been invited to join a Tomb of Light household workspace as a "
        f"<strong>{safe_member_role}</strong>.</p>"
        f"{invited_by_html}"
        "<p>Use your own account credentials (do not share passwords).</p>"
        f'<p><a href="{escape(accept_url, quote=True)}">Accept invite</a></p>'
        f'<p><a href="{escape(signin_url, quote=True)}">Sign in</a> or '
        f'<a href="{escape(signup_url, quote=True)}">create account</a></p>'
        "<p>If you did not expect this invite, you can ignore this message.</p>"
    )
    _send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        email_type="household_invite",
    )

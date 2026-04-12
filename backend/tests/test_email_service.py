import unittest
from unittest.mock import patch

from requests import HTTPError

from app.services import email_service


class FakePostmarkResponse:
    def __init__(
        self,
        *,
        status_code=422,
        reason="Unprocessable Entity",
        payload=None,
        text="",
        headers=None,
    ):
        self.status_code = status_code
        self.reason = reason
        self.payload = payload
        self.text = text
        self.headers = dict(headers or {})

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError(f"{self.status_code} Postmark error", response=self)


class PostmarkEmailLoggingTests(unittest.TestCase):
    def test_password_reset_postmark_block_logs_safe_structured_context(self):
        response = FakePostmarkResponse(
            payload={
                "ErrorCode": 300,
                "Message": "Your Postmark account is pending approval.",
            }
        )

        with (
            patch.object(email_service, "_postmark_token", return_value="server-token"),
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs(email_service.logger, level="ERROR") as captured,
        ):
            email_service._send_email(
                to_email="USER@example.com",
                subject="Reset your Tomb of Light password",
                text_body="Use reset-token-secret to reset your password.",
                html_body=(
                    '<a href="https://example.test/reset?token=reset-token-secret">'
                    "Reset</a>"
                ),
                email_type="password_reset",
            )

        self.assertEqual(len(captured.records), 1)
        record = captured.records[0]
        self.assertEqual(record.event, "postmark_email_send_failed")
        self.assertEqual(record.email_provider, "postmark")
        self.assertEqual(record.email_type, "password_reset")
        self.assertEqual(record.recipient_email, "user@example.com")
        self.assertEqual(record.message_stream, "outbound")
        self.assertEqual(record.postmark_status_code, 422)
        self.assertEqual(record.postmark_error_code, 300)
        self.assertEqual(
            record.postmark_error_message,
            "Your Postmark account is pending approval.",
        )

        logged_output = "\n".join(captured.output)
        self.assertIn("pending approval", logged_output)
        self.assertNotIn("server-token", logged_output)
        self.assertNotIn("reset-token-secret", logged_output)
        self.assertNotIn("https://example.test/reset", logged_output)

    def test_non_json_postmark_failure_does_not_log_raw_response_body(self):
        response = FakePostmarkResponse(
            status_code=500,
            reason="Internal Server Error",
            payload=ValueError("not json"),
            text="raw body containing reset-token-secret",
            headers={"Content-Type": "text/html"},
        )

        with (
            patch.object(email_service, "_postmark_token", return_value="server-token"),
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs(email_service.logger, level="ERROR") as captured,
        ):
            email_service._send_email(
                to_email="user@example.com",
                subject="Reset your Tomb of Light password",
                text_body="Use reset-token-secret to reset your password.",
                html_body=None,
                email_type="password_reset",
            )

        record = captured.records[0]
        self.assertFalse(record.postmark_response_json)
        self.assertEqual(record.postmark_response_content_type, "text/html")

        logged_output = "\n".join(captured.output)
        self.assertNotIn("raw body", logged_output)
        self.assertNotIn("server-token", logged_output)
        self.assertNotIn("reset-token-secret", logged_output)


if __name__ == "__main__":
    unittest.main()

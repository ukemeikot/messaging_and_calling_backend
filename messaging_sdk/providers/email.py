"""
Email delivery providers for the Messaging & Calling SDK.

This layer is transport-focused: it accepts already-rendered subject/body
content and handles provider-specific delivery.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Optional

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from messaging_sdk.core.config import Settings, settings as default_settings

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract base class for email delivery providers."""

    def __init__(self, from_email: str, from_name: str, frontend_url: str):
        self.from_email = from_email
        self.from_name = from_name
        self.frontend_url = frontend_url

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send an already-rendered email payload."""

    async def send_verification_email(self, to_email: str, token: str) -> bool:
        """Legacy helper retained for provider compatibility."""
        verification_url = f"{self.frontend_url}/verify-email?token={token}"
        return await self.send_email(
            to_email,
            "Verify Your Email Address",
            (
                "<html><body><h2>Verify your email</h2>"
                f"<p><a href=\"{verification_url}\">Verify Email</a></p>"
                f"<p>{verification_url}</p></body></html>"
            ),
            f"Verify your email: {verification_url}",
        )

    async def send_password_reset_email(self, to_email: str, token: str) -> bool:
        """Legacy helper retained for provider compatibility."""
        reset_url = f"{self.frontend_url}/reset-password?token={token}"
        return await self.send_email(
            to_email,
            "Reset Your Password",
            (
                "<html><body><h2>Password reset</h2>"
                f"<p><a href=\"{reset_url}\">Reset Password</a></p>"
                f"<p>{reset_url}</p></body></html>"
            ),
            f"Reset your password: {reset_url}",
        )


class ResendProvider(EmailProvider):
    """Email provider using Resend API."""

    def __init__(self, api_key: str, from_email: str, from_name: str, frontend_url: str):
        super().__init__(from_email, from_name, frontend_url)
        try:
            import resend

            resend.api_key = api_key
            self.resend = resend
        except ImportError as exc:
            raise ImportError(
                "resend package is required for ResendProvider. Install with: pip install resend"
            ) from exc

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        try:
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            if text_content:
                params["text"] = text_content

            result = self.resend.Emails.send(params)
            if result and result.get("id"):
                logger.info("Email sent successfully via Resend to %s", to_email)
                return True

            logger.error("Failed to send email via Resend to %s: %s", to_email, result)
            return False
        except Exception as exc:
            logger.error("Error sending email via Resend to %s: %s", to_email, exc)
            return False


class SendGridProvider(EmailProvider):
    """Email provider using SendGrid API."""

    def __init__(self, api_key: str, from_email: str, from_name: str, frontend_url: str):
        super().__init__(from_email, from_name, frontend_url)
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import From, Mail, Subject, To

            self.sg = SendGridAPIClient(api_key)
            self.Mail = Mail
            self.From = From
            self.To = To
            self.Subject = Subject
        except ImportError as exc:
            raise ImportError(
                "sendgrid package is required for SendGridProvider. Install with: pip install sendgrid"
            ) from exc

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        try:
            from sendgrid.helpers.mail import HtmlContent, PlainTextContent

            mail = self.Mail(
                self.From(self.from_email, self.from_name),
                self.To(to_email),
                self.Subject(subject),
            )
            mail.add_content(HtmlContent(html_content))
            if text_content:
                mail.add_content(PlainTextContent(text_content))

            response = self.sg.send(mail)
            if response.status_code in [200, 201, 202]:
                logger.info("Email sent successfully via SendGrid to %s", to_email)
                return True

            logger.error(
                "Failed to send email via SendGrid to %s: %s %s",
                to_email,
                response.status_code,
                response.body,
            )
            return False
        except Exception as exc:
            logger.error("Error sending email via SendGrid to %s: %s", to_email, exc)
            return False


class SMTPProvider(EmailProvider):
    """Email provider using SMTP transport."""

    def __init__(
        self,
        host: str,
        port: int,
        username: Optional[str],
        password: Optional[str],
        use_tls: bool,
        from_email: str,
        from_name: str,
        frontend_url: str,
    ):
        super().__init__(from_email, from_name, frontend_url)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = to_email

        if text_content:
            message.attach(MIMEText(text_content, "plain", "utf-8"))
        message.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
            logger.info("Email sent successfully via SMTP to %s", to_email)
            return True
        except Exception as exc:
            logger.error("Error sending email via SMTP to %s: %s", to_email, exc)
            return False


class ConsoleProvider(EmailProvider):
    """Email provider that logs content to stdout."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        print(f"\n{'=' * 50}")
        print(f"EMAIL TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"FROM: {self.from_name} <{self.from_email}>")
        print(f"{'=' * 50}")
        if text_content:
            print(f"TEXT VERSION:\n{text_content}")
        print(f"{'=' * 50}")
        print(f"HTML VERSION:\n{html_content}")
        print(f"{'=' * 50}\n")
        return True


def get_email_provider(settings_obj: Optional[Settings] = None) -> EmailProvider:
    """Return the configured email delivery provider."""
    email_config = settings_obj or default_settings

    if email_config.email_provider == "resend":
        if not email_config.resend_api_key:
            raise ValueError("Resend API key not configured")
        return ResendProvider(
            api_key=email_config.resend_api_key.get_secret_value(),
            from_email=email_config.resend_from_email,
            from_name=email_config.resend_from_name,
            frontend_url=email_config.frontend_url,
        )

    if email_config.email_provider == "sendgrid":
        if not email_config.sendgrid_api_key:
            raise ValueError("SendGrid API key not configured")
        return SendGridProvider(
            api_key=email_config.sendgrid_api_key.get_secret_value(),
            from_email=email_config.resend_from_email,
            from_name=email_config.resend_from_name,
            frontend_url=email_config.frontend_url,
        )

    if email_config.email_provider == "smtp":
        if not email_config.smtp_host:
            raise ValueError("SMTP host not configured")
        return SMTPProvider(
            host=email_config.smtp_host,
            port=email_config.smtp_port,
            username=email_config.smtp_username,
            password=(
                email_config.smtp_password.get_secret_value()
                if email_config.smtp_password
                else None
            ),
            use_tls=email_config.smtp_use_tls,
            from_email=email_config.resend_from_email,
            from_name=email_config.resend_from_name,
            frontend_url=email_config.frontend_url,
        )

    if email_config.email_provider == "console":
        return ConsoleProvider(
            from_email=email_config.resend_from_email,
            from_name=email_config.resend_from_name,
            frontend_url=email_config.frontend_url,
        )

    raise ValueError(f"Unsupported email provider: {email_config.email_provider}")


email_provider = get_email_provider()

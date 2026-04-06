"""
Email provider abstraction for Messaging & Calling SDK.

This module provides a pluggable email system that supports multiple providers:
- Resend (default, free tier)
- SendGrid
- SMTP

Usage:
    from messaging_sdk.providers.email import EmailProvider, get_email_provider

    provider = get_email_provider()
    await provider.send_verification_email(user_email, token)
"""

import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from messaging_sdk.core.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract base class for email providers."""

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
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Optional plain text version

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    async def send_verification_email(self, to_email: str, token: str) -> bool:
        """Send email verification email."""
        verification_url = f"{self.frontend_url}/verify-email?token={token}"

        subject = "Verify Your Email Address"
        html_content = f"""
        <html>
        <body>
            <h2>Welcome! Please verify your email address</h2>
            <p>Click the link below to verify your account:</p>
            <a href="{verification_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a>
            <p>If the button doesn't work, copy and paste this URL into your browser:</p>
            <p>{verification_url}</p>
            <p>This link will expire in 24 hours.</p>
        </body>
        </html>
        """

        text_content = f"""
        Welcome! Please verify your email address.

        Click this link to verify your account: {verification_url}

        This link will expire in 24 hours.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_password_reset_email(self, to_email: str, token: str) -> bool:
        """Send password reset email."""
        reset_url = f"{self.frontend_url}/reset-password?token={token}"

        subject = "Reset Your Password"
        html_content = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>You requested a password reset. Click the link below to set a new password:</p>
            <a href="{reset_url}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a>
            <p>If the button doesn't work, copy and paste this URL into your browser:</p>
            <p>{reset_url}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't request this reset, please ignore this email.</p>
        </body>
        </html>
        """

        text_content = f"""
        Password Reset Request

        You requested a password reset. Click this link to set a new password: {reset_url}

        This link will expire in 24 hours.

        If you didn't request this reset, please ignore this email.
        """

        return await self.send_email(to_email, subject, html_content, text_content)


class ResendProvider(EmailProvider):
    """Email provider using Resend API."""

    def __init__(self, api_key: str, from_email: str, from_name: str, frontend_url: str):
        super().__init__(from_email, from_name, frontend_url)
        try:
            import resend
            resend.api_key = api_key
            self.resend = resend
        except ImportError:
            raise ImportError("resend package is required for ResendProvider. Install with: pip install resend")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email using Resend API."""
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
                logger.info(f"Email sent successfully via Resend to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email via Resend to {to_email}: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending email via Resend to {to_email}: {str(e)}")
            return False


class SendGridProvider(EmailProvider):
    """Email provider using SendGrid API."""

    def __init__(self, api_key: str, from_email: str, from_name: str, frontend_url: str):
        super().__init__(from_email, from_name, frontend_url)
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, From, To, Subject, Content
            self.sg = SendGridAPIClient(api_key)
            self.Mail = Mail
            self.From = From
            self.To = To
            self.Subject = Subject
            self.Content = Content
        except ImportError:
            raise ImportError("sendgrid package is required for SendGridProvider. Install with: pip install sendgrid")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email using SendGrid API."""
        try:
            from_email_obj = self.From(self.from_email, self.from_name)
            to_email_obj = self.To(to_email)
            subject_obj = self.Subject(subject)

            # Create mail object
            mail = self.Mail(from_email_obj, to_email_obj, subject_obj)

            # Add HTML content
            from sendgrid.helpers.mail import HtmlContent
            html_content_obj = HtmlContent(html_content)
            mail.add_content(html_content_obj)

            # Add text content if provided
            if text_content:
                from sendgrid.helpers.mail import PlainTextContent
                text_content_obj = PlainTextContent(text_content)
                mail.add_content(text_content_obj)

            # Send email
            response = self.sg.send(mail)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully via SendGrid to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email via SendGrid to {to_email}: {response.status_code} {response.body}")
                return False

        except Exception as e:
            logger.error(f"Error sending email via SendGrid to {to_email}: {str(e)}")
            return False


class ConsoleProvider(EmailProvider):
    """Email provider that logs to console (for testing)."""

    def __init__(self, from_email: str, from_name: str, frontend_url: str):
        super().__init__(from_email, from_name, frontend_url)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Log email to console instead of sending."""
        print(f"\n{'='*50}")
        print(f"📧 EMAIL TO: {to_email}")
        print(f"📧 SUBJECT: {subject}")
        print(f"📧 FROM: {self.from_name} <{self.from_email}>")
        print(f"{'='*50}")
        if text_content:
            print(f"TEXT VERSION:\n{text_content}")
        print(f"{'='*50}")
        print(f"HTML VERSION:\n{html_content}")
        print(f"{'='*50}\n")
        return True


def get_email_provider() -> EmailProvider:
    """
    Factory function to get the configured email provider.

    Returns:
        Configured EmailProvider instance

    Raises:
        ValueError: If email provider is not configured properly
    """
    email_config = settings

    if email_config.email_provider == "resend":
        if not email_config.resend_api_key:
            raise ValueError("Resend API key not configured")
        return ResendProvider(
            api_key=email_config.resend_api_key.get_secret_value(),
            from_email=email_config.resend_from_email,
            from_name=email_config.resend_from_name,
            frontend_url=email_config.frontend_url
        )

    elif email_config.email_provider == "sendgrid":
        if not email_config.sendgrid_api_key:
            raise ValueError("SendGrid API key not configured")
        return SendGridProvider(
            api_key=email_config.sendgrid_api_key.get_secret_value(),
            from_email=email_config.resend_from_email,  # Reuse resend from_email setting
            from_name=email_config.resend_from_name,    # Reuse resend from_name setting
            frontend_url=email_config.frontend_url
        )

    elif email_config.email_provider == "smtp":
        if not email_config.smtp_host:
            raise ValueError("SMTP host not configured")
        return SMTPProvider(
            host=email_config.smtp_host,
            port=email_config.smtp_port,
            username=email_config.smtp_username,
            password=email_config.smtp_password,
            use_tls=email_config.smtp_use_tls,
            from_email=email_config.resend_from_email,  # Reuse resend from_email setting
            from_name=email_config.resend_from_name,    # Reuse resend from_name setting
            frontend_url=email_config.frontend_url
        )

    elif email_config.email_provider == "console":
        return ConsoleProvider(
            from_email=email_config.resend_from_email,
            from_name=email_config.resend_from_name,
            frontend_url=email_config.frontend_url
        )

    else:
        raise ValueError(f"Unsupported email provider: {email_config.email_provider}")


# Global email provider instance
email_provider = get_email_provider()
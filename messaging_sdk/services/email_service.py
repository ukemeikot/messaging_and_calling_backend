"""
Email service for Messaging & Calling SDK.

This service provides a unified interface for sending emails using
configurable email providers (Resend, SendGrid, SMTP).
"""

import logging
from typing import Optional

from messaging_sdk.providers.email import email_provider

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service that uses the configured email provider.

    This service provides high-level methods for common email operations
    like verification and password reset, while delegating the actual
    sending to the configured email provider.
    """

    def __init__(self):
        self.provider = email_provider

    async def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str
    ) -> bool:
        """
        Send email verification link.

        Args:
            to_email: Recipient email address
            username: User's username for personalization
            verification_token: Verification token

        Returns:
            True if sent successfully, False otherwise
        """
        return await self.provider.send_verification_email(to_email, verification_token)

    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """
        Send password reset link.

        Args:
            to_email: Recipient email address
            username: User's username for personalization
            reset_token: Password reset token

        Returns:
            True if sent successfully, False otherwise
        """
        return await self.provider.send_password_reset_email(to_email, reset_token)

    async def send_custom_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send a custom email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Optional plain text version

        Returns:
            True if sent successfully, False otherwise
        """
        return await self.provider.send_email(to_email, subject, html_content, text_content)


# Global email service instance
email_service = EmailService()
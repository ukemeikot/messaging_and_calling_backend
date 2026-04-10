"""
Email service for the Messaging & Calling SDK.

This service composes email content separately from provider delivery so apps
can customize templates, links, and branding without replacing transport.
"""

from __future__ import annotations

import logging
from typing import Optional

from messaging_sdk.core.config import Settings, settings as default_settings
from messaging_sdk.emailing import (
    EmailComposer,
    EmailCustomization,
    get_active_email_customization,
)
from messaging_sdk.providers.email import EmailProvider, get_email_provider

logger = logging.getLogger(__name__)


class EmailService:
    """
    High-level email orchestration service.

    Public send methods stay stable while composition and provider concerns stay
    decoupled underneath.
    """

    def __init__(
        self,
        *,
        settings_obj: Optional[Settings] = None,
        provider: Optional[EmailProvider] = None,
        customization: Optional[EmailCustomization] = None,
        composer: Optional[EmailComposer] = None,
    ):
        self.settings = settings_obj or default_settings
        self.provider = provider or get_email_provider(self.settings)
        active_customization = customization or get_active_email_customization(self.settings)
        self.composer = composer or EmailComposer(
            settings_obj=self.settings,
            customization=active_customization,
        )

    async def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str,
    ) -> bool:
        message = self.composer.compose(
            "verify_email",
            to_email=to_email,
            username=username,
            tokens={"verification_token": verification_token},
        )
        return await self.provider.send_email(
            to_email=to_email,
            subject=message.subject,
            html_content=message.html_body,
            text_content=message.text_body,
        )

    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str,
    ) -> bool:
        message = self.composer.compose(
            "password_reset",
            to_email=to_email,
            username=username,
            tokens={"reset_token": reset_token},
        )
        return await self.provider.send_email(
            to_email=to_email,
            subject=message.subject,
            html_content=message.html_body,
            text_content=message.text_body,
        )

    async def send_custom_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        return await self.provider.send_email(to_email, subject, html_content, text_content)


email_service = EmailService()

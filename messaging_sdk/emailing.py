"""
Email composition primitives for the Messaging & Calling SDK.

This module separates email content generation from provider delivery so apps
can customize templates, links, and branding without replacing the transport
layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    select_autoescape,
)

from messaging_sdk.core.config import Settings, settings as default_settings

EmailLinkBuilder = Callable[["EmailTemplateContext"], str]
EmailContextHook = Callable[["EmailTemplateContext"], Optional["EmailTemplateContext"]]
EmailMessageHook = Callable[["EmailMessage", "EmailTemplateContext"], Optional["EmailMessage"]]

DEFAULT_EMAIL_TEMPLATE_DIR = Path(__file__).resolve().parent / "email_templates"


@dataclass
class EmailMessage:
    """Rendered email payload ready for provider delivery."""

    subject: str
    html_body: str
    text_body: str
    headers: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class EmailTheme:
    """Branding and theme values exposed to templates."""

    app_name: str = "Your App"
    logo_url: Optional[str] = None
    primary_color: str = "#1d4ed8"
    accent_color: str = "#0f172a"
    support_email: Optional[str] = None
    support_url: Optional[str] = None
    footer_text: Optional[str] = None
    product_url: Optional[str] = None


@dataclass
class EmailTemplateContext:
    """Normalized context passed through link builders, hooks, and templates."""

    intent: str
    recipient_email: str
    user: dict[str, Any]
    tokens: dict[str, str]
    links: dict[str, str]
    theme: EmailTheme
    app: dict[str, Any]
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the context to a template-friendly dictionary."""
        return {
            "intent": self.intent,
            "recipient_email": self.recipient_email,
            "user": self.user,
            "tokens": self.tokens,
            "links": self.links,
            "theme": asdict(self.theme),
            "app": self.app,
            "data": self.data,
        }


@dataclass
class EmailCustomization:
    """Optional email customization bundle for applications."""

    template_dir: Optional[str | Path] = None
    theme: Optional[EmailTheme | dict[str, Any]] = None
    renderer: Optional["EmailTemplateRenderer"] = None
    link_builders: dict[str, EmailLinkBuilder] = field(default_factory=dict)
    before_render: Optional[EmailContextHook] = None
    after_render: Optional[EmailMessageHook] = None


@dataclass(frozen=True)
class _EmailIntentConfig:
    subject: str
    html_template: str
    text_template: str
    action_label: str
    headline: str
    intro_text: str
    expiry_text: str
    ignore_text: str
    link_key: str


EMAIL_INTENTS: dict[str, _EmailIntentConfig] = {
    "verify_email": _EmailIntentConfig(
        subject="Verify Your Email Address",
        html_template="verify_email.html",
        text_template="verify_email.txt",
        action_label="Verify Email",
        headline="Welcome! Please verify your email address",
        intro_text="Confirm your account to unlock messaging, calling, and profile features.",
        expiry_text="This verification link will expire in 24 hours.",
        ignore_text="If you did not create this account, you can safely ignore this email.",
        link_key="verify_email_url",
    ),
    "password_reset": _EmailIntentConfig(
        subject="Reset Your Password",
        html_template="password_reset.html",
        text_template="password_reset.txt",
        action_label="Reset Password",
        headline="Password reset request",
        intro_text="Use the secure link below to choose a new password for your account.",
        expiry_text="This password reset link will expire in 1 hour.",
        ignore_text="If you did not request a password reset, you can ignore this email.",
        link_key="password_reset_url",
    ),
}


class EmailTemplateRenderer:
    """Jinja-backed email renderer with override fallback support."""

    def __init__(self, template_dir: Optional[str | Path] = None):
        loaders: list[FileSystemLoader] = []

        if template_dir:
            resolved = Path(template_dir).expanduser()
            if not resolved.is_absolute():
                resolved = Path.cwd() / resolved
            loaders.append(FileSystemLoader(str(resolved)))

        loaders.append(FileSystemLoader(str(DEFAULT_EMAIL_TEMPLATE_DIR)))
        self.environment = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        try:
            template = self.environment.get_template(template_name)
            return template.render(**context).strip()
        except TemplateError as exc:
            raise ValueError(f"Failed to render email template '{template_name}': {exc}") from exc


class EmailComposer:
    """Compose rendered email messages from templates and hooks."""

    def __init__(
        self,
        settings_obj: Settings,
        customization: Optional[EmailCustomization] = None,
    ):
        self.settings = settings_obj
        self.customization = merge_email_customization(
            build_email_customization_from_settings(settings_obj),
            customization,
        )
        self.renderer = self.customization.renderer or EmailTemplateRenderer(
            self.customization.template_dir
        )
        self.link_builders = {
            "verify_email": default_verification_link_builder,
            "password_reset": default_password_reset_link_builder,
        }
        self.link_builders.update(self.customization.link_builders)
        self.theme = coerce_email_theme(self.customization.theme) or build_default_theme(settings_obj)

    def compose(
        self,
        intent: str,
        *,
        to_email: str,
        username: Optional[str],
        tokens: dict[str, str],
        user: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> EmailMessage:
        if intent not in EMAIL_INTENTS:
            raise ValueError(f"Unsupported email intent: {intent}")

        intent_config = EMAIL_INTENTS[intent]
        base_context = EmailTemplateContext(
            intent=intent,
            recipient_email=to_email,
            user={
                "email": to_email,
                "username": username,
                **(user or {}),
            },
            tokens=tokens,
            links={},
            theme=self.theme,
            app={
                "name": self.theme.app_name,
                "frontend_url": self.settings.frontend_url,
            },
            data={
                "subject": intent_config.subject,
                "action_label": intent_config.action_label,
                "headline": intent_config.headline,
                "intro_text": intent_config.intro_text,
                "expiry_text": intent_config.expiry_text,
                "ignore_text": intent_config.ignore_text,
                **(data or {}),
            },
        )
        base_context.links = self._build_links(base_context)

        if self.customization.before_render:
            updated_context = self.customization.before_render(base_context)
            if updated_context is not None:
                base_context = updated_context

        template_context = base_context.to_dict()
        html_body = self.renderer.render(intent_config.html_template, template_context)
        text_body = self.renderer.render(intent_config.text_template, template_context)
        message = EmailMessage(
            subject=str(base_context.data.get("subject", intent_config.subject)),
            html_body=html_body,
            text_body=text_body,
        )

        if self.customization.after_render:
            updated_message = self.customization.after_render(message, base_context)
            if updated_message is not None:
                message = updated_message

        return message

    def _build_links(self, context: EmailTemplateContext) -> dict[str, str]:
        builder = self.link_builders.get(context.intent)
        if not builder:
            raise ValueError(f"No link builder configured for email intent: {context.intent}")

        action_url = builder(context)
        intent_config = EMAIL_INTENTS[context.intent]
        return {
            "action_url": action_url,
            intent_config.link_key: action_url,
        }


def default_verification_link_builder(context: EmailTemplateContext) -> str:
    token = context.tokens.get("verification_token")
    if not token:
        raise ValueError("Verification email context is missing verification_token")
    return f"{context.app['frontend_url']}/verify-email?token={token}"


def default_password_reset_link_builder(context: EmailTemplateContext) -> str:
    token = context.tokens.get("reset_token")
    if not token:
        raise ValueError("Password reset email context is missing reset_token")
    return f"{context.app['frontend_url']}/reset-password?token={token}"


def coerce_email_theme(theme: Optional[EmailTheme | dict[str, Any]]) -> Optional[EmailTheme]:
    if theme is None:
        return None
    if isinstance(theme, EmailTheme):
        return theme
    return EmailTheme(**theme)


def build_default_theme(settings_obj: Settings) -> EmailTheme:
    footer_text = settings_obj.email_theme_footer_text or (
        f"Sent by {settings_obj.email_theme_app_name or settings_obj.resend_from_name}"
    )
    return EmailTheme(
        app_name=settings_obj.email_theme_app_name or settings_obj.resend_from_name,
        logo_url=settings_obj.email_theme_logo_url,
        primary_color=settings_obj.email_theme_primary_color,
        accent_color=settings_obj.email_theme_accent_color,
        support_email=settings_obj.email_theme_support_email or settings_obj.resend_from_email,
        support_url=settings_obj.email_theme_support_url,
        footer_text=footer_text,
        product_url=settings_obj.email_theme_product_url or settings_obj.frontend_url,
    )


def build_email_customization_from_settings(settings_obj: Settings) -> EmailCustomization:
    return EmailCustomization(
        template_dir=settings_obj.email_template_dir,
        theme=build_default_theme(settings_obj),
    )


def merge_email_customization(
    base: Optional[EmailCustomization],
    override: Optional[EmailCustomization],
) -> Optional[EmailCustomization]:
    if base is None:
        return override
    if override is None:
        return base

    merged_builders = dict(base.link_builders)
    merged_builders.update(override.link_builders)
    return EmailCustomization(
        template_dir=override.template_dir or base.template_dir,
        theme=override.theme or base.theme,
        renderer=override.renderer or base.renderer,
        link_builders=merged_builders,
        before_render=override.before_render or base.before_render,
        after_render=override.after_render or base.after_render,
    )


_active_email_customization: Optional[EmailCustomization] = None
_active_settings: Settings = default_settings


def configure_email_runtime(
    settings_obj: Settings,
    customization: Optional[EmailCustomization] = None,
) -> None:
    """Configure the runtime email customization used by EmailService."""
    global _active_email_customization, _active_settings
    _active_settings = settings_obj
    _active_email_customization = customization


def get_active_email_customization(
    settings_obj: Optional[Settings] = None,
) -> Optional[EmailCustomization]:
    active_settings = settings_obj or _active_settings
    return merge_email_customization(
        build_email_customization_from_settings(active_settings),
        _active_email_customization,
    )


def get_email_composer(settings_obj: Optional[Settings] = None) -> EmailComposer:
    active_settings = settings_obj or _active_settings
    return EmailComposer(
        settings_obj=active_settings,
        customization=get_active_email_customization(active_settings),
    )

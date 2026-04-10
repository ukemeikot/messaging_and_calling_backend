import shutil
import uuid
from pathlib import Path

import pytest

from messaging_sdk.core.config import Settings
from messaging_sdk.emailing import EmailCustomization, EmailMessage, EmailTemplateContext
from messaging_sdk.providers.email import ConsoleProvider, EmailProvider
from messaging_sdk.services.email_service import EmailService


class CaptureProvider(EmailProvider):
    def __init__(self):
        super().__init__(
            from_email="noreply@example.com",
            from_name="Example App",
            frontend_url="http://localhost:3000",
        )
        self.messages: list[dict[str, str | None]] = []

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
    ) -> bool:
        self.messages.append(
            {
                "to_email": to_email,
                "subject": subject,
                "html_content": html_content,
                "text_content": text_content,
            }
        )
        return True


def _settings(**overrides):
    values = {
        "email_provider": "console",
        "resend_from_email": "noreply@example.com",
        "resend_from_name": "Example App",
        "frontend_url": "http://localhost:3000",
        "email_theme_app_name": "Example App",
        "email_theme_support_email": "support@example.com",
    }
    values.update(overrides)
    return Settings(
        **values,
    )


@pytest.fixture
def template_dir():
    base_dir = Path.cwd() / ".test-artifacts" / f"email-templates-{uuid.uuid4().hex}"
    base_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield base_dir
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_default_email_templates_render_without_customization():
    provider = CaptureProvider()
    service = EmailService(settings_obj=_settings(), provider=provider)

    sent = await service.send_verification_email(
        "person@example.com",
        "person",
        "verification-token",
    )

    assert sent is True
    assert provider.messages[0]["subject"] == "Verify Your Email Address"
    assert "verification-token" in str(provider.messages[0]["html_content"])
    assert "Verify Email" in str(provider.messages[0]["text_content"])


@pytest.mark.asyncio
async def test_custom_template_directory_overrides_built_in_templates(template_dir: Path):
    (template_dir / "verify_email.html").write_text(
        "<html><body>Custom verify for {{ user.username }} at {{ links.action_url }}</body></html>",
        encoding="utf-8",
    )
    provider = CaptureProvider()
    service = EmailService(
        settings_obj=_settings(email_template_dir=str(template_dir)),
        provider=provider,
    )

    await service.send_verification_email("person@example.com", "person", "verification-token")

    assert "Custom verify for person" in str(provider.messages[0]["html_content"])
    assert "verification-token" in str(provider.messages[0]["html_content"])


@pytest.mark.asyncio
async def test_missing_override_template_falls_back_to_default(template_dir: Path):
    (template_dir / "verify_email.html").write_text(
        "<html><body>Only verify override</body></html>",
        encoding="utf-8",
    )
    provider = CaptureProvider()
    service = EmailService(
        settings_obj=_settings(email_template_dir=str(template_dir)),
        provider=provider,
    )

    await service.send_password_reset_email("person@example.com", "person", "reset-token")

    assert "Reset Your Password" in str(provider.messages[0]["subject"])
    assert "reset-token" in str(provider.messages[0]["html_content"])


@pytest.mark.asyncio
async def test_invalid_override_template_fails_clearly(template_dir: Path):
    (template_dir / "verify_email.html").write_text(
        "{% if user.username %}<p>{{ broken }}</p>",
        encoding="utf-8",
    )
    provider = CaptureProvider()
    service = EmailService(
        settings_obj=_settings(email_template_dir=str(template_dir)),
        provider=provider,
    )

    with pytest.raises(ValueError, match="Failed to render email template"):
        await service.send_verification_email("person@example.com", "person", "verification-token")


@pytest.mark.asyncio
async def test_custom_link_builder_and_hooks_are_applied():
    provider = CaptureProvider()

    def build_verify_link(context: EmailTemplateContext) -> str:
        return f"https://accounts.example.com/verify/{context.tokens['verification_token']}"

    def before_render(context: EmailTemplateContext):
        context.data["subject"] = "Please confirm your account"
        context.data["intro_text"] = "Custom intro copy"
        return context

    def after_render(message: EmailMessage, context: EmailTemplateContext):
        return EmailMessage(
            subject=message.subject,
            html_body=message.html_body + "<!-- signed -->",
            text_body=message.text_body + "\nSigned",
        )

    service = EmailService(
        settings_obj=_settings(),
        provider=provider,
        customization=EmailCustomization(
            link_builders={"verify_email": build_verify_link},
            before_render=before_render,
            after_render=after_render,
        ),
    )

    await service.send_verification_email("person@example.com", "person", "verification-token")

    assert provider.messages[0]["subject"] == "Please confirm your account"
    assert "https://accounts.example.com/verify/verification-token" in str(
        provider.messages[0]["html_content"]
    )
    assert "Custom intro copy" in str(provider.messages[0]["html_content"])
    assert "<!-- signed -->" in str(provider.messages[0]["html_content"])
    assert "Signed" in str(provider.messages[0]["text_content"])


@pytest.mark.asyncio
async def test_theme_values_appear_in_rendered_output():
    provider = CaptureProvider()
    service = EmailService(
        settings_obj=_settings(
            email_theme_app_name="Launchpad",
            email_theme_primary_color="#ff6b35",
            email_theme_footer_text="Launchpad support team",
        ),
        provider=provider,
    )

    await service.send_password_reset_email("person@example.com", "person", "reset-token")

    assert "Launchpad" in str(provider.messages[0]["html_content"])
    assert "#ff6b35" in str(provider.messages[0]["html_content"])
    assert "Launchpad support team" in str(provider.messages[0]["html_content"])


@pytest.mark.asyncio
async def test_console_provider_outputs_rendered_content(capsys):
    service = EmailService(
        settings_obj=_settings(),
        provider=ConsoleProvider(
            from_email="noreply@example.com",
            from_name="Example App",
            frontend_url="http://localhost:3000",
        ),
    )

    await service.send_password_reset_email("person@example.com", "person", "reset-token")

    captured = capsys.readouterr().out
    assert "SUBJECT: Reset Your Password" in captured
    assert "reset-token" in captured
    assert "Example App" in captured

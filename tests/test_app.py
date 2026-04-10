import pytest

from messaging_sdk import MessagingApp
from messaging_sdk.core.config import Settings


def test_messaging_app_initializes_with_test_settings():
    app = MessagingApp(settings=Settings(), title="Test App")

    assert app.title == "Test App"
    assert app.docs_url == "/docs"


def test_messaging_app_rejects_wildcard_cors_outside_development():
    settings = Settings(
        environment="production",
        cors_origins=["*"],
        email_provider="console",
    )

    with pytest.raises(ValueError, match="CORS wildcard origins"):
        MessagingApp(settings=settings, title="Test App")

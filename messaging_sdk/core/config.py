"""
Configuration management for Messaging & Calling SDK.

This module provides centralized configuration using Pydantic BaseSettings.
Supports loading from environment variables and optional YAML config file.

Usage:
    from messaging_sdk.core.config import settings

    # Access settings
    db_url = settings.database_url
    secret_key = settings.secret_key
"""

import os
from typing import Optional, List, Literal
from pathlib import Path

from pydantic import Field, validator
from pydantic_settings import BaseSettings
from pydantic.types import SecretStr


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: str = Field(..., env="DATABASE_URL")
    url_async: Optional[str] = Field(None, env="DATABASE_URL_ASYNC")

    @validator("url")
    def fix_postgresql_protocol(cls, v):
        """Convert postgresql:// to postgresql+asyncpg:// for async driver."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    class Config:
        env_prefix = "DATABASE_"


class SecuritySettings(BaseSettings):
    """Security and authentication settings."""

    secret_key: str = Field(..., env="SECRET_KEY", min_length=32)
    algorithm: str = Field("HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(15, env="ACCESS_TOKEN_EXPIRE_MINUTES", ge=1)
    refresh_token_expire_days: int = Field(7, env="REFRESH_TOKEN_EXPIRE_DAYS", ge=1)
    verification_token_expire_hours: int = Field(24, env="VERIFICATION_TOKEN_EXPIRE_HOURS", ge=1)

    class Config:
        env_prefix = "SECURITY_"


class OAuthSettings(BaseSettings):
    """OAuth provider settings."""

    google_client_id: str = Field(..., env="GOOGLE_CLIENT_ID")
    google_client_secret: SecretStr = Field(..., env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(..., env="GOOGLE_REDIRECT_URI")
    mobile_app_scheme: str = Field("enterprisemessaging", env="MOBILE_APP_SCHEME")

    class Config:
        env_prefix = "OAUTH_"


class EmailSettings(BaseSettings):
    """Email provider settings."""

    provider: Literal["resend", "sendgrid", "smtp", "console"] = Field("resend", env="EMAIL_PROVIDER")
    frontend_url: str = Field("http://localhost:3000", env="FRONTEND_URL")

    # Resend settings
    resend_api_key: Optional[SecretStr] = Field(None, env="RESEND_API_KEY")
    resend_from_email: str = Field("onboarding@resend.dev", env="RESEND_FROM_EMAIL")
    resend_from_name: str = Field("Your App", env="RESEND_FROM_NAME")

    # SendGrid settings
    sendgrid_api_key: Optional[SecretStr] = Field(None, env="SENDGRID_API_KEY")

    # SMTP settings
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(None, env="SMTP_USERNAME")
    smtp_password: Optional[SecretStr] = Field(None, env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, env="SMTP_USE_TLS")

    @validator("resend_api_key", pre=True, always=True)
    def validate_resend_settings(cls, v, values):
        """Validate Resend settings when provider is resend."""
        if values.get("provider") == "resend" and not v:
            raise ValueError("RESEND_API_KEY is required when EMAIL_PROVIDER=resend")
        return v

    @validator("sendgrid_api_key", pre=True, always=True)
    def validate_sendgrid_settings(cls, v, values):
        """Validate SendGrid settings when provider is sendgrid."""
        if values.get("provider") == "sendgrid" and not v:
            raise ValueError("SENDGRID_API_KEY is required when EMAIL_PROVIDER=sendgrid")
        return v

    @validator("smtp_host", pre=True, always=True)
    def validate_smtp_settings(cls, v, values):
        """Validate SMTP settings when provider is smtp."""
        if values.get("provider") == "smtp" and not v:
            raise ValueError("SMTP_HOST is required when EMAIL_PROVIDER=smtp")
        return v

    class Config:
        env_prefix = "EMAIL_"


class CacheSettings(BaseSettings):
    """Cache and Redis settings."""

    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    redis_db: int = Field(0, env="REDIS_DB")

    class Config:
        env_prefix = "CACHE_"


class TaskQueueSettings(BaseSettings):
    """Background task queue settings."""

    celery_broker_url: Optional[str] = Field(None, env="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(None, env="CELERY_RESULT_BACKEND")

    class Config:
        env_prefix = "TASK_QUEUE_"


class WebRTCSettings(BaseSettings):
    """WebRTC and calling settings."""

    turn_server_url: Optional[str] = Field(None, env="TURN_SERVER_URL")
    turn_server_username: Optional[str] = Field(None, env="TURN_SERVER_USERNAME")
    turn_server_credential: Optional[SecretStr] = Field(None, env="TURN_SERVER_CREDENTIAL")

    class Config:
        env_prefix = "WEBRTC_"


class DeploymentSettings(BaseSettings):
    """Deployment and environment settings."""

    environment: str = Field("development", env="ENVIRONMENT")
    cors_origins: List[str] = Field(["*"], env="CORS_ORIGINS")
    debug: bool = Field(False, env="DEBUG")

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle comma-separated string or eval'd list
            if v.startswith("[") and v.endswith("]"):
                # It's a string representation of a list
                import ast
                return ast.literal_eval(v)
            else:
                # Comma-separated values
                return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_prefix = "DEPLOYMENT_"


class Settings(BaseSettings):
    """Main settings class that combines all configuration sections."""

    # Sub-settings (lazy loaded)
    database_url: str = Field(..., env="DATABASE_URL")
    secret_key: str = Field(..., env="SECRET_KEY", min_length=32)

    # OAuth settings (optional)
    google_client_id: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[SecretStr] = Field(None, env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(None, env="GOOGLE_REDIRECT_URI")
    mobile_app_scheme: str = Field("enterprisemessaging", env="MOBILE_APP_SCHEME")

    # Email settings
    email_provider: Literal["resend", "sendgrid", "smtp", "console"] = Field("resend", env="EMAIL_PROVIDER")
    frontend_url: str = Field("http://localhost:3000", env="FRONTEND_URL")
    resend_api_key: Optional[SecretStr] = Field(None, env="RESEND_API_KEY")
    resend_from_email: str = Field("onboarding@resend.dev", env="RESEND_FROM_EMAIL")
    resend_from_name: str = Field("Your App", env="RESEND_FROM_NAME")
    sendgrid_api_key: Optional[SecretStr] = Field(None, env="SENDGRID_API_KEY")
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(None, env="SMTP_USERNAME")
    smtp_password: Optional[SecretStr] = Field(None, env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, env="SMTP_USE_TLS")

    # Cache settings
    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    redis_db: int = Field(0, env="REDIS_DB")

    # Task queue settings
    celery_broker_url: Optional[str] = Field(None, env="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(None, env="CELERY_RESULT_BACKEND")

    # WebRTC settings
    turn_server_url: Optional[str] = Field(None, env="TURN_SERVER_URL")
    turn_server_username: Optional[str] = Field(None, env="TURN_SERVER_USERNAME")
    turn_server_credential: Optional[SecretStr] = Field(None, env="TURN_SERVER_CREDENTIAL")

    # Deployment settings
    environment: str = Field("development", env="ENVIRONMENT")
    cors_origins: List[str] = Field(["*"], env="CORS_ORIGINS")
    debug: bool = Field(False, env="DEBUG")

    # JWT settings
    algorithm: str = Field("HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(15, env="ACCESS_TOKEN_EXPIRE_MINUTES", ge=1)
    refresh_token_expire_days: int = Field(7, env="REFRESH_TOKEN_EXPIRE_DAYS", ge=1)
    verification_token_expire_hours: int = Field(24, env="VERIFICATION_TOKEN_EXPIRE_HOURS", ge=1)

    @validator("database_url")
    def fix_postgresql_protocol(cls, v):
        """Convert postgresql:// to postgresql+asyncpg:// for async driver."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle comma-separated string or eval'd list
            if v.startswith("[") and v.endswith("]"):
                # It's a string representation of a list
                import ast
                return ast.literal_eval(v)
            else:
                # Comma-separated values
                return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        # Load .env file explicitly
        from dotenv import load_dotenv
        load_dotenv()
        super().__init__(**kwargs)

        # Load from YAML config file if it exists
        config_path = Path(".") / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f) or {}
                # Update settings from YAML (environment variables take precedence)
                for key, value in yaml_config.items():
                    if hasattr(self, key) and not os.getenv(key.upper()):
                        setattr(self, key, value)

    @property
    def database(self) -> DatabaseSettings:
        """Nested database settings for backward compatibility."""
        return DatabaseSettings(
            url=self.database_url,
            url_async=getattr(self, "database_url_async", None),
        )

    @property
    def security(self) -> SecuritySettings:
        """Nested security settings for backward compatibility."""
        return SecuritySettings(
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            refresh_token_expire_days=self.refresh_token_expire_days,
            verification_token_expire_hours=self.verification_token_expire_hours,
        )

    @property
    def oauth(self) -> Optional[OAuthSettings]:
        """Nested OAuth settings for backward compatibility."""
        if not (self.google_client_id or self.google_client_secret or self.google_redirect_uri):
            return None
        return OAuthSettings(
            google_client_id=self.google_client_id,
            google_client_secret=self.google_client_secret,
            google_redirect_uri=self.google_redirect_uri,
            mobile_app_scheme=self.mobile_app_scheme,
        )

    @property
    def email(self) -> EmailSettings:
        """Nested email settings for backward compatibility."""
        return EmailSettings(
            provider=self.email_provider,
            frontend_url=self.frontend_url,
            resend_api_key=self.resend_api_key,
            resend_from_email=self.resend_from_email,
            resend_from_name=self.resend_from_name,
            sendgrid_api_key=self.sendgrid_api_key,
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            smtp_username=self.smtp_username,
            smtp_password=self.smtp_password,
            smtp_use_tls=self.smtp_use_tls,
        )

    @property
    def cache(self) -> CacheSettings:
        """Nested cache settings for backward compatibility."""
        return CacheSettings(
            redis_url=self.redis_url,
            redis_db=self.redis_db,
        )

    @property
    def task_queue(self) -> TaskQueueSettings:
        """Nested task queue settings for backward compatibility."""
        return TaskQueueSettings(
            celery_broker_url=self.celery_broker_url,
            celery_result_backend=self.celery_result_backend,
        )

    @property
    def webrtc(self) -> WebRTCSettings:
        """Nested WebRTC settings for backward compatibility."""
        return WebRTCSettings(
            turn_server_url=self.turn_server_url,
            turn_server_username=self.turn_server_username,
            turn_server_credential=self.turn_server_credential,
        )

    @property
    def deployment(self) -> DeploymentSettings:
        """Nested deployment settings for backward compatibility."""
        return DeploymentSettings(
            environment=self.environment,
            cors_origins=self.cors_origins,
            debug=self.debug,
        )

    def validate_configuration(self) -> List[str]:
        """
        Validate the complete configuration and return any issues.

        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []

        # Check database
        if not self.database_url:
            issues.append("DATABASE_URL is required")

        # Check security
        if len(self.secret_key) < 32:
            issues.append("SECRET_KEY must be at least 32 characters long")

        # Check OAuth (optional but if configured, must be complete)
        if self.google_client_id or self.google_client_secret or self.google_redirect_uri:
            if not self.google_client_id:
                issues.append("GOOGLE_CLIENT_ID is required when OAuth is configured")
            if not self.google_client_secret:
                issues.append("GOOGLE_CLIENT_SECRET is required when OAuth is configured")
            if not self.google_redirect_uri:
                issues.append("GOOGLE_REDIRECT_URI is required when OAuth is configured")

        # Check email provider configuration
        if self.email_provider == "resend" and not self.resend_api_key:
            issues.append("RESEND_API_KEY is required when EMAIL_PROVIDER=resend")
        elif self.email_provider == "sendgrid" and not self.sendgrid_api_key:
            issues.append("SENDGRID_API_KEY is required when EMAIL_PROVIDER=sendgrid")
        elif self.email_provider == "smtp" and not self.smtp_host:
            issues.append("SMTP_HOST is required when EMAIL_PROVIDER=smtp")

        return issues


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency function to get settings (for FastAPI dependency injection)."""
    return settings
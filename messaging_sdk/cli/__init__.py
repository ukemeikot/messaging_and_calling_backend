"""
CLI tooling for the messaging SDK.

The CLI is intentionally self-contained so the scaffold command can run before a
project has any application configuration in place.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click


def _load_settings():
    """Import settings lazily so `init` works without an existing .env file."""
    from messaging_sdk.core.config import settings

    return settings


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Messaging & Calling SDK CLI."""


@cli.command()
@click.option("--project-name", required=True, help="Name of the new project")
@click.option(
    "--template",
    default="basic",
    type=click.Choice(["basic", "full"]),
    show_default=True,
    help="Project template to generate",
)
def init(project_name: str, template: str):
    """Initialize a new FastAPI project scaffold."""
    project_dir = Path(project_name)
    if project_dir.exists():
        raise click.ClickException(f"Directory '{project_name}' already exists.")

    click.echo(f"Initializing project scaffold in {project_dir}")
    project_dir.mkdir(parents=True)

    _create_basic_structure(project_dir, project_name)
    if template == "full":
        _create_full_template(project_dir, project_name)

    click.echo("Project scaffold created successfully.")
    click.echo(f"Location: {project_dir.resolve()}")
    click.echo("Next steps:")
    click.echo(f"  1. cd {project_name}")
    click.echo("  2. Copy .env.example to .env and fill in real values")
    click.echo("  3. Run alembic upgrade head")
    click.echo("  4. Start the app with uvicorn main:app --reload")


def _create_basic_structure(project_dir: Path, project_name: str):
    """Create the base project scaffold."""
    for directory in [
        project_dir / "app",
        project_dir / "app" / "email_templates",
        project_dir / "uploads",
        project_dir / "uploads" / "profile_pictures",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    secret_key = os.urandom(32).hex()

    env_content = f"""# {project_name} environment configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/{project_name}
SECRET_KEY={secret_key}
EMAIL_PROVIDER=console
FRONTEND_URL=http://localhost:3000
EMAIL_TEMPLATE_DIR=app/email_templates
EMAIL_THEME_APP_NAME={project_name}
EMAIL_THEME_PRIMARY_COLOR=#1d4ed8
EMAIL_THEME_ACCENT_COLOR=#0f172a
EMAIL_THEME_SUPPORT_EMAIL=support@example.com
EMAIL_THEME_FOOTER_TEXT=Sent by {project_name}
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
ENVIRONMENT=development
DEBUG=false
CORS_ORIGINS=["http://localhost:3000"]
"""
    (project_dir / ".env.example").write_text(env_content, encoding="utf-8")

    main_content = f'''"""
Application entrypoint for {project_name}.
"""

from messaging_sdk import MessagingApp
from messaging_sdk.core.config import Settings
from messaging_sdk.emailing import EmailCustomization

from app.email_hooks import AFTER_RENDER_HOOK, BEFORE_RENDER_HOOK, LINK_BUILDERS
from app.email_theme import EMAIL_THEME

settings = Settings()
email_customization = EmailCustomization(
    template_dir=settings.email_template_dir or "app/email_templates",
    theme=EMAIL_THEME,
    link_builders=LINK_BUILDERS,
    before_render=BEFORE_RENDER_HOOK,
    after_render=AFTER_RENDER_HOOK,
)

app = MessagingApp(
    settings=settings,
    title="{project_name}",
    email_customization=email_customization,
)
'''
    (project_dir / "main.py").write_text(main_content, encoding="utf-8")

    (project_dir / "app" / "__init__.py").write_text(
        '"""Application package for scaffolded customizations."""\n',
        encoding="utf-8",
    )
    (project_dir / "app" / "email_theme.py").write_text(
        f'''"""
Shared email theme values for {project_name}.
"""

from messaging_sdk.emailing import EmailTheme


EMAIL_THEME = EmailTheme(
    app_name="{project_name}",
    primary_color="#1d4ed8",
    accent_color="#0f172a",
    support_email="support@example.com",
    footer_text="Sent by {project_name}",
)
''',
        encoding="utf-8",
    )
    (project_dir / "app" / "email_hooks.py").write_text(
        '''"""
Optional email hooks for advanced customization.
"""

from messaging_sdk.emailing import EmailMessage, EmailTemplateContext


def before_render(context: EmailTemplateContext):
    """Mutate context before the templates are rendered."""
    return context


def after_render(message: EmailMessage, context: EmailTemplateContext):
    """Mutate the rendered message before provider delivery."""
    return message


def build_password_reset_link(context: EmailTemplateContext) -> str:
    token = context.tokens["reset_token"]
    return f"{context.app['frontend_url']}/reset-password?token={token}"


LINK_BUILDERS = {
    "password_reset": build_password_reset_link,
}

BEFORE_RENDER_HOOK = before_render
AFTER_RENDER_HOOK = after_render
''',
        encoding="utf-8",
    )
    _create_email_templates(project_dir / "app" / "email_templates")

    readme_content = f"""# {project_name}

FastAPI application scaffold generated by the Messaging & Calling SDK CLI.

## Quick Start

1. Create a virtual environment and install your dependencies.
2. Copy `.env.example` to `.env`.
3. Run `alembic upgrade head`.
4. Start the app with `uvicorn main:app --reload`.
"""
    (project_dir / "README.md").write_text(readme_content, encoding="utf-8")


def _create_email_templates(template_dir: Path):
    """Create editable email templates in the scaffold."""
    (template_dir / "_partials").mkdir(parents=True, exist_ok=True)
    templates: dict[str, str] = {
        "base.html": """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>{{ data.subject }}</title>
  </head>
  <body style=\"margin:0; padding:0; background:#f8fafc; color:#0f172a; font-family:Segoe UI, Arial, sans-serif;\">
    <div style=\"max-width:640px; margin:0 auto; padding:32px 16px;\">
      <div style=\"background:#ffffff; border:1px solid #e2e8f0; border-radius:20px; overflow:hidden;\">
        <div style=\"padding:28px 32px; background:linear-gradient(135deg, {{ theme.primary_color }}, {{ theme.accent_color }}); color:#ffffff;\">
          <p style=\"margin:0; font-size:12px; letter-spacing:0.18em; text-transform:uppercase; opacity:0.85;\">{{ app.name }}</p>
          <h1 style=\"margin:14px 0 0; font-size:28px; line-height:1.2;\">{{ data.headline }}</h1>
        </div>
        <div style=\"padding:32px;\">
          {% block content %}{% endblock %}
        </div>
      </div>
    </div>
  </body>
</html>
""",
        "_partials/button.html": """<a href=\"{{ url }}\" style=\"display:inline-block; background:{{ theme.primary_color }}; color:#ffffff; padding:14px 20px; border-radius:999px; text-decoration:none; font-weight:600;\">{{ label }}</a>
""",
        "_partials/footer.html": """<div style=\"margin-top:28px; padding-top:18px; border-top:1px solid #e2e8f0; color:#475569; font-size:14px; line-height:1.6;\">
  {% if theme.support_email %}<p style=\"margin:0 0 8px;\">Need help? Reply to <a href=\"mailto:{{ theme.support_email }}\" style=\"color:{{ theme.primary_color }};\">{{ theme.support_email }}</a>.</p>{% endif %}
  {% if theme.footer_text %}<p style=\"margin:0;\">{{ theme.footer_text }}</p>{% endif %}
</div>
""",
        "verify_email.html": """{% extends \"base.html\" %}

{% block content %}
<p style=\"margin:0 0 16px; color:#334155; font-size:16px; line-height:1.7;\">Hi{% if user.username %} {{ user.username }}{% endif %},</p>
<p style=\"margin:0 0 24px; color:#334155; font-size:16px; line-height:1.7;\">{{ data.intro_text }}</p>
<p style=\"margin:0 0 24px;\">{% with url=links.action_url, label=data.action_label %}{% include \"_partials/button.html\" %}{% endwith %}</p>
<p style=\"margin:0 0 12px; color:#475569; font-size:14px; line-height:1.7;\">If the button does not work, use this link:</p>
<p style=\"margin:0 0 16px; font-size:14px; word-break:break-word;\"><a href=\"{{ links.action_url }}\" style=\"color:{{ theme.primary_color }};\">{{ links.action_url }}</a></p>
<p style=\"margin:0; color:#475569; font-size:14px; line-height:1.7;\">{{ data.expiry_text }}</p>
<p style=\"margin:12px 0 0; color:#475569; font-size:14px; line-height:1.7;\">{{ data.ignore_text }}</p>
{% include \"_partials/footer.html\" %}
{% endblock %}
""",
        "verify_email.txt": """Hi{% if user.username %} {{ user.username }}{% endif %},

{{ data.intro_text }}

{{ data.action_label }}: {{ links.action_url }}

{{ data.expiry_text }}
{{ data.ignore_text }}
""",
        "password_reset.html": """{% extends \"base.html\" %}

{% block content %}
<p style=\"margin:0 0 16px; color:#334155; font-size:16px; line-height:1.7;\">Hi{% if user.username %} {{ user.username }}{% endif %},</p>
<p style=\"margin:0 0 24px; color:#334155; font-size:16px; line-height:1.7;\">{{ data.intro_text }}</p>
<p style=\"margin:0 0 24px;\">{% with url=links.action_url, label=data.action_label %}{% include \"_partials/button.html\" %}{% endwith %}</p>
<p style=\"margin:0 0 12px; color:#475569; font-size:14px; line-height:1.7;\">If the button does not work, use this link:</p>
<p style=\"margin:0 0 16px; font-size:14px; word-break:break-word;\"><a href=\"{{ links.action_url }}\" style=\"color:{{ theme.primary_color }};\">{{ links.action_url }}</a></p>
<p style=\"margin:0; color:#475569; font-size:14px; line-height:1.7;\">{{ data.expiry_text }}</p>
<p style=\"margin:12px 0 0; color:#475569; font-size:14px; line-height:1.7;\">{{ data.ignore_text }}</p>
{% include \"_partials/footer.html\" %}
{% endblock %}
""",
        "password_reset.txt": """Hi{% if user.username %} {{ user.username }}{% endif %},

{{ data.intro_text }}

{{ data.action_label }}: {{ links.action_url }}

{{ data.expiry_text }}
{{ data.ignore_text }}
""",
    }
    for relative_path, content in templates.items():
        (template_dir / relative_path).write_text(content, encoding="utf-8")


def _create_full_template(project_dir: Path, project_name: str):
    """Create the extended scaffold with container files."""
    docker_compose = f"""version: "3.8"

services:
  api:
    build: .
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - .:/app
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: {project_name}
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
"""
    (project_dir / "docker-compose.yml").write_text(docker_compose, encoding="utf-8")

    dockerfile = """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    (project_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")


@cli.command("db")
@click.option("--check-config", is_flag=True, help="Validate configuration first")
def db_command(check_config: bool):
    """Run database migrations for the current project."""
    settings = _load_settings()

    if check_config:
        issues = settings.validate_configuration()
        if issues:
            for issue in issues:
                click.echo(f"- {issue}")
            raise click.ClickException("Configuration validation failed.")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "Migration failed.")

    click.echo("Database migrations completed successfully.")


@cli.command()
def config():
    """Show configuration summary for the current project."""
    settings = _load_settings()

    click.echo("Configuration summary")
    click.echo(f"  Environment: {settings.environment}")
    click.echo(f"  Database: {settings.database_url}")
    click.echo(f"  Email provider: {settings.email_provider}")
    click.echo(f"  Debug: {settings.debug}")

    issues = settings.validate_configuration()
    if issues:
        click.echo("Validation issues:")
        for issue in issues:
            click.echo(f"  - {issue}")
    else:
        click.echo("Configuration is valid.")


__all__ = ["cli"]

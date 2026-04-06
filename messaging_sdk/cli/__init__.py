"""
CLI tool for Messaging & Calling SDK.

Provides commands for:
- Initializing new projects
- Database migrations
- Configuration validation
- Development utilities

Usage:
    messaging-sdk init --project-name myapp
    messaging-sdk db migrate
    messaging-sdk config test
"""

import os
import sys
from pathlib import Path
from typing import Optional
import click
import subprocess
import shutil

from messaging_sdk.core.config import settings


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Messaging & Calling SDK CLI tool."""
    pass


@cli.command()
@click.option("--project-name", required=True, help="Name of the new project")
@click.option("--template", default="basic", type=click.Choice(["basic", "full"]), help="Project template to use")
def init(project_name: str, template: str):
    """Initialize a new messaging project."""
    click.echo(f"Initializing new project: {project_name}")

    # Create project directory
    project_dir = Path(project_name)
    if project_dir.exists():
        click.echo(f"❌ Directory {project_name} already exists!", err=True)
        return

    project_dir.mkdir()
    os.chdir(project_dir)

    # Create basic project structure
    _create_basic_structure(project_name)

    if template == "full":
        _create_full_template(project_name)

    click.echo("✅ Project initialized successfully!"    click.echo(f"📁 Created project in: {project_dir.absolute()}")
    click.echo("🚀 Next steps:"
    click.echo("   1. cd {project_name}")
    click.echo("   2. Edit .env file with your configuration")
    click.echo("   3. Run: messaging-sdk db migrate"
    click.echo("   4. Run: uvicorn main:app --reload"


def _create_basic_structure(project_name: str):
    """Create basic project structure."""
    # Create directories
    dirs = ["app", "uploads", "uploads/profile_pictures"]
    for dir_name in dirs:
        Path(dir_name).mkdir(parents=True, exist_ok=True)

    # Create .env file
    env_content = f"""# {project_name} - Environment Configuration
# Copy this file to .env and fill in your values

# ========================================
# REQUIRED SETTINGS
# ========================================

# Database (choose one)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/{project_name}
# DATABASE_URL_ASYNC=postgresql+asyncpg://user:password@localhost:5432/{project_name}

# Security
SECRET_KEY={os.urandom(32).hex()}

# ========================================
# AUTHENTICATION (Google OAuth)
# ========================================

GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# ========================================
# EMAIL CONFIGURATION (choose one provider)
# ========================================

# Option 1: Resend (recommended for development)
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_resend_api_key_here
FRONTEND_URL=http://localhost:3000

# Option 2: SendGrid
# EMAIL_PROVIDER=sendgrid
# SENDGRID_API_KEY=SG.your_sendgrid_api_key_here

# Option 3: SMTP
# EMAIL_PROVIDER=smtp
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your-email@gmail.com
# SMTP_PASSWORD=your-app-password

# ========================================
# OPTIONAL: SCALING & PRODUCTION
# ========================================

# Redis (optional, enables caching and scaling)
# REDIS_URL=redis://localhost:6379/0

# Celery (optional, enables background task processing)
# CELERY_BROKER_URL=redis://localhost:6379/1
# CELERY_RESULT_BACKEND=redis://localhost:6379/2

# WebRTC (optional, for corporate networks)
# TURN_SERVER_URL=turn:your-turn-server.com:3478
# TURN_SERVER_USERNAME=your-username
# TURN_SERVER_CREDENTIAL=your-credential

# ========================================
# DEPLOYMENT
# ========================================

ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:3000"]
"""
    Path(".env.example").write_text(env_content)

    # Create main.py
    main_content = f'''"""
Main application file for {project_name}.

This file demonstrates how to use the Messaging & Calling SDK.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from messaging_sdk import MessagingApp
from messaging_sdk.core.config import settings

# Validate configuration
issues = settings.validate_configuration()
if issues:
    print("❌ Configuration issues found:")
    for issue in issues:
        print(f"   - {{issue}}")
    print("\\nPlease check your .env file and fix the issues above.")
    exit(1)

# Create FastAPI app using the SDK
app = MessagingApp(settings=settings)

# Add any custom routes or middleware here
# app.include_router(your_custom_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
'''
    Path("main.py").write_text(main_content)

    # Create requirements.txt
    requirements = """fastapi==0.124.4
uvicorn[standard]==0.38.0
messaging-calling-sdk==1.0.0
python-dotenv==1.2.1
"""
    Path("requirements.txt").write_text(requirements)

    # Create README.md
    readme_content = f"""# {project_name}

A messaging and calling application built with the Messaging & Calling SDK.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run database migrations:**
   ```bash
   messaging-sdk db migrate
   ```

4. **Start the server:**
   ```bash
   python main.py
   ```

The API will be available at: http://localhost:8000
API documentation: http://localhost:8000/docs

## Features

- ✅ User authentication (JWT + Google OAuth)
- ✅ Real-time messaging (1-on-1 and group chats)
- ✅ Voice and video calling (WebRTC)
- ✅ Contact management
- ✅ Full-text search
- ✅ Email notifications
- ✅ File uploads

## Configuration

See `.env.example` for all available configuration options.

## SDK Documentation

For more information about the Messaging & Calling SDK, visit:
https://github.com/yourorg/messaging-calling-sdk
"""
    Path("README.md").write_text(readme_content)


def _create_full_template(project_name: str):
    """Create additional files for full template."""
    # Create docker-compose.yml
    docker_compose = f"""version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:password@db:5432/{project_name}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/app/uploads
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: {project_name}
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
"""
    Path("docker-compose.yml").write_text(docker_compose)

    # Create Dockerfile
    dockerfile = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads/profile_pictures

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    Path("Dockerfile").write_text(dockerfile)


@cli.command()
@click.option("--check-config", is_flag=True, help="Validate configuration before migrating")
def db(check_config: bool):
    """Database management commands."""
    if check_config:
        click.echo("🔍 Validating configuration...")
        issues = settings.validate_configuration()
        if issues:
            click.echo("❌ Configuration issues found:")
            for issue in issues:
                click.echo(f"   - {issue}")
            click.echo("\\nPlease fix these issues before proceeding.")
            return

        click.echo("✅ Configuration is valid!")

    # Run alembic migrations
    try:
        click.echo("🗄️ Running database migrations...")
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd=".")

        if result.returncode == 0:
            click.echo("✅ Database migrations completed successfully!")
        else:
            click.echo("❌ Database migration failed:")
            click.echo(result.stderr)

    except FileNotFoundError:
        click.echo("❌ Alembic not found. Make sure the Messaging SDK is properly installed.")
    except Exception as e:
        click.echo(f"❌ Error running migrations: {e}")


@cli.command()
def config():
    """Configuration management commands."""
    click.echo("🔧 Configuration Status:")
    click.echo(f"   Environment: {settings.deployment.environment}")
    click.echo(f"   Database: {'✅ Configured' if settings.database.url else '❌ Not configured'}")
    click.echo(f"   Email: {settings.email.provider} ({'✅ Configured' if _is_email_configured() else '❌ Not configured'})")
    click.echo(f"   Cache: {'Redis' if settings.cache.redis_url else 'In-memory'}")
    click.echo(f"   Tasks: {'Celery' if settings.task_queue.celery_broker_url else 'FastAPI BackgroundTasks'}")

    issues = settings.validate_configuration()
    if issues:
        click.echo("\\n⚠️ Configuration Issues:")
        for issue in issues:
            click.echo(f"   - {issue}")
    else:
        click.echo("\\n✅ Configuration is valid!")


def _is_email_configured() -> bool:
    """Check if email is properly configured."""
    email_config = settings.email
    if email_config.provider == "resend":
        return bool(email_config.resend_api_key)
    elif email_config.provider == "sendgrid":
        return bool(email_config.sendgrid_api_key)
    elif email_config.provider == "smtp":
        return bool(email_config.smtp_host)
    return False


if __name__ == "__main__":
    cli()
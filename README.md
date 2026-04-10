# Messaging and Calling Backend

Messaging and Calling Backend is a FastAPI-based SDK source tree for teams that
want authentication, contacts, chat, calling, WebSocket signaling, search, and
profile management without assembling the whole backend from scratch.

This repository now supports both source integration and GitHub-based Python
package installation for your own FastAPI project. It includes the API surface,
service layer, CLI scaffold, tests, a static documentation website, release
automation, and security notes needed to start building on top of it.

## Documentation map

- [FEATURES.md](./FEATURES.md): feature inventory and implementation schema
- [CONTRIBUTING.md](./CONTRIBUTING.md): contributor workflow and documentation expectations
- [SECURITY.md](./SECURITY.md): current security posture and remaining hardening gaps
- [CHANGELOG.md](./CHANGELOG.md): release-facing summary of changes
- [DEPLOYMENT.md](./DEPLOYMENT.md): branch promotion, GitHub package installs, and website hosting
- [website/](./website/README.md): static docs and project website

## Built-in SDK features

- JWT registration, login, and authenticated current-user lookup
- Email verification and password reset flows
- Google OAuth for web and mobile handoff flows
- Customizable email composition with built-in templates, theme values, and hooks
- Profile retrieval, update, password change, profile picture upload, and account deletion
- Contact requests, acceptance, blocking, and relationship-aware messaging rules
- Direct conversations and group chat management
- Message send, edit, soft delete, read tracking, and messaging WebSocket events
- Voice and video call lifecycle APIs plus signaling WebSockets
- PostgreSQL-backed global, user, message, and conversation search
- Source CLI scaffolding for FastAPI projects

For the full implementation map, see [FEATURES.md](./FEATURES.md).

## Current caveats

- PostgreSQL is the intended runtime database. SQLite is only used in tests.
- Search features rely on PostgreSQL operators and indexes and are not portable to SQLite.
- Packaging metadata now exists for installation, and the recommended distribution path right now is GitHub install URLs rather than PyPI.
- Before public deployment, read [SECURITY.md](./SECURITY.md).

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Set `EMAIL_PROVIDER=console` for local development if you do not want to send real emails.
5. Run database migrations.
6. Start the API.

```bash
python -m venv .venv

# PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn messaging_sdk.main:app --reload
```

Open `http://localhost:8000/docs` for the generated OpenAPI docs.

## Minimal configuration

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/messaging_db
SECRET_KEY=replace-this-with-a-long-random-secret-key
EMAIL_PROVIDER=console
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
DEBUG=false
CORS_ORIGINS=["http://localhost:3000"]
```

Useful email customization variables:

```env
EMAIL_TEMPLATE_DIR=app/email_templates
EMAIL_THEME_APP_NAME=Messaging Platform
EMAIL_THEME_PRIMARY_COLOR=#1d4ed8
EMAIL_THEME_ACCENT_COLOR=#0f172a
EMAIL_THEME_SUPPORT_EMAIL=support@example.com
EMAIL_THEME_FOOTER_TEXT=Sent by Messaging Platform
```

## How to use the SDK

### 1. Install it into your project from GitHub

```bash
pip install "git+https://github.com/ukemeikot/messaging-and-calling-backend.git@main#subdirectory=messaging_and_calling_backend"
messaging-sdk config
```

For a local editable install while developing inside this repository:

```bash
pip install -e .
```

### 2. Mount it directly in a FastAPI app

```python
from messaging_sdk import MessagingApp
from messaging_sdk.core.config import Settings

settings = Settings()
app = MessagingApp(settings=settings, title="My Product Messaging API")
```

This gives you the built-in routers, middleware, static upload mount, and
startup table creation behavior.

### 3. Scaffold a starter project

```bash
python -m messaging_sdk.cli init --project-name my_app
python -m messaging_sdk.cli init --project-name my_app --template full
```

Useful CLI commands:

```bash
python -m messaging_sdk.cli config
python -m messaging_sdk.cli db --check-config
```

The scaffold now includes:

- `app/email_templates/` for editable email templates
- `app/email_theme.py` for shared email branding values
- `app/email_hooks.py` for advanced link and render hooks

### 4. Customize built-in email behavior

The SDK supports three levels of email customization:

- packaged defaults in `messaging_sdk/email_templates/`
- file-based overrides through `EMAIL_TEMPLATE_DIR`
- programmatic hooks with `EmailCustomization`

Example:

```python
from messaging_sdk import MessagingApp
from messaging_sdk.core.config import Settings
from messaging_sdk.emailing import EmailCustomization, EmailTheme


def build_password_reset_link(context):
    token = context.tokens["reset_token"]
    return f"https://accounts.example.com/reset/{token}"


settings = Settings()
email_customization = EmailCustomization(
    template_dir=settings.email_template_dir,
    theme=EmailTheme(
        app_name="Acme Chat",
        primary_color="#2563eb",
        accent_color="#111827",
        support_email="support@acme.test",
        footer_text="Sent by Acme Chat",
    ),
    link_builders={"password_reset": build_password_reset_link},
)

app = MessagingApp(
    settings=settings,
    title="Acme Messaging API",
    email_customization=email_customization,
)
```

## Feature usage guide

### Authentication and identity

- `/api/v1/auth/register`: create a local account
- `/api/v1/auth/login`: obtain JWT tokens
- `/api/v1/auth/me`: fetch the authenticated user
- `/api/v1/auth/resend-verification` and `/api/v1/auth/verify-email`: email verification flow
- `/api/v1/auth/forgot-password` and `/api/v1/auth/reset-password`: password reset flow
- `/api/v1/auth/google/*`: Google OAuth web and mobile flows

### Profile management

- `/api/v1/profile`: get and update the current profile
- `/api/v1/profile/password`: change password
- `/api/v1/profile/picture`: upload a validated image file
- `/api/v1/profile/{user_id}`: view the public profile for another user
- `DELETE /api/v1/profile`: delete the authenticated account

### Contacts and messaging

- Contacts must be accepted before direct conversations can be created
- Group chats support participant add/remove, admin promotion, and admin-only member settings
- Messaging supports send, edit, delete, read receipts, and typing events over WebSocket
- Conversation access is membership-protected at the service layer and WebSocket flow

### Calling and signaling

- Call APIs support initiating, answering, declining, ending, inviting, and history lookup
- Signaling WebSocket access is validated against real call participation
- Group and 1-on-1 calls share the same service layer with participant records

### Search

- User, message, conversation, and global search are available
- Search is PostgreSQL-specific today because it depends on full-text and similarity operators

## Testing

Run the full repository test suite with:

```bash
pytest
```

The suite currently covers:

- auth and security helpers
- user, contact, chat, and call services
- email composition and scaffold generation
- app initialization behavior

## Release process

This repository includes GitHub Actions automation for CI, promotion checks, deployment, and release drafting:

- PRs are enforced through `feature/*` -> `develop` -> `main`
- pushes and pull requests across protected branches run `pytest`
- merges to `main` update `CHANGELOG.md`, refresh draft release notes, and deploy the docs website
- version tags such as `v0.1.0` publish a GitHub release

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full operational guide.

## Documentation website

The repository includes a static project site under
[`website/`](./website/README.md).

Preview it locally with:

```bash
python -m http.server 8080 --directory website
```

Then open `http://127.0.0.1:8080`.

For production hosting, the repository is wired to deploy the site from `main`
to GitHub Pages and serve it from `messagingandcallingbackend.credianlab.xyz`.

## Documentation policy

Documentation is part of the feature surface of this repository.

When a feature changes, update the relevant docs in the same change set:

- `README.md` for setup and usage changes
- `FEATURES.md` for capability inventory or architecture changes
- `SECURITY.md` for security-impacting behavior
- `CHANGELOG.md` for release-visible changes

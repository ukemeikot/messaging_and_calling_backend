import os
import shutil
import sys
import uuid
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test-bootstrap.db"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-123"
os.environ["EMAIL_PROVIDER"] = "console"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["GOOGLE_REDIRECT_URI"] = ""
os.environ["DEBUG"] = "false"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from messaging_sdk.database import Base
from messaging_sdk.emailing import configure_email_runtime
import messaging_sdk.models  # noqa: F401
from messaging_sdk.core.transient_store import (
    mobile_auth_code_store,
    rate_limiter,
    used_token_store,
)
from messaging_sdk.core.config import settings as app_settings
from messaging_sdk.models.contact import Contact, ContactStatus
from messaging_sdk.services.user_service import UserService

ARTIFACT_ROOT = ROOT / ".test-artifacts"
ARTIFACT_ROOT.mkdir(exist_ok=True)


@pytest.fixture
async def db_session():
    db_dir = ARTIFACT_ROOT / f"db-{uuid.uuid4().hex}"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()
    shutil.rmtree(db_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_transient_security_state():
    used_token_store.clear()
    mobile_auth_code_store.clear()
    rate_limiter.clear()
    configure_email_runtime(app_settings, None)
    yield
    used_token_store.clear()
    mobile_auth_code_store.clear()
    rate_limiter.clear()
    configure_email_runtime(app_settings, None)


@pytest.fixture
def user_factory(db_session):
    async def factory(
        username: str,
        email: str | None = None,
        password: str = "Password123!",
        full_name: str | None = None,
    ):
        service = UserService(db_session)
        return await service.create_user(
            username=username,
            email=email or f"{username}@example.com",
            password=password,
            full_name=full_name,
        )

    return factory


@pytest.fixture
def accepted_contact_factory(db_session):
    async def factory(user, other_user):
        contact = Contact(
            user_id=user.id,
            contact_user_id=other_user.id,
            status=ContactStatus.ACCEPTED,
        )
        db_session.add(contact)
        await db_session.commit()
        await db_session.refresh(contact)
        return contact

    return factory

from starlette.requests import Request

import pytest
from fastapi import BackgroundTasks, HTTPException

from messaging_sdk.api.v1.auth import (
    forgot_password,
    mobile_exchange_code,
    reset_password,
    verify_email,
)
from messaging_sdk.core.security import (
    create_password_reset_token,
    create_verification_token,
    hash_password,
)
from messaging_sdk.core.transient_store import mobile_auth_code_store
from messaging_sdk.schemas.user import (
    MobileCodeExchangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
)


def _make_request(
    path: str,
    method: str = "POST",
    client_ip: str = "127.0.0.1",
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_verify_email_token_is_single_use(db_session, user_factory):
    user = await user_factory("alice")
    token = create_verification_token(user.id, user.email)

    first_response = await verify_email(
        token,
        _make_request("/api/v1/auth/verify-email", method="GET"),
        db_session,
    )

    assert first_response["message"] == "Email verified successfully!"

    with pytest.raises(HTTPException) as exc:
        await verify_email(
            token,
            _make_request("/api/v1/auth/verify-email", method="GET"),
            db_session,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_token_is_single_use(db_session, user_factory):
    user = await user_factory("alice")
    token = create_password_reset_token(user.id, user.email, str(user.hashed_password))

    first_response = await reset_password(
        PasswordResetConfirm(token=token, new_password="EvenBetter123"),
        _make_request("/api/v1/auth/reset-password"),
        db_session,
    )

    assert "Password reset successfully" in first_response["message"]

    with pytest.raises(HTTPException) as exc:
        await reset_password(
            PasswordResetConfirm(token=token, new_password="AnotherPass123"),
            _make_request("/api/v1/auth/reset-password"),
            db_session,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_rejects_stale_password_state(db_session, user_factory):
    user = await user_factory("alice")
    token = create_password_reset_token(user.id, user.email, str(user.hashed_password))

    user.hashed_password = hash_password("ChangedBeforeUse123")
    await db_session.commit()
    await db_session.refresh(user)

    with pytest.raises(HTTPException) as exc:
        await reset_password(
            PasswordResetConfirm(token=token, new_password="AnotherPass123"),
            _make_request("/api/v1/auth/reset-password"),
            db_session,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_forgot_password_is_rate_limited_by_ip(db_session):
    request = _make_request("/api/v1/auth/forgot-password")

    for index in range(5):
        response = await forgot_password(
            PasswordResetRequest(email=f"user{index}@example.com"),
            request,
            BackgroundTasks(),
            db_session,
        )
        assert response["message"] == "Password reset email sent"

    with pytest.raises(HTTPException) as exc:
        await forgot_password(
            PasswordResetRequest(email="overflow@example.com"),
            request,
            BackgroundTasks(),
            db_session,
        )

    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_mobile_auth_code_exchange_is_single_use():
    code = "mobile-auth-code-12345"
    mobile_auth_code_store.put(
        code,
        {
            "message": "Authentication successful",
            "user": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "mobile_user",
                "email": "mobile@example.com",
                "full_name": None,
                "bio": None,
                "profile_picture_url": None,
                "is_active": True,
                "is_verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": None,
            },
            "tokens": {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "bearer",
                "expires_in": 900,
            },
            "is_new_user": False,
        },
        ttl_seconds=300,
    )

    response = await mobile_exchange_code(MobileCodeExchangeRequest(code=code))

    assert response.user.username == "mobile_user"
    assert response.tokens.access_token == "access"

    with pytest.raises(HTTPException) as exc:
        await mobile_exchange_code(MobileCodeExchangeRequest(code=code))

    assert exc.value.status_code == 400

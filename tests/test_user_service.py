import pytest

from messaging_sdk.services.user_service import UserService


@pytest.mark.asyncio
async def test_create_authenticate_and_search_users(db_session, user_factory):
    service = UserService(db_session)

    current_user = await user_factory("current", full_name="Current User")
    found_user = await user_factory("alice", full_name="Alice Example")
    inactive_user = await user_factory("disabled", full_name="Disabled User")
    inactive_user.is_active = False
    await db_session.commit()

    authenticated = await service.authenticate_user("alice@example.com", "Password123!")
    search_results = await service.search_users("ali", current_user.id)

    assert authenticated is not None
    assert authenticated.username == "alice"
    assert [user.username for user in search_results] == [found_user.username]
    assert inactive_user.username not in [user.username for user in search_results]


@pytest.mark.asyncio
async def test_create_user_normalizes_email_and_username(db_session):
    service = UserService(db_session)

    user = await service.create_user(
        username="MixedCase",
        email="MixedCase@Example.com",
        password="Password123!",
    )

    assert user.username == "mixedcase"
    assert user.email == "mixedcase@example.com"
    assert user.hashed_password != "Password123!"

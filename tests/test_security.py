import uuid

import pytest
from jose import JWTError

from messaging_sdk.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    decode_token,
    hash_password,
    password_reset_state_matches,
    verify_password,
    verify_password_reset_token,
    verify_verification_token,
)


def test_password_hash_round_trip():
    password = "Password123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True


def test_access_and_refresh_tokens_round_trip():
    payload = {"user_id": str(uuid.uuid4()), "username": "tester"}

    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    decoded_access = decode_token(access_token)
    decoded_refresh = decode_token(refresh_token)

    assert decoded_access["username"] == "tester"
    assert decoded_refresh["type"] == "refresh"


def test_verification_token_rejects_password_reset_token():
    user_id = uuid.uuid4()
    reset_token = create_password_reset_token(
        user_id,
        "person@example.com",
        "hashed-password-state",
    )

    with pytest.raises(JWTError):
        verify_verification_token(reset_token)


def test_password_reset_token_rejects_verification_token():
    user_id = uuid.uuid4()
    verification_token = create_verification_token(user_id, "person@example.com")

    with pytest.raises(JWTError):
        verify_password_reset_token(verification_token)


def test_password_reset_token_is_bound_to_current_password_state():
    user_id = uuid.uuid4()
    original_state = hash_password("Password123!")
    token = create_password_reset_token(user_id, "person@example.com", original_state)

    token_data = verify_password_reset_token(token)

    assert password_reset_state_matches(token_data["pwd"], original_state) is True
    assert password_reset_state_matches(token_data["pwd"], hash_password("Password123!")) is False

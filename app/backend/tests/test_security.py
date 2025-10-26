"""Test security utilities."""

import pytest

from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing() -> None:
    """Test password hashing and verification."""
    password = "mysecurepassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_password_hashing_long_password() -> None:
    """Test password hashing with long password (SHA256 preprocessing)."""
    # Password longer than 72 bytes
    long_password = "a" * 100
    hashed = hash_password(long_password)

    assert verify_password(long_password, hashed)
    assert not verify_password("a" * 99, hashed)


def test_create_and_decode_access_token() -> None:
    """Test JWT access token creation and decoding."""
    user_id = 123
    token = create_access_token(data={"sub": str(user_id)})

    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_and_decode_refresh_token() -> None:
    """Test JWT refresh token creation and decoding."""
    user_id = 456
    token = create_refresh_token(data={"sub": str(user_id)})

    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"
    assert "exp" in payload


def test_decode_invalid_token() -> None:
    """Test decoding invalid token raises error."""
    with pytest.raises(ValueError, match="Could not validate credentials"):
        decode_token("invalid.token.here")

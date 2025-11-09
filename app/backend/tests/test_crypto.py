"""
Tests for encryption utilities.

These tests verify that sensitive data (tokens, credentials) is properly encrypted
at rest and can be decrypted for use.
"""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from src.core.config import get_settings
from src.core.crypto import decrypt_token, encrypt_token, get_cipher

SECRET_TOKEN = "gAAAAABpD5z79YRnzW0lxRkvYHn21dfZSV4kh6w1KcC6nXM3rVWY3HoeVKeMZ-olvJ6y_ezK02mhUDV0LuMCdMMBL3z3V-nmIw=="


class TestEncryption:
    """Test encryption and decryption of sensitive data."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encryption and decryption are reversible."""
        original_token = "test_whatsapp_token_12345"

        encrypted = encrypt_token(original_token)

        assert encrypted != original_token

        assert encrypted.startswith("gAAAAA")

        decrypted = decrypt_token(encrypted)
        assert decrypted == original_token

    def test_encrypt_empty_string_raises_error(self) -> None:
        """Test that encrypting empty string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot encrypt empty token"):
            encrypt_token("")

    def test_decrypt_empty_string_raises_error(self) -> None:
        """Test that decrypting empty string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot decrypt empty token"):
            decrypt_token("")

    def test_decrypt_invalid_token_raises_error(self) -> None:
        """Test that decrypting invalid data raises ValueError."""
        with pytest.raises(ValueError, match="Failed to decrypt token"):
            decrypt_token("this_is_not_a_valid_fernet_token")

    def test_different_tokens_produce_different_ciphertext(self) -> None:
        """Test that different tokens produce different encrypted values."""
        token1 = "token_abc_123"
        token2 = "token_xyz_789"

        encrypted1 = encrypt_token(token1)
        encrypted2 = encrypt_token(token2)

        assert encrypted1 != encrypted2

        assert decrypt_token(encrypted1) == token1
        assert decrypt_token(encrypted2) == token2

    def test_same_token_produces_different_ciphertext(self) -> None:
        """Test that encrypting the same token twice produces different ciphertext.

        This is expected behavior with Fernet due to timestamp and random IV.
        """
        token = "same_token_12345"

        encrypted1 = encrypt_token(token)
        encrypted2 = encrypt_token(token)

        assert encrypted1 != encrypted2

        assert decrypt_token(encrypted1) == token
        assert decrypt_token(encrypted2) == token

    def test_cipher_is_cached(self) -> None:
        """Test that get_cipher() returns the same instance on multiple calls."""
        cipher1 = get_cipher()
        cipher2 = get_cipher()

        assert cipher1 is cipher2

    def test_missing_encryption_key_raises_error(self) -> None:
        """Test that missing ENCRYPTION_KEY in settings raises ValueError."""
        get_settings.cache_clear()
        get_cipher.cache_clear()

        with patch("src.core.crypto.get_settings") as mock_settings:
            mock_settings.return_value.ENCRYPTION_KEY.get_secret_value.return_value = None

            with pytest.raises(ValueError, match="ENCRYPTION_KEY must be configured"):
                get_cipher()

        get_settings.cache_clear()
        get_cipher.cache_clear()

    def test_invalid_encryption_key_raises_error(self) -> None:
        """Test that invalid ENCRYPTION_KEY format raises ValueError."""
        get_settings.cache_clear()
        get_cipher.cache_clear()

        with patch("src.core.crypto.get_settings") as mock_settings:
            mock_settings.return_value.ENCRYPTION_KEY.get_secret_value.return_value = (
                "invalid_key_format"
            )

            with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY format"):
                get_cipher()

        get_settings.cache_clear()
        get_cipher.cache_clear()

    def test_long_token_encryption(self) -> None:
        """Test encryption of long tokens (e.g., JWT tokens)."""
        long_token = "EAABsbCS1iHgBO" + "x" * 500

        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == long_token

    def test_special_characters_in_token(self) -> None:
        """Test encryption of tokens with special characters."""
        token_with_special_chars = "token-with_special.chars!@#$%^&*()"

        encrypted = encrypt_token(token_with_special_chars)
        decrypted = decrypt_token(encrypted)

        assert decrypted == token_with_special_chars

    def test_unicode_characters_in_token(self) -> None:
        """Test encryption of tokens with unicode characters."""
        token_with_unicode = "token_with_émojis_🔐_and_中文"

        encrypted = encrypt_token(token_with_unicode)
        decrypted = decrypt_token(encrypted)

        assert decrypted == token_with_unicode


class TestCipherKeyRotation:
    """Test scenarios related to encryption key rotation."""

    def test_decryption_fails_with_wrong_key(self) -> None:
        """Test that tokens encrypted with one key cannot be decrypted with another."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"ENCRYPTION_KEY": key1}):
            get_settings.cache_clear()
            get_cipher.cache_clear()
            encrypted = SECRET_TOKEN

        with patch.dict(os.environ, {"ENCRYPTION_KEY": key2}):
            get_settings.cache_clear()
            get_cipher.cache_clear()
            with pytest.raises(ValueError, match="Failed to decrypt token"):
                decrypt_token(encrypted)

        get_settings.cache_clear()
        get_cipher.cache_clear()

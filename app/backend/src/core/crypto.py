"""
Encryption utilities for sensitive data at rest.

Uses Fernet (symmetric encryption) to encrypt/decrypt tokens and credentials.
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from src.core.config import get_settings


@lru_cache(maxsize=1)
def get_cipher() -> Fernet:
    """
    Get cached Fernet cipher instance.

    The cipher is cached to avoid recreating it on every encryption/decryption operation.
    Uses ENCRYPTION_KEY from application settings.

    Returns:
        Fernet: Initialized cipher for encryption/decryption operations.

    Raises:
        ValueError: If ENCRYPTION_KEY is not configured or invalid.
    """
    settings = get_settings()
    encryption_key = settings.ENCRYPTION_KEY.get_secret_value()

    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY must be configured in environment variables")

    try:
        return Fernet(encryption_key.encode())
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for secure storage.

    Args:
        token: Plain text token to encrypt.

    Returns:
        str: Encrypted token as base64-encoded string suitable for database storage.

    Raises:
        ValueError: If token is empty or encryption fails.

    Example:
        >>> encrypted = encrypt_token("my_secret_token")
        >>> encrypted.startswith("gAAAAA")  # Fernet tokens start with this prefix
        True
    """
    if not token:
        raise ValueError("Cannot encrypt empty token")

    cipher = get_cipher()
    encrypted_bytes = cipher.encrypt(token.encode())
    return encrypted_bytes.decode()


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a token from storage.

    Args:
        encrypted_token: Encrypted token (base64-encoded Fernet token).

    Returns:
        str: Decrypted plain text token.

    Raises:
        ValueError: If encrypted_token is empty or decryption fails.

    Example:
        >>> encrypted = encrypt_token("my_secret_token")
        >>> decrypt_token(encrypted)
        'my_secret_token'
    """
    if not encrypted_token:
        raise ValueError("Cannot decrypt empty token")

    cipher = get_cipher()
    try:
        decrypted_bytes = cipher.decrypt(encrypted_token.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt token: {e}")

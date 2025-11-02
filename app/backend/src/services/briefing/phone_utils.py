"""Utilities for Brazilian phone number validation and normalization."""

import re
from typing import Literal


def normalize_phone(phone: str) -> str:
    """Normalize Brazilian phone number to format +55DDNNNNNNNNN.

    Args:
        phone: Phone number in any format (with or without formatting)

    Returns:
        Normalized phone in format +55DDNNNNNNNNN (e.g., +5511987654321)

    Examples:
        >>> normalize_phone("(11) 98765-4321")
        '+5511987654321'
        >>> normalize_phone("11 9 8765 4321")
        '+5511987654321'
        >>> normalize_phone("+55 11 98765-4321")
        '+5511987654321'
        >>> normalize_phone("5511987654321")
        '+5511987654321'
    """
    # Remove all non-digit characters
    digits_only = re.sub(r"\D", "", phone)

    # Add +55 if not present
    if not digits_only.startswith("55"):
        digits_only = "55" + digits_only

    # Ensure it starts with +
    if not digits_only.startswith("+"):
        digits_only = "+" + digits_only

    return digits_only


def validate_brazilian_phone(
    phone: str, allow_landline: bool = True
) -> tuple[bool, Literal["mobile", "landline", "invalid"] | None]:
    """Validate if a phone number is a valid Brazilian number.

    Args:
        phone: Phone number to validate (can be formatted or normalized)
        allow_landline: Whether to accept landline numbers (8 digits after DDD)

    Returns:
        Tuple of (is_valid, phone_type)
        - is_valid: True if valid Brazilian number
        - phone_type: "mobile", "landline", or None if invalid

    Examples:
        >>> validate_brazilian_phone("+5511987654321")
        (True, 'mobile')
        >>> validate_brazilian_phone("+551133334444")
        (True, 'landline')
        >>> validate_brazilian_phone("+5511888")
        (False, 'invalid')
    """
    # Normalize first
    normalized = normalize_phone(phone)

    # Remove +55 prefix for validation
    if not normalized.startswith("+55"):
        return False, "invalid"

    number = normalized[3:]  # Remove +55

    # Check if DDD is valid (11-99, excluding some invalid ranges)
    if len(number) < 10:
        return False, "invalid"

    ddd = number[:2]
    try:
        ddd_int = int(ddd)
    except ValueError:
        return False, "invalid"

    # Valid DDD ranges in Brazil: 11-99, but excluding some
    if not (11 <= ddd_int <= 99):
        return False, "invalid"

    remaining = number[2:]

    # Mobile: DDD + 9 + 8 digits = 11 digits total
    if len(remaining) == 9 and remaining[0] == "9":
        return True, "mobile"

    # Landline: DDD + 8 digits = 10 digits total
    if allow_landline and len(remaining) == 8:
        return True, "landline"

    return False, "invalid"


def format_phone_display(phone: str) -> str:
    """Format phone number for display with Brazilian formatting.

    Args:
        phone: Phone number (preferably normalized)

    Returns:
        Formatted phone for display

    Examples:
        >>> format_phone_display("+5511987654321")
        '+55 (11) 98765-4321'
        >>> format_phone_display("+551133334444")
        '+55 (11) 3333-4444'
    """
    normalized = normalize_phone(phone)

    if not normalized.startswith("+55"):
        return phone  # Return as-is if not Brazilian

    # Remove +55
    number = normalized[3:]

    if len(number) == 11:  # Mobile: (DD) 9XXXX-XXXX
        ddd = number[:2]
        part1 = number[2:7]
        part2 = number[7:]
        return f"+55 ({ddd}) {part1}-{part2}"
    elif len(number) == 10:  # Landline: (DD) XXXX-XXXX
        ddd = number[:2]
        part1 = number[2:6]
        part2 = number[6:]
        return f"+55 ({ddd}) {part1}-{part2}"

    return phone  # Return as-is if format doesn't match

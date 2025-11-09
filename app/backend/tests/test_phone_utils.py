"""Tests for phone number validation and normalization utilities."""

from src.services.briefing.phone_utils import (
    format_phone_display,
    normalize_phone,
    validate_brazilian_phone,
)


def test_normalize_phone_with_formatting():
    """Test normalizing phone with standard Brazilian formatting."""
    assert normalize_phone("(11) 98765-4321") == "+5511987654321"


def test_normalize_phone_with_spaces():
    """Test normalizing phone with spaces."""
    assert normalize_phone("11 9 8765 4321") == "+5511987654321"


def test_normalize_phone_already_normalized():
    """Test normalizing already normalized phone."""
    assert normalize_phone("+5511987654321") == "+5511987654321"


def test_normalize_phone_with_country_code_no_plus():
    """Test normalizing phone with country code but no plus sign."""
    assert normalize_phone("5511987654321") == "+5511987654321"


def test_normalize_phone_without_country_code():
    """Test normalizing phone without country code."""
    assert normalize_phone("11987654321") == "+5511987654321"


def test_normalize_phone_various_formatting():
    """Test normalizing phones with various formatting styles."""
    test_cases = [
        ("(11) 98765-4321", "+5511987654321"),
        ("11987654321", "+5511987654321"),
        ("+55 11 98765-4321", "+5511987654321"),
        ("55 (11) 9 8765-4321", "+5511987654321"),
        ("+55 11 3333-4444", "+551133334444"),
    ]

    for input_phone, expected in test_cases:
        assert normalize_phone(input_phone) == expected


def test_validate_mobile_phone():
    """Test validation of valid mobile phone."""
    is_valid, phone_type = validate_brazilian_phone("+5511987654321")
    assert is_valid is True
    assert phone_type == "mobile"


def test_validate_landline_phone():
    """Test validation of valid landline phone."""
    is_valid, phone_type = validate_brazilian_phone("+551133334444")
    assert is_valid is True
    assert phone_type == "landline"


def test_validate_landline_not_allowed():
    """Test validation when landlines are not allowed."""
    is_valid, phone_type = validate_brazilian_phone("+551133334444", allow_landline=False)
    assert is_valid is False
    assert phone_type == "invalid"


def test_validate_invalid_too_short():
    """Test validation of phone number that's too short."""
    is_valid, phone_type = validate_brazilian_phone("+5511888")
    assert is_valid is False
    assert phone_type == "invalid"


def test_validate_invalid_ddd():
    """Test validation of phone with invalid DDD."""
    is_valid, phone_type = validate_brazilian_phone("+5509987654321")
    assert is_valid is False
    assert phone_type == "invalid"


def test_validate_various_valid_ddds():
    """Test validation with various valid Brazilian DDDs."""
    valid_ddds = ["11", "21", "41", "51", "85", "91"]

    for ddd in valid_ddds:
        is_valid, phone_type = validate_brazilian_phone(f"+55{ddd}987654321")
        assert is_valid is True
        assert phone_type == "mobile"


def test_validate_mobile_without_9():
    """Test validation of mobile number without leading 9 (invalid)."""
    is_valid, phone_type = validate_brazilian_phone("+5511887654321")
    assert is_valid is False
    assert phone_type == "invalid"


def test_validate_unformatted_phone():
    """Test validation handles unformatted input."""
    is_valid, phone_type = validate_brazilian_phone("11987654321")
    assert is_valid is True
    assert phone_type == "mobile"


def test_format_mobile_phone_display():
    """Test formatting mobile phone for display."""
    assert format_phone_display("+5511987654321") == "+55 (11) 98765-4321"


def test_format_landline_phone_display():
    """Test formatting landline phone for display."""
    assert format_phone_display("+551133334444") == "+55 (11) 3333-4444"


def test_format_phone_display_various_ddds():
    """Test formatting phones with different DDDs."""
    test_cases = [
        ("+5521987654321", "+55 (21) 98765-4321"),
        ("+5541987654321", "+55 (41) 98765-4321"),
        ("+5585987654321", "+55 (85) 98765-4321"),
    ]

    for input_phone, expected in test_cases:
        assert format_phone_display(input_phone) == expected


def test_format_phone_display_handles_unformatted():
    """Test that format_phone_display normalizes input first."""
    assert format_phone_display("(11) 98765-4321") == "+55 (11) 98765-4321"


def test_format_phone_display_invalid_returns_as_is():
    """Test that invalid phones are returned as-is."""
    invalid_phone = "+1234567"
    assert format_phone_display(invalid_phone) == invalid_phone

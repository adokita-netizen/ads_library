"""Tests for shared utility modules: db.py and crypto.py."""

import pytest

from app.utils.db import escape_like
from app.utils.crypto import encrypt_value, decrypt_value


class TestEscapeLike:
    """Test SQL LIKE wildcard escaping."""

    def test_escapes_percent(self):
        assert escape_like("100%") == "100\\%"

    def test_escapes_underscore(self):
        assert escape_like("user_name") == "user\\_name"

    def test_escapes_backslash(self):
        assert escape_like("path\\to") == "path\\\\to"

    def test_escapes_all_at_once(self):
        assert escape_like("a%b_c\\d") == "a\\%b\\_c\\\\d"

    def test_plain_string_unchanged(self):
        assert escape_like("hello world") == "hello world"

    def test_empty_string(self):
        assert escape_like("") == ""

    def test_japanese_string(self):
        assert escape_like("美容%コスメ") == "美容\\%コスメ"


class TestCrypto:
    """Test Fernet encryption/decryption for API keys."""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "sk-abc123secretkey"
        ciphertext = encrypt_value(plaintext)
        assert ciphertext != plaintext
        assert decrypt_value(ciphertext) == plaintext

    def test_encrypt_produces_different_ciphertexts(self):
        """Fernet uses random IV, so encrypting the same value twice should differ."""
        ct1 = encrypt_value("same-value")
        ct2 = encrypt_value("same-value")
        assert ct1 != ct2
        # But both should decrypt to the same value
        assert decrypt_value(ct1) == "same-value"
        assert decrypt_value(ct2) == "same-value"

    def test_decrypt_invalid_raises(self):
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_value("not-a-valid-ciphertext")

    def test_decrypt_tampered_raises(self):
        ct = encrypt_value("secret")
        tampered = ct[:-5] + "XXXXX"
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_value(tampered)

    def test_empty_string_roundtrip(self):
        ct = encrypt_value("")
        assert decrypt_value(ct) == ""

    def test_unicode_roundtrip(self):
        plaintext = "日本語のAPIキー🔑"
        ct = encrypt_value(plaintext)
        assert decrypt_value(ct) == plaintext

    def test_long_key_roundtrip(self):
        plaintext = "EAAGm0PX" + "a" * 500
        ct = encrypt_value(plaintext)
        assert decrypt_value(ct) == plaintext

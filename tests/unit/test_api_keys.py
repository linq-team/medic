"""Unit tests for API key generation, hashing, and verification."""
import pytest
from unittest.mock import patch


class TestGenerateApiKey:
    """Tests for generate_api_key function."""

    def test_generate_api_key_returns_tuple(self):
        """Test that generate_api_key returns a tuple of (key, hash)."""
        from Medic.Core.api_keys import generate_api_key

        result = generate_api_key()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generate_api_key_has_prefix(self):
        """Test that generated key has the expected prefix."""
        from Medic.Core.api_keys import generate_api_key, API_KEY_PREFIX

        full_key, _ = generate_api_key()

        assert full_key.startswith(API_KEY_PREFIX)

    def test_generate_api_key_sufficient_length(self):
        """Test that generated key has sufficient entropy (32+ bytes)."""
        from Medic.Core.api_keys import generate_api_key, API_KEY_PREFIX, MIN_KEY_BYTES

        full_key, _ = generate_api_key()

        # Remove prefix and check remaining length
        # URL-safe base64 uses ~4 chars per 3 bytes, so 32 bytes = ~43 chars
        key_body = full_key[len(API_KEY_PREFIX) :]
        # 32 bytes in URL-safe base64 is 43 characters
        assert len(key_body) >= 43

    def test_generate_api_key_returns_valid_hash(self):
        """Test that generate_api_key returns a valid argon2 hash."""
        from Medic.Core.api_keys import generate_api_key

        _, key_hash = generate_api_key()

        # Argon2 hashes start with $argon2
        assert key_hash.startswith("$argon2")

    def test_generate_api_key_unique_keys(self):
        """Test that multiple calls generate unique keys."""
        from Medic.Core.api_keys import generate_api_key

        keys = set()
        for _ in range(100):
            full_key, _ = generate_api_key()
            keys.add(full_key)

        # All keys should be unique
        assert len(keys) == 100

    def test_generate_api_key_unique_hashes(self):
        """Test that even hashing the same key twice produces different hashes."""
        from Medic.Core.api_keys import generate_api_key, hash_api_key

        full_key, hash1 = generate_api_key()
        hash2 = hash_api_key(full_key)

        # Argon2 includes random salt, so hashes should be different
        assert hash1 != hash2


class TestHashApiKey:
    """Tests for hash_api_key function."""

    def test_hash_api_key_returns_string(self):
        """Test that hash_api_key returns a string."""
        from Medic.Core.api_keys import hash_api_key

        result = hash_api_key("test_key")

        assert isinstance(result, str)

    def test_hash_api_key_returns_argon2_hash(self):
        """Test that hash_api_key returns an argon2 formatted hash."""
        from Medic.Core.api_keys import hash_api_key

        result = hash_api_key("test_key")

        assert result.startswith("$argon2")

    def test_hash_api_key_different_salts(self):
        """Test that hashing same key produces different hashes (random salt)."""
        from Medic.Core.api_keys import hash_api_key

        hash1 = hash_api_key("same_key")
        hash2 = hash_api_key("same_key")

        # Even same input should produce different hashes due to random salt
        assert hash1 != hash2


class TestVerifyApiKey:
    """Tests for verify_api_key function."""

    def test_verify_api_key_valid_key(self):
        """Test that verify_api_key returns True for valid key."""
        from Medic.Core.api_keys import generate_api_key, verify_api_key

        full_key, key_hash = generate_api_key()

        result = verify_api_key(full_key, key_hash)

        assert result is True

    def test_verify_api_key_invalid_key(self):
        """Test that verify_api_key returns False for invalid key."""
        from Medic.Core.api_keys import generate_api_key, verify_api_key

        _, key_hash = generate_api_key()

        result = verify_api_key("wrong_key", key_hash)

        assert result is False

    def test_verify_api_key_modified_key(self):
        """Test that verify_api_key returns False for modified key."""
        from Medic.Core.api_keys import generate_api_key, verify_api_key

        full_key, key_hash = generate_api_key()
        modified_key = full_key + "x"

        result = verify_api_key(modified_key, key_hash)

        assert result is False

    def test_verify_api_key_invalid_hash_format(self):
        """Test that verify_api_key returns False for invalid hash format."""
        from Medic.Core.api_keys import verify_api_key

        result = verify_api_key("some_key", "not_a_valid_hash")

        assert result is False

    def test_verify_api_key_empty_key(self):
        """Test that verify_api_key handles empty key."""
        from Medic.Core.api_keys import hash_api_key, verify_api_key

        key_hash = hash_api_key("real_key")

        result = verify_api_key("", key_hash)

        assert result is False


class TestNeedsRehash:
    """Tests for needs_rehash function."""

    def test_needs_rehash_fresh_hash(self):
        """Test that a freshly generated hash does not need rehashing."""
        from Medic.Core.api_keys import generate_api_key, needs_rehash

        _, key_hash = generate_api_key()

        result = needs_rehash(key_hash)

        assert result is False


class TestApiKeyIntegration:
    """Integration tests for the full API key workflow."""

    def test_full_workflow_generate_and_verify(self):
        """Test complete workflow: generate -> verify."""
        from Medic.Core.api_keys import generate_api_key, verify_api_key

        # Generate a key
        full_key, key_hash = generate_api_key()

        # Verify the key works
        assert verify_api_key(full_key, key_hash) is True

        # Verify wrong key fails
        assert verify_api_key("wrong_key", key_hash) is False

    def test_workflow_hash_separately(self):
        """Test workflow where hashing is done separately."""
        from Medic.Core.api_keys import hash_api_key, verify_api_key

        original_key = "mdk_my_custom_api_key_12345"
        stored_hash = hash_api_key(original_key)

        # Later, verify the key
        assert verify_api_key(original_key, stored_hash) is True
        assert verify_api_key("different_key", stored_hash) is False

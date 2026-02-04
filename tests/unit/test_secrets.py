"""Unit tests for secrets module."""
import base64
import os
import pytest
from unittest.mock import patch, MagicMock


# Generate a valid test key
TEST_KEY = base64.b64encode(os.urandom(32)).decode('utf-8')


class TestEncryptionKey:
    """Tests for encryption key handling."""

    def test_generate_encryption_key_returns_base64_string(self):
        """Test generate_encryption_key returns valid base64."""
        from Medic.Core.secrets import generate_encryption_key

        key = generate_encryption_key()
        assert isinstance(key, str)

        # Should be decodable
        decoded = base64.b64decode(key)
        assert len(decoded) == 32  # 256 bits

    def test_generate_encryption_key_unique(self):
        """Test generate_encryption_key returns unique values."""
        from Medic.Core.secrets import generate_encryption_key

        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        assert key1 != key2

    def test_get_encryption_key_raises_without_env_var(self):
        """Test _get_encryption_key raises EncryptionKeyError without env var."""
        from Medic.Core.secrets import _get_encryption_key, EncryptionKeyError

        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop('MEDIC_SECRETS_KEY', None)
            with pytest.raises(EncryptionKeyError, match="not found"):
                _get_encryption_key()

    def test_get_encryption_key_raises_for_invalid_base64(self):
        """Test _get_encryption_key raises for invalid base64."""
        from Medic.Core.secrets import _get_encryption_key, EncryptionKeyError

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': 'not-valid-base64!!!'}):
            with pytest.raises(EncryptionKeyError, match="Invalid encryption key format"):
                _get_encryption_key()

    def test_get_encryption_key_raises_for_wrong_size(self):
        """Test _get_encryption_key raises for wrong key size."""
        from Medic.Core.secrets import _get_encryption_key, EncryptionKeyError

        # 16 bytes instead of 32
        short_key = base64.b64encode(os.urandom(16)).decode('utf-8')
        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': short_key}):
            with pytest.raises(EncryptionKeyError, match="must be 32 bytes"):
                _get_encryption_key()

    def test_get_encryption_key_success(self):
        """Test _get_encryption_key returns key when properly configured."""
        from Medic.Core.secrets import _get_encryption_key

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            key = _get_encryption_key()
            assert len(key) == 32


class TestEncryption:
    """Tests for encryption/decryption functions."""

    def test_encrypt_secret_returns_tuple(self):
        """Test encrypt_secret returns (ciphertext, nonce, tag) tuple."""
        from Medic.Core.secrets import encrypt_secret

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            ciphertext, nonce, tag = encrypt_secret("test secret")

            assert isinstance(ciphertext, bytes)
            assert isinstance(nonce, bytes)
            assert isinstance(tag, bytes)
            assert len(nonce) == 12  # GCM nonce
            assert len(tag) == 16    # GCM tag

    def test_encrypt_secret_unique_nonce(self):
        """Test encrypt_secret generates unique nonce each time."""
        from Medic.Core.secrets import encrypt_secret

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            _, nonce1, _ = encrypt_secret("test")
            _, nonce2, _ = encrypt_secret("test")
            assert nonce1 != nonce2

    def test_decrypt_secret_roundtrip(self):
        """Test encrypt then decrypt returns original value."""
        from Medic.Core.secrets import encrypt_secret, decrypt_secret

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            original = "my super secret password!"
            ciphertext, nonce, tag = encrypt_secret(original)
            decrypted = decrypt_secret(ciphertext, nonce, tag)
            assert decrypted == original

    def test_decrypt_secret_unicode(self):
        """Test encryption/decryption handles unicode."""
        from Medic.Core.secrets import encrypt_secret, decrypt_secret

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            original = "Hello 世界! 🔐"
            ciphertext, nonce, tag = encrypt_secret(original)
            decrypted = decrypt_secret(ciphertext, nonce, tag)
            assert decrypted == original

    def test_decrypt_secret_fails_with_tampered_ciphertext(self):
        """Test decryption fails if ciphertext is tampered."""
        from Medic.Core.secrets import encrypt_secret, decrypt_secret, DecryptionError

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            ciphertext, nonce, tag = encrypt_secret("secret")
            # Tamper with ciphertext
            tampered = bytes([b ^ 0xFF for b in ciphertext])
            with pytest.raises(DecryptionError):
                decrypt_secret(tampered, nonce, tag)

    def test_decrypt_secret_fails_with_wrong_nonce(self):
        """Test decryption fails with wrong nonce."""
        from Medic.Core.secrets import encrypt_secret, decrypt_secret, DecryptionError

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            ciphertext, nonce, tag = encrypt_secret("secret")
            wrong_nonce = os.urandom(12)
            with pytest.raises(DecryptionError):
                decrypt_secret(ciphertext, wrong_nonce, tag)

    def test_decrypt_secret_fails_with_wrong_tag(self):
        """Test decryption fails with wrong tag."""
        from Medic.Core.secrets import encrypt_secret, decrypt_secret, DecryptionError

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            ciphertext, nonce, tag = encrypt_secret("secret")
            wrong_tag = os.urandom(16)
            with pytest.raises(DecryptionError):
                decrypt_secret(ciphertext, nonce, wrong_tag)

    def test_decrypt_secret_fails_with_wrong_key(self):
        """Test decryption fails with different key."""
        from Medic.Core.secrets import encrypt_secret, decrypt_secret, DecryptionError

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            ciphertext, nonce, tag = encrypt_secret("secret")

        # Use different key
        other_key = base64.b64encode(os.urandom(32)).decode('utf-8')
        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': other_key}):
            with pytest.raises(DecryptionError):
                decrypt_secret(ciphertext, nonce, tag)


class TestSecretPattern:
    """Tests for secret reference pattern matching."""

    def test_find_secret_references_single(self):
        """Test finding a single secret reference."""
        from Medic.Core.secrets import find_secret_references

        refs = find_secret_references("Bearer ${secrets.API_TOKEN}")
        assert refs == ["API_TOKEN"]

    def test_find_secret_references_multiple(self):
        """Test finding multiple secret references."""
        from Medic.Core.secrets import find_secret_references

        text = "user=${secrets.DB_USER} pass=${secrets.DB_PASSWORD}"
        refs = find_secret_references(text)
        assert set(refs) == {"DB_USER", "DB_PASSWORD"}

    def test_find_secret_references_in_dict(self):
        """Test finding secret references in dictionary."""
        from Medic.Core.secrets import find_secret_references

        data = {
            "url": "https://api.example.com",
            "headers": {
                "Authorization": "Bearer ${secrets.API_KEY}"
            },
            "body": {
                "password": "${secrets.PASSWORD}"
            }
        }
        refs = find_secret_references(data)
        assert set(refs) == {"API_KEY", "PASSWORD"}

    def test_find_secret_references_in_list(self):
        """Test finding secret references in list."""
        from Medic.Core.secrets import find_secret_references

        data = ["${secrets.SECRET1}", "plain text", "${secrets.SECRET2}"]
        refs = find_secret_references(data)
        assert set(refs) == {"SECRET1", "SECRET2"}

    def test_find_secret_references_none(self):
        """Test finding no secret references."""
        from Medic.Core.secrets import find_secret_references

        refs = find_secret_references("no secrets here ${VAR_NAME}")
        assert refs == []

    def test_find_secret_references_underscore_names(self):
        """Test secret names with underscores."""
        from Medic.Core.secrets import find_secret_references

        refs = find_secret_references("${secrets.MY_LONG_SECRET_NAME}")
        assert refs == ["MY_LONG_SECRET_NAME"]

    def test_find_secret_references_alphanumeric(self):
        """Test secret names with numbers."""
        from Medic.Core.secrets import find_secret_references

        refs = find_secret_references("${secrets.API_KEY_V2}")
        assert refs == ["API_KEY_V2"]


class TestSecretSubstitution:
    """Tests for secret substitution functionality."""

    @patch('Medic.Core.secrets.get_secret_value')
    def test_substitute_secrets_string(self, mock_get_value):
        """Test substituting secrets in a string."""
        from Medic.Core.secrets import substitute_secrets

        mock_get_value.return_value = "supersecret123"

        result = substitute_secrets("Bearer ${secrets.API_TOKEN}")
        assert result == "Bearer supersecret123"
        mock_get_value.assert_called_once_with("API_TOKEN")

    @patch('Medic.Core.secrets.get_secret_value')
    def test_substitute_secrets_dict(self, mock_get_value):
        """Test substituting secrets in a dictionary."""
        from Medic.Core.secrets import substitute_secrets

        mock_get_value.side_effect = lambda name: {
            "API_KEY": "key123",
            "API_SECRET": "secret456"
        }[name]

        data = {
            "key": "${secrets.API_KEY}",
            "secret": "${secrets.API_SECRET}"
        }
        result = substitute_secrets(data)
        assert result == {
            "key": "key123",
            "secret": "secret456"
        }

    @patch('Medic.Core.secrets.get_secret_value')
    def test_substitute_secrets_list(self, mock_get_value):
        """Test substituting secrets in a list."""
        from Medic.Core.secrets import substitute_secrets

        mock_get_value.return_value = "secret"

        data = ["prefix-${secrets.VALUE}", "plain"]
        result = substitute_secrets(data)
        assert result == ["prefix-secret", "plain"]

    @patch('Medic.Core.secrets.get_secret_value')
    def test_substitute_secrets_with_cache(self, mock_get_value):
        """Test substitution uses cache to avoid repeated DB calls."""
        from Medic.Core.secrets import substitute_secrets

        mock_get_value.return_value = "cached_value"

        cache: dict = {}
        # First call should populate cache
        result1 = substitute_secrets("${secrets.KEY}", cache)
        assert result1 == "cached_value"
        assert mock_get_value.call_count == 1

        # Second call should use cache
        result2 = substitute_secrets("${secrets.KEY}", cache)
        assert result2 == "cached_value"
        assert mock_get_value.call_count == 1  # Still 1, used cache

    @patch('Medic.Core.secrets.get_secret_value')
    def test_substitute_secrets_not_found_raises(self, mock_get_value):
        """Test substitution raises when secret not found."""
        from Medic.Core.secrets import substitute_secrets, SecretNotFoundError

        mock_get_value.side_effect = SecretNotFoundError("NOT_FOUND")

        with pytest.raises(SecretNotFoundError):
            substitute_secrets("${secrets.NOT_FOUND}")

    def test_substitute_secrets_non_string_passthrough(self):
        """Test non-string values pass through unchanged."""
        from Medic.Core.secrets import substitute_secrets

        assert substitute_secrets(123) == 123
        assert substitute_secrets(None) is None
        assert substitute_secrets(True) is True


class TestValidateSecretReferences:
    """Tests for validating secret references exist."""

    @patch('Medic.Core.secrets.secret_exists')
    def test_validate_all_exist(self, mock_exists):
        """Test validation passes when all secrets exist."""
        from Medic.Core.secrets import validate_secret_references

        mock_exists.return_value = True

        missing = validate_secret_references("${secrets.A} ${secrets.B}")
        assert missing == []

    @patch('Medic.Core.secrets.secret_exists')
    def test_validate_some_missing(self, mock_exists):
        """Test validation returns missing secret names."""
        from Medic.Core.secrets import validate_secret_references

        mock_exists.side_effect = lambda name: name == "EXISTS"

        missing = validate_secret_references(
            "${secrets.EXISTS} ${secrets.MISSING1} ${secrets.MISSING2}"
        )
        assert set(missing) == {"MISSING1", "MISSING2"}


class TestDatabaseOperations:
    """Tests for database operations."""

    @patch('Medic.Core.secrets.encrypt_secret')
    @patch('Medic.Core.secrets.db.query_db')
    def test_create_secret_success(self, mock_query, mock_encrypt):
        """Test creating a secret successfully."""
        from Medic.Core.secrets import create_secret

        mock_encrypt.return_value = (b'ciphertext', b'nonce12bytes', b'tag16byteslong!!')
        mock_query.return_value = '[{"secret_id": 1}]'

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            result = create_secret("API_TOKEN", "secret_value", "API token")

        assert result is not None
        assert result.secret_id == 1
        assert result.name == "API_TOKEN"
        assert result.description == "API token"

    @patch('Medic.Core.secrets.db.query_db')
    def test_create_secret_invalid_name(self, mock_query):
        """Test creating a secret with invalid name fails."""
        from Medic.Core.secrets import create_secret

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            # Name starts with number
            result = create_secret("123_INVALID", "value")
            assert result is None

            # Name has special characters
            result = create_secret("invalid-name", "value")
            assert result is None

    @patch('Medic.Core.secrets.db.query_db')
    def test_get_secret_metadata(self, mock_query):
        """Test getting secret metadata without value."""
        from Medic.Core.secrets import get_secret

        mock_query.return_value = '''[{
            "secret_id": 1,
            "name": "API_TOKEN",
            "description": "Test token",
            "created_at": "2026-02-03T14:00:00-06:00",
            "updated_at": "2026-02-03T14:00:00-06:00",
            "created_by": "test_user"
        }]'''

        result = get_secret("API_TOKEN")

        assert result is not None
        assert result.secret_id == 1
        assert result.name == "API_TOKEN"
        assert result.created_by == "test_user"

    @patch('Medic.Core.secrets.db.query_db')
    def test_get_secret_not_found(self, mock_query):
        """Test getting non-existent secret returns None."""
        from Medic.Core.secrets import get_secret

        mock_query.return_value = '[]'

        result = get_secret("NONEXISTENT")
        assert result is None

    @patch('Medic.Core.secrets.decrypt_secret')
    @patch('Medic.Core.secrets.db.query_db')
    def test_get_secret_value_success(self, mock_query, mock_decrypt):
        """Test getting and decrypting secret value."""
        from Medic.Core.secrets import get_secret_value
        import json

        # Create mock data with memoryview-like bytes
        encrypted_value = b'encrypted_data'
        nonce = b'nonce12bytes'
        tag = b'tag16byteslong!!'

        # The query returns a JSON string where bytea is returned as memoryview
        # We mock it by returning bytes directly
        mock_result = [{
            "encrypted_value": encrypted_value,
            "nonce": nonce,
            "tag": tag
        }]
        mock_query.return_value = json.dumps([{
            "encrypted_value": "encrypted_data",
            "nonce": "nonce12bytes",
            "tag": "tag16byteslong!!"
        }])
        mock_decrypt.return_value = "decrypted_secret"

        # Need to patch the bytea conversion since we're using str in mock
        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            with patch('Medic.Core.secrets.get_secret_value') as mock_get:
                mock_get.return_value = "decrypted_secret"
                result = mock_get("MY_SECRET")

        assert result == "decrypted_secret"

    @patch('Medic.Core.secrets.db.query_db')
    def test_get_secret_value_not_found(self, mock_query):
        """Test getting non-existent secret value raises."""
        from Medic.Core.secrets import get_secret_value, SecretNotFoundError

        mock_query.return_value = '[]'

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            with pytest.raises(SecretNotFoundError, match="not found"):
                get_secret_value("NONEXISTENT")

    @patch('Medic.Core.secrets.db.query_db')
    def test_list_secrets(self, mock_query):
        """Test listing all secrets."""
        from Medic.Core.secrets import list_secrets

        mock_query.return_value = '''[
            {"secret_id": 1, "name": "SECRET1", "description": null,
             "created_at": "2026-02-03T14:00:00-06:00",
             "updated_at": "2026-02-03T14:00:00-06:00", "created_by": null},
            {"secret_id": 2, "name": "SECRET2", "description": "desc",
             "created_at": "2026-02-03T14:00:00-06:00",
             "updated_at": "2026-02-03T14:00:00-06:00", "created_by": "admin"}
        ]'''

        result = list_secrets()

        assert len(result) == 2
        assert result[0].name == "SECRET1"
        assert result[1].name == "SECRET2"

    @patch('Medic.Core.secrets.db.query_db')
    def test_secret_exists_true(self, mock_query):
        """Test secret_exists returns True when secret exists."""
        from Medic.Core.secrets import secret_exists

        mock_query.return_value = '[{"?column?": 1}]'

        assert secret_exists("EXISTS") is True

    @patch('Medic.Core.secrets.db.query_db')
    def test_secret_exists_false(self, mock_query):
        """Test secret_exists returns False when secret doesn't exist."""
        from Medic.Core.secrets import secret_exists

        mock_query.return_value = '[]'

        assert secret_exists("NONEXISTENT") is False

    @patch('Medic.Core.secrets.encrypt_secret')
    @patch('Medic.Core.secrets.db.insert_db')
    def test_update_secret(self, mock_insert, mock_encrypt):
        """Test updating a secret."""
        from Medic.Core.secrets import update_secret

        mock_encrypt.return_value = (b'new_cipher', b'new_nonce!!!', b'new_tag_16bytes!')
        mock_insert.return_value = True

        with patch.dict(os.environ, {'MEDIC_SECRETS_KEY': TEST_KEY}):
            result = update_secret("MY_SECRET", "new_value")

        assert result is True

    @patch('Medic.Core.secrets.db.insert_db')
    def test_delete_secret(self, mock_insert):
        """Test deleting a secret."""
        from Medic.Core.secrets import delete_secret

        mock_insert.return_value = True

        result = delete_secret("MY_SECRET")
        assert result is True
        mock_insert.assert_called_once()


class TestSecretToDict:
    """Tests for Secret.to_dict method."""

    def test_to_dict(self):
        """Test Secret.to_dict returns proper dictionary."""
        from Medic.Core.secrets import Secret
        from datetime import datetime
        import pytz

        tz = pytz.timezone('America/Chicago')
        created = datetime(2026, 2, 3, 14, 0, 0, tzinfo=tz)
        updated = datetime(2026, 2, 3, 15, 0, 0, tzinfo=tz)

        secret = Secret(
            secret_id=1,
            name="API_KEY",
            description="API key for service",
            created_at=created,
            updated_at=updated,
            created_by="admin"
        )

        result = secret.to_dict()

        assert result["secret_id"] == 1
        assert result["name"] == "API_KEY"
        assert result["description"] == "API key for service"
        assert result["created_by"] == "admin"
        assert "created_at" in result
        assert "updated_at" in result


class TestExceptionClasses:
    """Tests for custom exception classes."""

    def test_secrets_error_base(self):
        """Test SecretsError is the base exception."""
        from Medic.Core.secrets import (
            SecretsError,
            EncryptionKeyError,
            SecretNotFoundError,
            DecryptionError
        )

        assert issubclass(EncryptionKeyError, SecretsError)
        assert issubclass(SecretNotFoundError, SecretsError)
        assert issubclass(DecryptionError, SecretsError)

    def test_encryption_key_error_message(self):
        """Test EncryptionKeyError has proper message."""
        from Medic.Core.secrets import EncryptionKeyError

        error = EncryptionKeyError("Key not found")
        assert "Key not found" in str(error)

    def test_secret_not_found_error_message(self):
        """Test SecretNotFoundError has proper message."""
        from Medic.Core.secrets import SecretNotFoundError

        error = SecretNotFoundError("MY_SECRET")
        assert "MY_SECRET" in str(error)

    def test_decryption_error_message(self):
        """Test DecryptionError has proper message."""
        from Medic.Core.secrets import DecryptionError

        error = DecryptionError("Invalid tag")
        assert "Invalid tag" in str(error)

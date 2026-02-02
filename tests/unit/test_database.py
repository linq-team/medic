"""Unit tests for database module."""
import pytest
from unittest.mock import patch, MagicMock
import psycopg2


class TestConnectDb:
    """Tests for connect_db function."""

    @patch("psycopg2.connect")
    def test_connect_db_success(self, mock_connect, mock_env_vars):
        """Test successful database connection."""
        from Medic.Core.database import connect_db

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = connect_db()

        assert result == mock_conn
        mock_connect.assert_called_once_with(
            user="test_user",
            password="test_pass",
            host="localhost",
            port="5432",
            database="test_medic"
        )

    @patch("psycopg2.connect")
    def test_connect_db_failure(self, mock_connect, mock_env_vars):
        """Test database connection failure."""
        from Medic.Core.database import connect_db

        mock_connect.side_effect = psycopg2.Error("Connection failed")

        with pytest.raises(ConnectionError):
            connect_db()


class TestQueryDb:
    """Tests for query_db function."""

    @patch("Medic.Core.database.connect_db")
    def test_query_db_with_columns(self, mock_connect, mock_env_vars):
        """Test query with column names returned."""
        from Medic.Core.database import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, "test", "UP")]
        mock_cursor.description = [("id",), ("name",), ("status",)]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = query_db("SELECT * FROM test WHERE id = %s", (1,))

        assert result is not None
        assert "id" in result
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = %s", (1,))
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("Medic.Core.database.connect_db")
    def test_query_db_without_columns(self, mock_connect, mock_env_vars):
        """Test query returning raw rows."""
        from Medic.Core.database import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, "test", "UP")]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = query_db("SELECT * FROM test", show_columns=False)

        assert result == [(1, "test", "UP")]

    @patch("Medic.Core.database.connect_db")
    def test_query_db_error_handling(self, mock_connect, mock_env_vars):
        """Test query error handling."""
        from Medic.Core.database import query_db

        mock_connect.side_effect = psycopg2.Error("Query failed")

        result = query_db("SELECT * FROM test")

        assert result is None

    @patch("Medic.Core.database.connect_db")
    def test_query_db_cursor_closed_on_error(self, mock_connect, mock_env_vars):
        """Test cursor is closed even on error."""
        from Medic.Core.database import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.Error("Query failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = query_db("SELECT * FROM test")

        assert result is None
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


class TestInsertDb:
    """Tests for insert_db function."""

    @patch("Medic.Core.database.connect_db")
    def test_insert_db_success(self, mock_connect, mock_env_vars):
        """Test successful insert."""
        from Medic.Core.database import insert_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = insert_db("INSERT INTO test VALUES (%s)", ("value",))

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("Medic.Core.database.connect_db")
    def test_insert_db_failure(self, mock_connect, mock_env_vars):
        """Test insert failure."""
        from Medic.Core.database import insert_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.Error("Insert failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = insert_db("INSERT INTO test VALUES (%s)", ("value",))

        assert result is False

    @patch("Medic.Core.database.connect_db")
    def test_insert_db_parameterized_query(self, mock_connect, mock_env_vars):
        """Test that parameterized queries work correctly."""
        from Medic.Core.database import insert_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        insert_db(
            "INSERT INTO services(name, value) VALUES (%s, %s)",
            ("test'; DROP TABLE services; --", "value")
        )

        # Verify the query was called with safe parameters
        call_args = mock_cursor.execute.call_args
        assert call_args[0][0] == "INSERT INTO services(name, value) VALUES (%s, %s)"
        assert call_args[0][1] == ("test'; DROP TABLE services; --", "value")

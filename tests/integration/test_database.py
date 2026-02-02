"""Integration tests for database operations with real PostgreSQL."""
import pytest
import os


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set - skipping real database tests"
)
class TestRealDatabaseIntegration:
    """
    Integration tests with real PostgreSQL database.

    These tests require a running PostgreSQL instance.
    Set TEST_DATABASE_URL environment variable to run these tests.

    Example:
        export TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/medic_test
    """

    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Set up test database connection."""
        # Parse TEST_DATABASE_URL and set individual env vars
        db_url = os.environ.get("TEST_DATABASE_URL", "")
        if db_url:
            # Simple URL parsing - in production use urllib.parse
            parts = db_url.replace("postgresql://", "").split("@")
            if len(parts) == 2:
                user_pass = parts[0].split(":")
                host_db = parts[1].split("/")
                host_port = host_db[0].split(":")

                os.environ["PG_USER"] = user_pass[0]
                os.environ["PG_PASS"] = user_pass[1] if len(user_pass) > 1 else ""
                os.environ["DB_HOST"] = host_port[0]
                os.environ["DB_NAME"] = host_db[1] if len(host_db) > 1 else "medic_test"

        yield

    def test_database_connection(self):
        """Test actual database connection."""
        from Medic.Core.database import connect_db

        conn = connect_db()
        assert conn is not None
        conn.close()

    def test_query_and_insert(self):
        """Test query and insert operations."""
        from Medic.Core.database import query_db, insert_db

        # Create a test table
        insert_db("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                name TEXT
            )
        """)

        # Insert data
        result = insert_db(
            "INSERT INTO test_table (name) VALUES (%s)",
            ("test_value",)
        )
        assert result is True

        # Query data
        rows = query_db(
            "SELECT * FROM test_table WHERE name = %s",
            ("test_value",),
            show_columns=False
        )
        assert len(rows) >= 1

        # Cleanup
        insert_db("DROP TABLE IF EXISTS test_table")


@pytest.mark.integration
class TestMockedDatabaseIntegration:
    """Integration tests with mocked database for CI environments."""

    def test_connection_retry_logic(self, mock_db_connection, mock_env_vars):
        """Test that connection failures are handled gracefully."""
        import psycopg2
        from Medic.Core.database import query_db

        mock_db_connection["connect"].side_effect = psycopg2.Error("Connection refused")

        result = query_db("SELECT 1")
        assert result is None

    def test_transaction_commit(self, mock_db_connection, mock_env_vars):
        """Test that transactions are properly committed."""
        from Medic.Core.database import insert_db

        mock_db_connection["connect"].side_effect = None
        mock_db_connection["connect"].return_value = mock_db_connection["connection"]

        result = insert_db("INSERT INTO test VALUES (%s)", ("value",))

        mock_db_connection["connection"].commit.assert_called_once()

"""Integration tests for Medic API."""
import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for the full API flow."""

    @patch("Medic.Core.database.connect_db")
    def test_full_heartbeat_flow(self, mock_connect, app, mock_env_vars):
        """Test the full heartbeat registration and posting flow."""
        client = app.test_client()

        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Step 1: Register a service
        mock_cursor.fetchall.return_value = [(0,)]  # Not registered
        response = client.post(
            "/service",
            data=json.dumps({
                "heartbeat_name": "integration-test-hb",
                "service_name": "integration-test-service",
                "alert_interval": 5,
                "team": "platform"
            }),
            content_type="application/json"
        )
        assert response.status_code == 201

        # Step 2: Post a heartbeat
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [
            ("service_id",), ("heartbeat_name",), ("active",),
            ("alert_interval",), ("team",), ("priority",)
        ]
        # Return service info for heartbeat lookup
        mock_cursor.fetchall.return_value = [(1, "integration-test-hb", 1, 5, "platform", "p3")]

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "integration-test-hb",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True
                with patch("Medic.Core.routes.hbeat.Heartbeat"):
                    response = client.post(
                        "/heartbeat",
                        data=json.dumps({
                            "heartbeat_name": "integration-test-hb",
                            "status": "UP"
                        }),
                        content_type="application/json"
                    )
                    assert response.status_code == 201

    @patch("Medic.Core.database.connect_db")
    def test_service_update_flow(self, mock_connect, app, mock_env_vars):
        """Test service update operations."""
        client = app.test_client()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            # Service exists
            mock_query.return_value = json.dumps([{"service_id": 1}])

            with patch("Medic.Core.routes.db.insert_db") as mock_insert:
                mock_insert.return_value = True

                # Mute the service
                response = client.post(
                    "/service/test-heartbeat",
                    data=json.dumps({"muted": 1}),
                    content_type="application/json"
                )
                assert response.status_code == 200

                # Update priority
                response = client.post(
                    "/service/test-heartbeat",
                    data=json.dumps({"priority": "p1"}),
                    content_type="application/json"
                )
                assert response.status_code == 200


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @patch("Medic.Core.database.connect_db")
    def test_parameterized_queries_prevent_injection(self, mock_connect, mock_env_vars):
        """Test that parameterized queries properly escape dangerous input."""
        from Medic.Core.database import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [("id",)]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Attempt SQL injection
        malicious_input = "'; DROP TABLE services; --"
        query_db(
            "SELECT * FROM services WHERE heartbeat_name = %s",
            (malicious_input,),
            show_columns=True
        )

        # Verify the dangerous input was passed as a parameter, not interpolated
        call_args = mock_cursor.execute.call_args
        assert call_args[0][0] == "SELECT * FROM services WHERE heartbeat_name = %s"
        assert call_args[0][1] == (malicious_input,)
        # The actual query string should NOT contain the malicious content
        assert "DROP TABLE" not in call_args[0][0]


@pytest.mark.integration
class TestV2HeartbeatSignals:
    """Integration tests for V2 heartbeat start/complete/fail endpoints."""

    def test_heartbeat_start_success(self, app, mock_env_vars):
        """Test successful recording of STARTED signal."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                # Mock job_runs module to avoid database dependency
                with patch("Medic.Core.routes.job_runs") as mock_job_runs:
                    mock_job_runs.record_job_start.return_value = None

                    response = client.post(
                        "/v2/heartbeat/1/start",
                        data=json.dumps({"run_id": "job-run-123"}),
                        content_type="application/json"
                    )

                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["message"] == "Job signal STARTED recorded successfully."
                    assert data["results"]["status"] == "STARTED"
                    assert data["results"]["run_id"] == "job-run-123"

    def test_heartbeat_complete_success(self, app, mock_env_vars):
        """Test successful recording of COMPLETED signal."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                # Mock job_runs module to avoid database dependency
                with patch("Medic.Core.routes.job_runs") as mock_job_runs:
                    mock_job_runs.record_job_completion.return_value = None

                    response = client.post(
                        "/v2/heartbeat/1/complete",
                        data=json.dumps({"run_id": "job-run-123"}),
                        content_type="application/json"
                    )

                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["message"] == "Job signal COMPLETED recorded successfully."
                    assert data["results"]["status"] == "COMPLETED"
                    assert data["results"]["run_id"] == "job-run-123"

    def test_heartbeat_fail_success(self, app, mock_env_vars):
        """Test successful recording of FAILED signal."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                # Mock job_runs module to avoid database dependency
                with patch("Medic.Core.routes.job_runs") as mock_job_runs:
                    mock_job_runs.record_job_completion.return_value = None

                    response = client.post(
                        "/v2/heartbeat/1/fail",
                        data=json.dumps({"run_id": "job-run-123"}),
                        content_type="application/json"
                    )

                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["message"] == "Job signal FAILED recorded successfully."
                    assert data["results"]["status"] == "FAILED"
                    assert data["results"]["run_id"] == "job-run-123"

    def test_heartbeat_start_without_run_id(self, app, mock_env_vars):
        """Test recording STARTED signal without run_id."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                response = client.post(
                    "/v2/heartbeat/1/start",
                    content_type="application/json"
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["run_id"] is None

    def test_heartbeat_signal_service_not_found(self, app, mock_env_vars):
        """Test signal recording when service doesn't exist."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = '[]'

            response = client.post(
                "/v2/heartbeat/999/start",
                data=json.dumps({"run_id": "job-run-123"}),
                content_type="application/json"
            )

            assert response.status_code == 404
            data = json.loads(response.data)
            assert data["success"] is False
            assert "not found" in data["message"]

    def test_heartbeat_signal_service_inactive(self, app, mock_env_vars):
        """Test signal recording when service is inactive."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 0
            }])

            response = client.post(
                "/v2/heartbeat/1/start",
                data=json.dumps({"run_id": "job-run-123"}),
                content_type="application/json"
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "inactive" in data["message"]

    def test_heartbeat_signal_database_error(self, app, mock_env_vars):
        """Test signal recording when database insert fails."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = False

                response = client.post(
                    "/v2/heartbeat/1/start",
                    data=json.dumps({"run_id": "job-run-123"}),
                    content_type="application/json"
                )

                assert response.status_code == 500
                data = json.loads(response.data)
                assert data["success"] is False
                assert "Failed" in data["message"]

    def test_full_job_lifecycle(self, app, mock_env_vars):
        """Test complete job lifecycle: start -> complete."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "batch-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                # Mock job_runs module to avoid database dependency
                with patch("Medic.Core.routes.job_runs") as mock_job_runs:
                    mock_job_runs.record_job_start.return_value = None
                    mock_job_runs.record_job_completion.return_value = None

                    run_id = "batch-run-456"

                    # Start the job
                    response = client.post(
                        "/v2/heartbeat/1/start",
                        data=json.dumps({"run_id": run_id}),
                        content_type="application/json"
                    )
                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["results"]["status"] == "STARTED"

                    # Complete the job
                    response = client.post(
                        "/v2/heartbeat/1/complete",
                        data=json.dumps({"run_id": run_id}),
                        content_type="application/json"
                    )
                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["results"]["status"] == "COMPLETED"

    def test_full_job_lifecycle_with_failure(self, app, mock_env_vars):
        """Test job lifecycle with failure: start -> fail."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "batch-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                # Mock job_runs module to avoid database dependency
                with patch("Medic.Core.routes.job_runs") as mock_job_runs:
                    mock_job_runs.record_job_start.return_value = None
                    mock_job_runs.record_job_completion.return_value = None

                    run_id = "batch-run-789"

                    # Start the job
                    response = client.post(
                        "/v2/heartbeat/1/start",
                        data=json.dumps({"run_id": run_id}),
                        content_type="application/json"
                    )
                    assert response.status_code == 201

                    # Fail the job
                    response = client.post(
                        "/v2/heartbeat/1/fail",
                        data=json.dumps({"run_id": run_id}),
                        content_type="application/json"
                    )
                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["results"]["status"] == "FAILED"

    def test_heartbeat_signal_invalid_json_body(self, app, mock_env_vars):
        """Test signal recording with invalid JSON body (still works, run_id=None)."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "test-job",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True

                # Send invalid JSON - should still work with run_id=None
                response = client.post(
                    "/v2/heartbeat/1/start",
                    data="not valid json",
                    content_type="application/json"
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["run_id"] is None


@pytest.mark.integration
class TestV2DurationStatistics:
    """Integration tests for V2 duration statistics endpoint."""

    def test_duration_stats_success_with_data(self, app, mock_env_vars):
        """Test successful stats retrieval with sufficient data."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "batch-job"
            }])

            with patch("Medic.Core.routes.job_runs.get_duration_statistics") as mock_stats:
                from Medic.Core.job_runs import DurationStatistics
                mock_stats.return_value = DurationStatistics(
                    service_id=1,
                    run_count=50,
                    avg_duration_ms=1500.5,
                    p50_duration_ms=1200,
                    p95_duration_ms=2800,
                    p99_duration_ms=3500,
                    min_duration_ms=500,
                    max_duration_ms=4000
                )

                response = client.get("/v2/services/1/stats")

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["service_id"] == 1
                assert data["results"]["run_count"] == 50
                assert data["results"]["avg_duration_ms"] == 1500.5
                assert data["results"]["p50_duration_ms"] == 1200
                assert data["results"]["p95_duration_ms"] == 2800
                assert data["results"]["p99_duration_ms"] == 3500
                assert data["results"]["min_duration_ms"] == 500
                assert data["results"]["max_duration_ms"] == 4000

    def test_duration_stats_insufficient_data(self, app, mock_env_vars):
        """Test stats retrieval with insufficient data (< 5 runs)."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "batch-job"
            }])

            with patch("Medic.Core.routes.job_runs.get_duration_statistics") as mock_stats:
                from Medic.Core.job_runs import DurationStatistics
                # Return empty stats (fewer than 5 runs)
                mock_stats.return_value = DurationStatistics(
                    service_id=1,
                    run_count=3
                )

                response = client.get("/v2/services/1/stats")

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["service_id"] == 1
                assert data["results"]["run_count"] == 3
                assert data["results"]["avg_duration_ms"] is None
                assert data["results"]["p50_duration_ms"] is None
                assert data["results"]["p95_duration_ms"] is None
                assert data["results"]["p99_duration_ms"] is None

    def test_duration_stats_no_runs(self, app, mock_env_vars):
        """Test stats retrieval with no runs."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "batch-job"
            }])

            with patch("Medic.Core.routes.job_runs.get_duration_statistics") as mock_stats:
                from Medic.Core.job_runs import DurationStatistics
                mock_stats.return_value = DurationStatistics(
                    service_id=1,
                    run_count=0
                )

                response = client.get("/v2/services/1/stats")

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["run_count"] == 0
                assert data["results"]["avg_duration_ms"] is None

    def test_duration_stats_service_not_found(self, app, mock_env_vars):
        """Test stats retrieval when service doesn't exist."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = '[]'

            response = client.get("/v2/services/999/stats")

            assert response.status_code == 404
            data = json.loads(response.data)
            assert data["success"] is False
            assert "not found" in data["message"]

    def test_duration_stats_service_null_result(self, app, mock_env_vars):
        """Test stats retrieval when database returns null."""
        client = app.test_client()

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = None

            response = client.get("/v2/services/999/stats")

            assert response.status_code == 404
            data = json.loads(response.data)
            assert data["success"] is False

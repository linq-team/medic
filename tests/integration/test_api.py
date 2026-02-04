"""Integration tests for Medic API."""
import os
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


@pytest.mark.integration
class TestV2AuditLogs:
    """Integration tests for V2 audit logs query endpoint."""

    def test_audit_logs_query_no_filters(self, app, mock_env_vars):
        """Test querying audit logs without any filters."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=0,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get("/v2/audit-logs")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["results"]["total_count"] == 0
            assert data["results"]["limit"] == 50
            assert data["results"]["offset"] == 0
            assert data["results"]["has_more"] is False

    def test_audit_logs_query_with_execution_id(self, app, mock_env_vars):
        """Test querying audit logs by execution_id."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import (
                AuditActionType,
                AuditLogEntry,
                AuditLogQueryResult,
            )
            from datetime import datetime
            import pytz

            now = datetime.now(pytz.timezone('America/Chicago'))
            mock_query.return_value = AuditLogQueryResult(
                entries=[
                    AuditLogEntry(
                        log_id=1,
                        execution_id=100,
                        action_type=AuditActionType.EXECUTION_STARTED,
                        details={"playbook_name": "test"},
                        actor=None,
                        timestamp=now,
                    )
                ],
                total_count=1,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get("/v2/audit-logs?execution_id=100")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["results"]["total_count"] == 1
            assert len(data["results"]["entries"]) == 1
            assert data["results"]["entries"][0]["execution_id"] == 100

            # Verify query was called with correct params
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["execution_id"] == 100

    def test_audit_logs_query_with_service_id(self, app, mock_env_vars):
        """Test querying audit logs by service_id."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=0,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get("/v2/audit-logs?service_id=42")

            assert response.status_code == 200
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["service_id"] == 42

    def test_audit_logs_query_with_action_type(self, app, mock_env_vars):
        """Test querying audit logs by action_type."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=0,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get("/v2/audit-logs?action_type=approved")

            assert response.status_code == 200
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["action_type"] == "approved"

    def test_audit_logs_query_with_invalid_action_type(self, app, mock_env_vars):
        """Test querying audit logs with invalid action_type."""
        client = app.test_client()

        response = client.get("/v2/audit-logs?action_type=invalid_type")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Invalid action_type" in data["message"]

    def test_audit_logs_query_with_date_range(self, app, mock_env_vars):
        """Test querying audit logs with date range."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=0,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get(
                "/v2/audit-logs?"
                "start_date=2026-01-01T00:00:00Z&"
                "end_date=2026-01-31T23:59:59Z"
            )

            assert response.status_code == 200
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["start_date"] is not None
            assert call_kwargs["end_date"] is not None

    def test_audit_logs_query_with_invalid_start_date(self, app, mock_env_vars):
        """Test querying audit logs with invalid start_date format."""
        client = app.test_client()

        response = client.get("/v2/audit-logs?start_date=not-a-date")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Invalid start_date format" in data["message"]

    def test_audit_logs_query_with_invalid_end_date(self, app, mock_env_vars):
        """Test querying audit logs with invalid end_date format."""
        client = app.test_client()

        response = client.get("/v2/audit-logs?end_date=2026/01/31")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Invalid end_date format" in data["message"]

    def test_audit_logs_query_with_pagination(self, app, mock_env_vars):
        """Test querying audit logs with pagination."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=100,
                limit=10,
                offset=50,
                has_more=True,
            )

            response = client.get("/v2/audit-logs?limit=10&offset=50")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["results"]["limit"] == 10
            assert data["results"]["offset"] == 50
            assert data["results"]["has_more"] is True

            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["limit"] == 10
            assert call_kwargs["offset"] == 50

    def test_audit_logs_csv_export(self, app, mock_env_vars):
        """Test exporting audit logs as CSV."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import (
                AuditActionType,
                AuditLogEntry,
                AuditLogQueryResult,
            )
            from datetime import datetime
            import pytz

            now = datetime.now(pytz.timezone('America/Chicago'))
            mock_query.return_value = AuditLogQueryResult(
                entries=[
                    AuditLogEntry(
                        log_id=1,
                        execution_id=100,
                        action_type=AuditActionType.EXECUTION_STARTED,
                        details={"playbook_name": "test"},
                        actor=None,
                        timestamp=now,
                    ),
                    AuditLogEntry(
                        log_id=2,
                        execution_id=100,
                        action_type=AuditActionType.APPROVED,
                        details={},
                        actor="user123",
                        timestamp=now,
                    ),
                ],
                total_count=2,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get(
                "/v2/audit-logs",
                headers={"Accept": "text/csv"}
            )

            assert response.status_code == 200
            assert response.content_type == "text/csv; charset=utf-8"
            assert (
                response.headers.get("Content-Disposition") ==
                "attachment; filename=audit_logs.csv"
            )
            assert response.headers.get("X-Total-Count") == "2"
            assert response.headers.get("X-Has-More") == "false"

            # Verify CSV content
            csv_content = response.data.decode("utf-8")
            assert "log_id" in csv_content  # Header
            assert "execution_started" in csv_content
            assert "approved" in csv_content
            assert "user123" in csv_content

    def test_audit_logs_query_with_actor(self, app, mock_env_vars):
        """Test querying audit logs by actor."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=0,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get("/v2/audit-logs?actor=user123")

            assert response.status_code == 200
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["actor"] == "user123"

    def test_audit_logs_query_multiple_filters(self, app, mock_env_vars):
        """Test querying audit logs with multiple filters."""
        client = app.test_client()

        with patch("Medic.Core.audit_log.query_audit_logs") as mock_query:
            from Medic.Core.audit_log import AuditLogQueryResult
            mock_query.return_value = AuditLogQueryResult(
                entries=[],
                total_count=0,
                limit=50,
                offset=0,
                has_more=False,
            )

            response = client.get(
                "/v2/audit-logs?"
                "execution_id=100&"
                "service_id=42&"
                "action_type=approved&"
                "actor=user123"
            )

            assert response.status_code == 200
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["execution_id"] == 100
            assert call_kwargs["service_id"] == 42
            assert call_kwargs["action_type"] == "approved"
            assert call_kwargs["actor"] == "user123"


@pytest.mark.integration
class TestV2PlaybookExecute:
    """Integration tests for V2 playbook execution API endpoint."""

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_success_no_approval(
        self, mock_rate, app, mock_env_vars
    ):
        """Test successful playbook execution without approval required."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=123,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.RUNNING,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/playbooks/1/execute",
                    data=json.dumps({}),
                    content_type="application/json"
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["execution_id"] == 123
                assert data["results"]["playbook_id"] == 1
                assert data["results"]["playbook_name"] == "test-playbook"
                assert data["results"]["status"] == "running"

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_with_service_id(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution with service_id parameter."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="service-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch("Medic.Core.routes.db.query_db") as mock_query:
                # Service exists
                mock_query.return_value = json.dumps([{
                    "service_id": 42,
                    "heartbeat_name": "test-service"
                }])

                with patch(
                    "Medic.Core.playbook_engine.start_playbook_execution"
                ) as mock_start:
                    from Medic.Core.playbook_engine import (
                        ExecutionStatus,
                        PlaybookExecution,
                    )
                    mock_execution = PlaybookExecution(
                        execution_id=124,
                        playbook_id=1,
                        service_id=42,
                        status=ExecutionStatus.RUNNING,
                    )
                    mock_start.return_value = mock_execution

                    response = client.post(
                        "/v2/playbooks/1/execute",
                        data=json.dumps({"service_id": 42}),
                        content_type="application/json"
                    )

                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["results"]["execution_id"] == 124
                    assert data["results"]["service_id"] == 42

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_with_variables(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution with custom variables."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="var-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=125,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.RUNNING,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/playbooks/1/execute",
                    data=json.dumps({
                        "variables": {
                            "ENV": "production",
                            "TIMEOUT": 30
                        }
                    }),
                    content_type="application/json"
                )

                assert response.status_code == 201

                # Verify variables were passed to start_playbook_execution
                mock_start.assert_called_once()
                call_kwargs = mock_start.call_args[1]
                assert call_kwargs["context"]["ENV"] == "production"
                assert call_kwargs["context"]["TIMEOUT"] == 30
                assert call_kwargs["context"]["trigger"] == "api"

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_pending_approval(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution that requires approval."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="approval-playbook",
                description="Test playbook requiring approval",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.REQUIRED,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=126,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.PENDING_APPROVAL,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/playbooks/1/execute",
                    data=json.dumps({}),
                    content_type="application/json"
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["status"] == "pending_approval"
                assert "approval" in data["results"]["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_not_found(self, mock_rate, app, mock_env_vars):
        """Test playbook execution when playbook doesn't exist."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            mock_get.return_value = None

            response = client.post(
                "/v2/playbooks/999/execute",
                data=json.dumps({}),
                content_type="application/json"
            )

            assert response.status_code == 404
            data = json.loads(response.data)
            assert data["success"] is False
            assert "not found" in data["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_service_not_found(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution when service_id doesn't exist."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch("Medic.Core.routes.db.query_db") as mock_query:
                # Service doesn't exist
                mock_query.return_value = '[]'

                response = client.post(
                    "/v2/playbooks/1/execute",
                    data=json.dumps({"service_id": 999}),
                    content_type="application/json"
                )

                assert response.status_code == 404
                data = json.loads(response.data)
                assert data["success"] is False
                assert "Service ID 999 not found" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_invalid_service_id(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution with invalid service_id type."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            response = client.post(
                "/v2/playbooks/1/execute",
                data=json.dumps({"service_id": "not-an-int"}),
                content_type="application/json"
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "integer" in data["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_invalid_variables(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution with invalid variables type."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            response = client.post(
                "/v2/playbooks/1/execute",
                data=json.dumps({"variables": "not-a-dict"}),
                content_type="application/json"
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "dictionary" in data["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_invalid_json(self, mock_rate, app, mock_env_vars):
        """Test playbook execution with invalid JSON body."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            response = client.post(
                "/v2/playbooks/1/execute",
                data="not valid json",
                content_type="application/json"
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Invalid JSON" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_execution_failure(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution when start fails."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                mock_start.return_value = None  # Execution failed

                response = client.post(
                    "/v2/playbooks/1/execute",
                    data=json.dumps({}),
                    content_type="application/json"
                )

                assert response.status_code == 500
                data = json.loads(response.data)
                assert data["success"] is False
                assert "Failed to start" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_empty_body(self, mock_rate, app, mock_env_vars):
        """Test playbook execution with empty request body."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=127,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.RUNNING,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/playbooks/1/execute",
                    content_type="application/json"
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["service_id"] is None

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_execute_playbook_string_service_id_conversion(
        self, mock_rate, app, mock_env_vars
    ):
        """Test playbook execution with string service_id that converts."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch("Medic.Core.routes.db.query_db") as mock_query:
                # Service exists
                mock_query.return_value = json.dumps([{
                    "service_id": 42,
                    "heartbeat_name": "test-service"
                }])

                with patch(
                    "Medic.Core.playbook_engine.start_playbook_execution"
                ) as mock_start:
                    from Medic.Core.playbook_engine import (
                        ExecutionStatus,
                        PlaybookExecution,
                    )
                    mock_execution = PlaybookExecution(
                        execution_id=128,
                        playbook_id=1,
                        service_id=42,
                        status=ExecutionStatus.RUNNING,
                    )
                    mock_start.return_value = mock_execution

                    # Send service_id as string "42"
                    response = client.post(
                        "/v2/playbooks/1/execute",
                        data=json.dumps({"service_id": "42"}),
                        content_type="application/json"
                    )

                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["results"]["service_id"] == 42


class TestWebhookTriggerPlaybook:
    """Tests for POST /v2/webhooks/playbooks/:id/trigger endpoint."""

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_playbook_success(self, mock_rate, app, mock_env_vars):
        """Test successful playbook execution via webhook."""
        mock_rate.return_value = None  # Not rate limited
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test playbook for webhook",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=200,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.RUNNING,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/webhooks/playbooks/1/trigger",
                    data=json.dumps({}),
                    content_type="application/json",
                    headers={"X-Webhook-Secret": "test-webhook-secret"}
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["execution_id"] == 200
                assert data["results"]["playbook_id"] == 1
                assert data["results"]["playbook_name"] == "test-playbook"
                assert data["results"]["status"] == "running"

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_missing_secret_header(
        self, mock_rate, app, mock_env_vars
    ):
        """Test webhook trigger without X-Webhook-Secret header."""
        mock_rate.return_value = None
        client = app.test_client()

        response = client.post(
            "/v2/webhooks/playbooks/1/trigger",
            data=json.dumps({}),
            content_type="application/json"
            # No X-Webhook-Secret header
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Missing X-Webhook-Secret" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_invalid_secret(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with invalid secret."""
        mock_rate.return_value = None
        client = app.test_client()

        response = client.post(
            "/v2/webhooks/playbooks/1/trigger",
            data=json.dumps({}),
            content_type="application/json",
            headers={"X-Webhook-Secret": "wrong-secret"}
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Invalid webhook secret" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    def test_webhook_trigger_no_secret_configured(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger when MEDIC_WEBHOOK_SECRET not configured."""
        mock_rate.return_value = None
        client = app.test_client()

        # Ensure the env var is not set
        with patch.dict(os.environ, {}, clear=False):
            # Remove the key if it exists
            if "MEDIC_WEBHOOK_SECRET" in os.environ:
                del os.environ["MEDIC_WEBHOOK_SECRET"]

            response = client.post(
                "/v2/webhooks/playbooks/1/trigger",
                data=json.dumps({}),
                content_type="application/json",
                headers={"X-Webhook-Secret": "some-secret"}
            )

            assert response.status_code == 503
            data = json.loads(response.data)
            assert data["success"] is False
            assert "not configured" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_playbook_not_found(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with non-existent playbook."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            mock_get.return_value = None

            response = client.post(
                "/v2/webhooks/playbooks/999/trigger",
                data=json.dumps({}),
                content_type="application/json",
                headers={"X-Webhook-Secret": "test-webhook-secret"}
            )

            assert response.status_code == 404
            data = json.loads(response.data)
            assert data["success"] is False
            assert "not found" in data["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_with_service_id(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with service_id in body."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch("Medic.Core.routes.db.query_db") as mock_query:
                mock_query.return_value = json.dumps([{
                    "service_id": 42,
                    "heartbeat_name": "test-service"
                }])

                with patch(
                    "Medic.Core.playbook_engine.start_playbook_execution"
                ) as mock_start:
                    from Medic.Core.playbook_engine import (
                        ExecutionStatus,
                        PlaybookExecution,
                    )
                    mock_execution = PlaybookExecution(
                        execution_id=201,
                        playbook_id=1,
                        service_id=42,
                        status=ExecutionStatus.RUNNING,
                    )
                    mock_start.return_value = mock_execution

                    response = client.post(
                        "/v2/webhooks/playbooks/1/trigger",
                        data=json.dumps({"service_id": 42}),
                        content_type="application/json",
                        headers={"X-Webhook-Secret": "test-webhook-secret"}
                    )

                    assert response.status_code == 201
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["results"]["service_id"] == 42

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_with_variables(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with variables in body."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=202,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.RUNNING,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/webhooks/playbooks/1/trigger",
                    data=json.dumps({
                        "variables": {
                            "ENV": "production",
                            "TIMEOUT": 30
                        }
                    }),
                    content_type="application/json",
                    headers={"X-Webhook-Secret": "test-webhook-secret"}
                )

                assert response.status_code == 201
                # Verify context was passed with variables and trigger type
                call_kwargs = mock_start.call_args[1]
                assert call_kwargs["context"]["ENV"] == "production"
                assert call_kwargs["context"]["TIMEOUT"] == 30
                assert call_kwargs["context"]["trigger"] == "webhook"

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_pending_approval(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with playbook requiring approval."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.REQUIRED,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                from Medic.Core.playbook_engine import (
                    ExecutionStatus,
                    PlaybookExecution,
                )
                mock_execution = PlaybookExecution(
                    execution_id=203,
                    playbook_id=1,
                    service_id=None,
                    status=ExecutionStatus.PENDING_APPROVAL,
                )
                mock_start.return_value = mock_execution

                response = client.post(
                    "/v2/webhooks/playbooks/1/trigger",
                    data=json.dumps({}),
                    content_type="application/json",
                    headers={"X-Webhook-Secret": "test-webhook-secret"}
                )

                assert response.status_code == 201
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["results"]["status"] == "pending_approval"
                assert "approval" in data["results"]["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_service_not_found(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with non-existent service_id."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch("Medic.Core.routes.db.query_db") as mock_query:
                mock_query.return_value = "[]"  # Service not found

                response = client.post(
                    "/v2/webhooks/playbooks/1/trigger",
                    data=json.dumps({"service_id": 999}),
                    content_type="application/json",
                    headers={"X-Webhook-Secret": "test-webhook-secret"}
                )

                assert response.status_code == 404
                data = json.loads(response.data)
                assert data["success"] is False
                assert "Service ID 999 not found" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_invalid_json(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with invalid JSON body."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            response = client.post(
                "/v2/webhooks/playbooks/1/trigger",
                data="not valid json",
                content_type="application/json",
                headers={"X-Webhook-Secret": "test-webhook-secret"}
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Invalid JSON" in data["message"]

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_invalid_service_id(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger with non-integer service_id."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            response = client.post(
                "/v2/webhooks/playbooks/1/trigger",
                data=json.dumps({"service_id": "not-an-int"}),
                content_type="application/json",
                headers={"X-Webhook-Secret": "test-webhook-secret"}
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False
            assert "integer" in data["message"].lower()

    @patch("Medic.Core.rate_limit_middleware.verify_rate_limit")
    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_execution_failure(self, mock_rate, app, mock_env_vars):
        """Test webhook trigger when execution fails to start."""
        mock_rate.return_value = None
        client = app.test_client()

        with patch("Medic.Core.playbook_engine.get_playbook_by_id") as mock_get:
            from Medic.Core.playbook_parser import (
                ApprovalMode,
                Playbook,
                WaitStep,
            )
            mock_playbook = Playbook(
                name="test-playbook",
                description="Test",
                steps=[WaitStep(name="wait", duration_seconds=1)],
                approval=ApprovalMode.NONE,
            )
            mock_get.return_value = mock_playbook

            with patch(
                "Medic.Core.playbook_engine.start_playbook_execution"
            ) as mock_start:
                mock_start.return_value = None  # Execution failed to start

                response = client.post(
                    "/v2/webhooks/playbooks/1/trigger",
                    data=json.dumps({}),
                    content_type="application/json",
                    headers={"X-Webhook-Secret": "test-webhook-secret"}
                )

                assert response.status_code == 500
                data = json.loads(response.data)
                assert data["success"] is False
                assert "Failed to start" in data["message"]

    @patch.dict(os.environ, {"MEDIC_WEBHOOK_SECRET": "test-webhook-secret"})
    def test_webhook_trigger_rate_limited(self, app, mock_env_vars):
        """Test webhook trigger when rate limited."""
        client = app.test_client()

        with patch(
            "Medic.Core.rate_limit_middleware.verify_rate_limit"
        ) as mock_rate:
            # Simulate rate limit exceeded
            mock_rate.return_value = (
                json.dumps({
                    "success": False,
                    "message": "Rate limit exceeded",
                    "retry_after": 30
                }),
                429,
                {"Retry-After": "30"}
            )

            response = client.post(
                "/v2/webhooks/playbooks/1/trigger",
                data=json.dumps({}),
                content_type="application/json",
                headers={"X-Webhook-Secret": "test-webhook-secret"}
            )

            assert response.status_code == 429
            data = json.loads(response.data)
            assert data["success"] is False
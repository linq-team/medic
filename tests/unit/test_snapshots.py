"""Unit tests for service snapshots module."""

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from Medic.Core.snapshots import (
    SnapshotActionType,
    ServiceSnapshot,
    SnapshotQueryResult,
    create_snapshot,
    get_snapshot_by_id,
    query_snapshots,
    restore_snapshot,
    get_service_data,
)


class TestSnapshotActionType:
    """Tests for SnapshotActionType enum."""

    def test_is_valid_returns_true_for_valid_types(self):
        """Test that is_valid returns True for valid action types."""
        assert SnapshotActionType.is_valid("deactivate") is True
        assert SnapshotActionType.is_valid("activate") is True
        assert SnapshotActionType.is_valid("mute") is True
        assert SnapshotActionType.is_valid("unmute") is True
        assert SnapshotActionType.is_valid("edit") is True
        assert SnapshotActionType.is_valid("bulk_edit") is True
        assert SnapshotActionType.is_valid("priority_change") is True
        assert SnapshotActionType.is_valid("team_change") is True
        assert SnapshotActionType.is_valid("delete") is True

    def test_is_valid_returns_false_for_invalid_types(self):
        """Test that is_valid returns False for invalid action types."""
        assert SnapshotActionType.is_valid("invalid") is False
        assert SnapshotActionType.is_valid("") is False
        assert SnapshotActionType.is_valid("DEACTIVATE") is False

    def test_values_returns_all_types(self):
        """Test that values() returns all valid action types."""
        values = SnapshotActionType.values()
        assert len(values) == 9
        assert "deactivate" in values
        assert "activate" in values


class TestServiceSnapshot:
    """Tests for ServiceSnapshot dataclass."""

    def test_to_dict_serializes_correctly(self):
        """Test that to_dict returns correct dictionary."""
        created_at = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        snapshot = ServiceSnapshot(
            snapshot_id=1,
            service_id=42,
            snapshot_data={"heartbeat_name": "test-service", "active": 1},
            action_type="deactivate",
            actor="user@example.com",
            created_at=created_at,
            restored_at=None,
        )

        result = snapshot.to_dict()

        assert result["snapshot_id"] == 1
        assert result["service_id"] == 42
        assert result["snapshot_data"] == {"heartbeat_name": "test-service", "active": 1}
        assert result["action_type"] == "deactivate"
        assert result["actor"] == "user@example.com"
        assert result["created_at"] == "2026-01-15T10:30:00+00:00"
        assert result["restored_at"] is None

    def test_to_dict_handles_restored_at(self):
        """Test that to_dict correctly serializes restored_at."""
        restored_at = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        snapshot = ServiceSnapshot(
            snapshot_id=1,
            service_id=42,
            snapshot_data={},
            action_type="edit",
            actor=None,
            created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            restored_at=restored_at,
        )

        result = snapshot.to_dict()

        assert result["restored_at"] == "2026-01-16T12:00:00+00:00"


class TestSnapshotQueryResult:
    """Tests for SnapshotQueryResult dataclass."""

    def test_to_dict_serializes_correctly(self):
        """Test that to_dict returns correct pagination structure."""
        entries = [
            ServiceSnapshot(
                snapshot_id=1,
                service_id=42,
                snapshot_data={},
                action_type="edit",
                actor=None,
                created_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                restored_at=None,
            )
        ]
        result = SnapshotQueryResult(
            entries=entries,
            total_count=100,
            limit=50,
            offset=0,
            has_more=True,
        )

        output = result.to_dict()

        assert len(output["entries"]) == 1
        assert output["total_count"] == 100
        assert output["limit"] == 50
        assert output["offset"] == 0
        assert output["has_more"] is True


class TestGetServiceData:
    """Tests for get_service_data function."""

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_service_data_when_found(self, mock_query_db):
        """Test that service data is returned when service exists."""
        mock_query_db.return_value = json.dumps([{
            "service_id": 42,
            "heartbeat_name": "test-service",
            "service_name": "Test Service",
            "active": 1,
            "alert_interval": 5,
            "threshold": 1,
            "team": "platform",
            "priority": "p2",
            "muted": 0,
            "down": 0,
            "runbook": "https://docs.example.com",
            "date_added": "2026-01-01T00:00:00",
            "date_modified": None,
            "date_muted": None,
        }])

        result = get_service_data(42)

        assert result is not None
        assert result["service_id"] == 42
        assert result["heartbeat_name"] == "test-service"

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_none_when_service_not_found(self, mock_query_db):
        """Test that None is returned when service doesn't exist."""
        mock_query_db.return_value = "[]"

        result = get_service_data(999)

        assert result is None

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_none_for_empty_result(self, mock_query_db):
        """Test that None is returned for empty result."""
        mock_query_db.return_value = None

        result = get_service_data(999)

        assert result is None


class TestCreateSnapshot:
    """Tests for create_snapshot function."""

    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    @patch("Medic.Core.snapshots.get_now")
    def test_creates_snapshot_successfully(self, mock_now, mock_insert, mock_query):
        """Test successful snapshot creation."""
        mock_now.return_value = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # First call - get service data
        mock_query.side_effect = [
            json.dumps([{
                "service_id": 42,
                "heartbeat_name": "test-service",
                "service_name": "Test Service",
                "active": 1,
                "alert_interval": 5,
                "threshold": 1,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "date_added": "2026-01-01T00:00:00",
                "date_modified": None,
                "date_muted": None,
            }]),
            # Second call - get snapshot ID
            json.dumps([{"snapshot_id": 1}]),
        ]
        mock_insert.return_value = True

        result = create_snapshot(
            service_id=42,
            action_type=SnapshotActionType.DEACTIVATE,
            actor="user@example.com",
        )

        assert result is not None
        assert result.snapshot_id == 1
        assert result.service_id == 42
        assert result.action_type == "deactivate"
        assert result.actor == "user@example.com"
        mock_insert.assert_called_once()

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_none_when_service_not_found(self, mock_query):
        """Test that None is returned when service doesn't exist."""
        mock_query.return_value = "[]"

        result = create_snapshot(
            service_id=999,
            action_type=SnapshotActionType.EDIT,
        )

        assert result is None

    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    def test_returns_none_when_insert_fails(self, mock_insert, mock_query):
        """Test that None is returned when database insert fails."""
        mock_query.return_value = json.dumps([{
            "service_id": 42,
            "heartbeat_name": "test-service",
            "service_name": "Test Service",
            "active": 1,
            "alert_interval": 5,
            "threshold": 1,
            "team": "platform",
            "priority": "p2",
            "muted": 0,
            "down": 0,
            "runbook": None,
            "date_added": "2026-01-01T00:00:00",
            "date_modified": None,
            "date_muted": None,
        }])
        mock_insert.return_value = False

        result = create_snapshot(
            service_id=42,
            action_type=SnapshotActionType.MUTE,
        )

        assert result is None


class TestGetSnapshotById:
    """Tests for get_snapshot_by_id function."""

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_snapshot_when_found(self, mock_query):
        """Test that snapshot is returned when found."""
        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": '{"heartbeat_name": "test-service", "active": 1}',
            "action_type": "deactivate",
            "actor": "user@example.com",
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": None,
        }])

        result = get_snapshot_by_id(1)

        assert result is not None
        assert result.snapshot_id == 1
        assert result.service_id == 42
        assert result.action_type == "deactivate"

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_none_when_not_found(self, mock_query):
        """Test that None is returned when snapshot doesn't exist."""
        mock_query.return_value = "[]"

        result = get_snapshot_by_id(999)

        assert result is None


class TestQuerySnapshots:
    """Tests for query_snapshots function."""

    @patch("Medic.Core.snapshots.db.query_db")
    def test_queries_all_snapshots(self, mock_query):
        """Test querying all snapshots without filters."""
        mock_query.side_effect = [
            # Count query
            json.dumps([{"total": 2}]),
            # Data query
            json.dumps([
                {
                    "snapshot_id": 2,
                    "service_id": 42,
                    "snapshot_data": '{}',
                    "action_type": "edit",
                    "actor": None,
                    "created_at": "2026-01-16T10:30:00+00:00",
                    "restored_at": None,
                },
                {
                    "snapshot_id": 1,
                    "service_id": 42,
                    "snapshot_data": '{}',
                    "action_type": "deactivate",
                    "actor": "user@example.com",
                    "created_at": "2026-01-15T10:30:00+00:00",
                    "restored_at": None,
                },
            ]),
        ]

        result = query_snapshots()

        assert result.total_count == 2
        assert len(result.entries) == 2
        assert result.limit == 50
        assert result.offset == 0
        assert result.has_more is False

    @patch("Medic.Core.snapshots.db.query_db")
    def test_queries_with_service_id_filter(self, mock_query):
        """Test querying snapshots filtered by service_id."""
        mock_query.side_effect = [
            json.dumps([{"total": 1}]),
            json.dumps([{
                "snapshot_id": 1,
                "service_id": 42,
                "snapshot_data": '{}',
                "action_type": "deactivate",
                "actor": None,
                "created_at": "2026-01-15T10:30:00+00:00",
                "restored_at": None,
            }]),
        ]

        result = query_snapshots(service_id=42)

        assert result.total_count == 1
        # Verify the query included the service_id filter
        call_args = mock_query.call_args_list[0]
        assert "service_id = %s" in call_args[0][0]

    @patch("Medic.Core.snapshots.db.query_db")
    def test_queries_with_action_type_filter(self, mock_query):
        """Test querying snapshots filtered by action_type."""
        mock_query.side_effect = [
            json.dumps([{"total": 1}]),
            json.dumps([{
                "snapshot_id": 1,
                "service_id": 42,
                "snapshot_data": '{}',
                "action_type": "mute",
                "actor": None,
                "created_at": "2026-01-15T10:30:00+00:00",
                "restored_at": None,
            }]),
        ]

        result = query_snapshots(action_type="mute")

        assert result.total_count == 1
        # Verify the query included the action_type filter
        call_args = mock_query.call_args_list[0]
        assert "action_type = %s" in call_args[0][0]

    @patch("Medic.Core.snapshots.db.query_db")
    def test_validates_limit_bounds(self, mock_query):
        """Test that limit is bounded correctly."""
        mock_query.side_effect = [
            json.dumps([{"total": 0}]),
            json.dumps([]),
        ]

        # Test max limit
        result = query_snapshots(limit=500)
        assert result.limit == 250

        # Reset mocks
        mock_query.side_effect = [
            json.dumps([{"total": 0}]),
            json.dumps([]),
        ]

        # Test min limit
        result = query_snapshots(limit=-5)
        assert result.limit == 1

    @patch("Medic.Core.snapshots.db.query_db")
    def test_has_more_is_true_when_more_results(self, mock_query):
        """Test that has_more is calculated correctly."""
        mock_query.side_effect = [
            json.dumps([{"total": 100}]),
            json.dumps([{
                "snapshot_id": 1,
                "service_id": 42,
                "snapshot_data": '{}',
                "action_type": "edit",
                "actor": None,
                "created_at": "2026-01-15T10:30:00+00:00",
                "restored_at": None,
            }]),
        ]

        result = query_snapshots(limit=1, offset=0)

        assert result.total_count == 100
        assert result.has_more is True


class TestRestoreSnapshot:
    """Tests for restore_snapshot function."""

    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    @patch("Medic.Core.snapshots.get_now")
    def test_restores_snapshot_successfully(self, mock_now, mock_insert, mock_query):
        """Test successful snapshot restoration."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_now.return_value = now

        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": json.dumps({
                "service_name": "Test Service",
                "active": 1,
                "alert_interval": 5,
                "threshold": 1,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": "https://docs.example.com",
            }),
            "action_type": "deactivate",
            "actor": "user@example.com",
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": None,
        }])
        mock_insert.return_value = True

        result = restore_snapshot(1, actor="restore-user@example.com")

        assert result is not None
        assert result.snapshot_id == 1
        assert result.restored_at == now
        # Verify both update queries were called (service update + snapshot restore)
        assert mock_insert.call_count == 2

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_none_when_snapshot_not_found(self, mock_query):
        """Test that None is returned when snapshot doesn't exist."""
        mock_query.return_value = "[]"

        result = restore_snapshot(999)

        assert result is None

    @patch("Medic.Core.snapshots.db.query_db")
    def test_returns_none_when_already_restored(self, mock_query):
        """Test that None is returned when snapshot was already restored."""
        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": '{}',
            "action_type": "deactivate",
            "actor": "user@example.com",
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": "2026-01-16T10:00:00+00:00",  # Already restored
        }])

        result = restore_snapshot(1)

        assert result is None

    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    def test_returns_none_when_update_fails(self, mock_insert, mock_query):
        """Test that None is returned when service update fails."""
        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": json.dumps({
                "service_name": "Test",
                "active": 1,
                "alert_interval": 5,
                "threshold": 1,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
            }),
            "action_type": "deactivate",
            "actor": None,
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": None,
        }])
        mock_insert.return_value = False

        result = restore_snapshot(1)

        assert result is None


class TestSnapshotRouteEndpoints:
    """Tests for snapshot API route endpoints."""

    @patch("Medic.Core.snapshots.db.query_db")
    def test_list_snapshots_endpoint(self, mock_query, client, mock_env_vars):
        """Test GET /v2/snapshots endpoint."""
        mock_query.side_effect = [
            json.dumps([{"total": 1}]),
            json.dumps([{
                "snapshot_id": 1,
                "service_id": 42,
                "snapshot_data": '{}',
                "action_type": "edit",
                "actor": None,
                "created_at": "2026-01-15T10:30:00+00:00",
                "restored_at": None,
            }]),
        ]

        response = client.get("/v2/snapshots")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "entries" in data["results"]
        assert "total_count" in data["results"]

    @patch("Medic.Core.snapshots.db.query_db")
    def test_list_snapshots_with_filters(self, mock_query, client, mock_env_vars):
        """Test GET /v2/snapshots with filters."""
        mock_query.side_effect = [
            json.dumps([{"total": 1}]),
            json.dumps([{
                "snapshot_id": 1,
                "service_id": 42,
                "snapshot_data": '{}',
                "action_type": "deactivate",
                "actor": None,
                "created_at": "2026-01-15T10:30:00+00:00",
                "restored_at": None,
            }]),
        ]

        response = client.get(
            "/v2/snapshots?service_id=42&action_type=deactivate&limit=10&offset=0"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_list_snapshots_invalid_action_type(self, client, mock_env_vars):
        """Test GET /v2/snapshots with invalid action_type."""
        response = client.get("/v2/snapshots?action_type=invalid")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Invalid action_type" in data["message"]

    def test_list_snapshots_invalid_date_format(self, client, mock_env_vars):
        """Test GET /v2/snapshots with invalid date format."""
        response = client.get("/v2/snapshots?start_date=invalid-date")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Invalid start_date format" in data["message"]

    @patch("Medic.Core.snapshots.db.query_db")
    def test_get_snapshot_endpoint(self, mock_query, client, mock_env_vars):
        """Test GET /v2/snapshots/:id endpoint."""
        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": '{"heartbeat_name": "test"}',
            "action_type": "edit",
            "actor": "user@example.com",
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": None,
        }])

        response = client.get("/v2/snapshots/1")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["results"]["snapshot_id"] == 1

    @patch("Medic.Core.snapshots.db.query_db")
    def test_get_snapshot_not_found(self, mock_query, client, mock_env_vars):
        """Test GET /v2/snapshots/:id when snapshot doesn't exist."""
        mock_query.return_value = "[]"

        response = client.get("/v2/snapshots/999")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data["message"]

    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    @patch("Medic.Core.snapshots.get_now")
    def test_restore_snapshot_endpoint(
        self, mock_now, mock_insert, mock_query, client, mock_env_vars
    ):
        """Test POST /v2/snapshots/:id/restore endpoint."""
        mock_now.return_value = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": json.dumps({
                "service_name": "Test",
                "active": 1,
                "alert_interval": 5,
                "threshold": 1,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
            }),
            "action_type": "deactivate",
            "actor": None,
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": None,
        }])
        mock_insert.return_value = True

        response = client.post(
            "/v2/snapshots/1/restore",
            data=json.dumps({"actor": "restore-user@example.com"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "restored_at" in data["results"]

    @patch("Medic.Core.snapshots.db.query_db")
    def test_restore_snapshot_not_found(self, mock_query, client, mock_env_vars):
        """Test POST /v2/snapshots/:id/restore when snapshot doesn't exist."""
        mock_query.return_value = "[]"

        response = client.post("/v2/snapshots/999/restore")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data["message"]

    @patch("Medic.Core.snapshots.db.query_db")
    def test_restore_snapshot_already_restored(self, mock_query, client, mock_env_vars):
        """Test POST /v2/snapshots/:id/restore when already restored."""
        mock_query.return_value = json.dumps([{
            "snapshot_id": 1,
            "service_id": 42,
            "snapshot_data": '{}',
            "action_type": "deactivate",
            "actor": None,
            "created_at": "2026-01-15T10:30:00+00:00",
            "restored_at": "2026-01-16T10:00:00+00:00",  # Already restored
        }])

        response = client.post("/v2/snapshots/1/restore")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "already been restored" in data["message"]


class TestAutoSnapshotCreation:
    """Tests for auto-snapshot creation on service updates."""

    @patch("Medic.Core.routes.db")
    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    def test_creates_snapshot_on_deactivate(
        self, mock_snapshot_insert, mock_snapshot_query, mock_routes_db, client, mock_env_vars
    ):
        """Test that snapshot is created when deactivating a service."""
        # Mock routes db - service lookup
        mock_routes_db.query_db.return_value = json.dumps([{
            "service_id": 42,
        }])
        mock_routes_db.insert_db.return_value = True

        # Mock snapshots db - get service data and snapshot ID
        mock_snapshot_query.side_effect = [
            json.dumps([{
                "service_id": 42,
                "heartbeat_name": "test-service",
                "service_name": "Test",
                "active": 1,
                "alert_interval": 5,
                "threshold": 1,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "date_added": "2026-01-01T00:00:00",
                "date_modified": None,
                "date_muted": None,
            }]),
            json.dumps([{"snapshot_id": 1}]),
        ]
        mock_snapshot_insert.return_value = True

        response = client.post(
            "/service/test-service",
            data=json.dumps({"active": 0}),
            content_type="application/json",
        )

        assert response.status_code == 200
        # Verify snapshot was created
        assert mock_snapshot_insert.called

    @patch("Medic.Core.routes.db")
    @patch("Medic.Core.snapshots.db.query_db")
    @patch("Medic.Core.snapshots.db.insert_db")
    def test_creates_snapshot_on_mute(
        self, mock_snapshot_insert, mock_snapshot_query, mock_routes_db, client, mock_env_vars
    ):
        """Test that snapshot is created when muting a service."""
        mock_routes_db.query_db.return_value = json.dumps([{
            "service_id": 42,
        }])
        mock_routes_db.insert_db.return_value = True

        mock_snapshot_query.side_effect = [
            json.dumps([{
                "service_id": 42,
                "heartbeat_name": "test-service",
                "service_name": "Test",
                "active": 1,
                "alert_interval": 5,
                "threshold": 1,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "date_added": "2026-01-01T00:00:00",
                "date_modified": None,
                "date_muted": None,
            }]),
            json.dumps([{"snapshot_id": 1}]),
        ]
        mock_snapshot_insert.return_value = True

        response = client.post(
            "/service/test-service",
            data=json.dumps({"muted": 1}),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert mock_snapshot_insert.called

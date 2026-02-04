"""Unit tests for team-based alert routing."""
import json
from unittest.mock import patch


class TestGetTeamForService:
    """Tests for get_team_for_service function."""

    def test_returns_team_when_service_has_team(self, mock_env_vars):
        """Test that team is returned when service has a team assigned."""
        from Medic.Core.alert_routing import get_team_for_service

        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": "C87654321"
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_team_for_service(123)

            assert result is not None
            assert result["team_id"] == 1
            assert result["name"] == "Platform"
            assert result["slack_channel_id"] == "C87654321"

    def test_returns_none_when_service_has_no_team(self, mock_env_vars):
        """Test that None is returned when service has no team."""
        from Medic.Core.alert_routing import get_team_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_team_for_service(123)

            assert result is None

    def test_returns_none_when_query_fails(self, mock_env_vars):
        """Test that None is returned when database query fails."""
        from Medic.Core.alert_routing import get_team_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = None

            result = get_team_for_service(123)

            assert result is None

    def test_query_joins_teams_and_services(self, mock_env_vars):
        """Test that query properly joins teams and services tables."""
        from Medic.Core.alert_routing import get_team_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            get_team_for_service(456)

            mock_query.assert_called_once()
            call_args = mock_query.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "medic.teams" in query
            assert "services" in query
            assert "INNER JOIN" in query
            assert params == (456,)


class TestGetSlackChannelForService:
    """Tests for get_slack_channel_for_service function."""

    def test_returns_team_channel_when_team_has_channel(self, mock_env_vars):
        """Test that team's Slack channel is returned when available."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": "C_TEAM_CHANNEL"
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_service(123)

            assert result == "C_TEAM_CHANNEL"

    def test_returns_default_when_team_has_no_channel(self, mock_env_vars):
        """Test that default channel is returned when team has no channel."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": None
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_service(123)

            # Default from mock_env_vars fixture
            assert result == "C12345678"

    def test_returns_default_when_team_channel_empty(self, mock_env_vars):
        """Test that default channel is returned when team channel is empty."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": ""
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_service(123)

            assert result == "C12345678"

    def test_returns_default_when_no_team(self, mock_env_vars):
        """Test that default channel is returned when service has no team."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_slack_channel_for_service(123)

            assert result == "C12345678"

    def test_returns_default_when_query_fails(self, mock_env_vars):
        """Test that default channel is returned when database fails."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = None

            result = get_slack_channel_for_service(123)

            assert result == "C12345678"

    def test_returns_empty_when_no_default_and_no_team(self):
        """Test behavior when no default channel is set and no team."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])
            with patch.dict("os.environ", {}, clear=True):
                result = get_slack_channel_for_service(123)

                assert result == ""


class TestGetSlackChannelForTeam:
    """Tests for get_slack_channel_for_team function."""

    def test_returns_team_channel_when_set(self, mock_env_vars):
        """Test that team's Slack channel is returned when set."""
        from Medic.Core.alert_routing import get_slack_channel_for_team

        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": "C_PLATFORM"
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_team(1)

            assert result == "C_PLATFORM"

    def test_returns_default_when_team_has_no_channel(self, mock_env_vars):
        """Test that default channel is returned when team has no channel."""
        from Medic.Core.alert_routing import get_slack_channel_for_team

        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": None
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_team(1)

            assert result == "C12345678"

    def test_returns_default_when_team_not_found(self, mock_env_vars):
        """Test that default channel is returned when team doesn't exist."""
        from Medic.Core.alert_routing import get_slack_channel_for_team

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_slack_channel_for_team(999)

            assert result == "C12345678"

    def test_returns_default_when_query_fails(self, mock_env_vars):
        """Test that default channel is returned when query fails."""
        from Medic.Core.alert_routing import get_slack_channel_for_team

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = None

            result = get_slack_channel_for_team(1)

            assert result == "C12345678"

    def test_queries_correct_table(self, mock_env_vars):
        """Test that query targets the teams table correctly."""
        from Medic.Core.alert_routing import get_slack_channel_for_team

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            get_slack_channel_for_team(42)

            mock_query.assert_called_once()
            call_args = mock_query.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "medic.teams" in query
            assert "team_id" in query
            assert params == (42,)


class TestAlertRoutingIntegration:
    """Integration tests for alert routing."""

    def test_routing_priority_team_channel_first(self, mock_env_vars):
        """Test that team channel takes priority over default."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        # Service has team with channel
        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": "C_CUSTOM_TEAM"
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_service(123)

            # Team channel takes priority
            assert result == "C_CUSTOM_TEAM"
            # Not the default
            assert result != "C12345678"

    def test_fallback_chain_no_team_channel_to_default(self, mock_env_vars):
        """Test fallback from team without channel to default."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        # Service has team without channel
        team_data = [{
            "team_id": 1,
            "name": "Platform",
            "slack_channel_id": None
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(team_data)

            result = get_slack_channel_for_service(123)

            # Falls back to default
            assert result == "C12345678"

    def test_fallback_chain_no_team_to_default(self, mock_env_vars):
        """Test fallback from no team to default."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_slack_channel_for_service(123)

            # Falls back to default
            assert result == "C12345678"

    def test_multiple_services_different_teams(self, mock_env_vars):
        """Test that different services can route to different channels."""
        from Medic.Core.alert_routing import get_slack_channel_for_service

        # First call for service 1
        team1_data = [{
            "team_id": 1,
            "name": "Team A",
            "slack_channel_id": "C_TEAM_A"
        }]

        # Second call for service 2
        team2_data = [{
            "team_id": 2,
            "name": "Team B",
            "slack_channel_id": "C_TEAM_B"
        }]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.side_effect = [
                json.dumps(team1_data),
                json.dumps(team2_data)
            ]

            result1 = get_slack_channel_for_service(1)
            result2 = get_slack_channel_for_service(2)

            assert result1 == "C_TEAM_A"
            assert result2 == "C_TEAM_B"
            assert result1 != result2


class TestGetNotificationTargetsForService:
    """Tests for get_notification_targets_for_service function."""

    def test_returns_empty_list_when_no_targets(self, mock_env_vars):
        """Test that empty list is returned when service has no targets."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_notification_targets_for_service(123)

            assert result == []

    def test_returns_empty_list_when_query_fails(self, mock_env_vars):
        """Test that empty list is returned when query fails."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = None

            result = get_notification_targets_for_service(123)

            assert result == []

    def test_returns_targets_ordered_by_priority(self, mock_env_vars):
        """Test that targets are returned in priority order."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        targets_data = [
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 3,
                "service_id": 123,
                "type": "webhook",
                "config": {"url": "https://example.com/hook"},
                "priority": 2,
                "enabled": True
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            # Note: DB query already orders by priority, so we return in order
            mock_query.return_value = json.dumps(sorted(
                targets_data, key=lambda x: x["priority"]
            ))

            result = get_notification_targets_for_service(123)

            assert len(result) == 3
            assert result[0].target_id == 1  # priority 0
            assert result[1].target_id == 2  # priority 1
            assert result[2].target_id == 3  # priority 2

    def test_parses_target_types_correctly(self, mock_env_vars):
        """Test that notification types are parsed correctly."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationType
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
            {
                "target_id": 3,
                "service_id": 123,
                "type": "webhook",
                "config": {"url": "https://example.com"},
                "priority": 2,
                "enabled": True
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(123)

            assert result[0].target_type == NotificationType.SLACK
            assert result[1].target_type == NotificationType.PAGERDUTY
            assert result[2].target_type == NotificationType.WEBHOOK

    def test_parses_string_config_as_json(self, mock_env_vars):
        """Test that string config is parsed as JSON."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": '{"channel_id": "C123", "mention": "@here"}',
                "priority": 0,
                "enabled": True
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(123)

            assert result[0].config["channel_id"] == "C123"
            assert result[0].config["mention"] == "@here"

    def test_queries_enabled_targets_by_default(self, mock_env_vars):
        """Test that only enabled targets are queried by default."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            get_notification_targets_for_service(123)

            call_args = mock_query.call_args
            query = call_args[0][0]
            assert "enabled = TRUE" in query

    def test_queries_all_targets_when_enabled_only_false(self, mock_env_vars):
        """Test that all targets are queried when enabled_only=False."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            get_notification_targets_for_service(123, enabled_only=False)

            call_args = mock_query.call_args
            query = call_args[0][0]
            assert "enabled = TRUE" not in query


class TestRouteAlert:
    """Tests for route_alert function."""

    def test_returns_empty_when_no_targets(self, mock_env_vars):
        """Test that empty list is returned when no targets exist."""
        from Medic.Core.alert_routing import route_alert

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            results = route_alert(123, {"alert": "test"})

            assert results == []

    def test_notify_all_sends_to_all_targets(self, mock_env_vars):
        """Test that notify_all mode sends to all targets."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_ALL,
                sender=mock_sender
            )

            assert len(results) == 2
            assert len(calls) == 2
            assert 1 in calls
            assert 2 in calls

    def test_notify_all_continues_on_failure(self, mock_env_vars):
        """Test that notify_all continues even when a target fails."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            # First target fails, second succeeds
            return target.target_id != 1

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_ALL,
                sender=mock_sender
            )

            assert len(results) == 2
            assert len(calls) == 2
            assert results[0].success is False
            assert results[1].success is True

    def test_notify_until_success_stops_after_success(self, mock_env_vars):
        """Test that notify_until_success stops after first success."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True  # All succeed

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_UNTIL_SUCCESS,
                sender=mock_sender
            )

            # Only first target should be called
            assert len(results) == 1
            assert len(calls) == 1
            assert calls[0] == 1
            assert results[0].success is True

    def test_notify_until_success_tries_next_on_failure(self, mock_env_vars):
        """Test that notify_until_success tries next target on failure."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
            {
                "target_id": 3,
                "service_id": 123,
                "type": "webhook",
                "config": {"url": "https://example.com"},
                "priority": 2,
                "enabled": True
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            # Only target 2 succeeds
            return target.target_id == 2

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_UNTIL_SUCCESS,
                sender=mock_sender
            )

            # Should try 1 (fail), then 2 (success), stop
            assert len(results) == 2
            assert len(calls) == 2
            assert calls == [1, 2]
            assert results[0].success is False
            assert results[1].success is True

    def test_notify_until_success_tries_all_when_all_fail(self, mock_env_vars):
        """Test that notify_until_success tries all targets when all fail."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return False  # All fail

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_UNTIL_SUCCESS,
                sender=mock_sender
            )

            assert len(results) == 2
            assert len(calls) == 2
            assert all(not r.success for r in results)

    def test_handles_sender_exceptions(self, mock_env_vars):
        """Test that route_alert handles exceptions from sender."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True
            },
        ]

        def mock_sender(target, payload):
            if target.target_id == 1:
                raise Exception("Network error")
            return True

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_ALL,
                sender=mock_sender
            )

            assert len(results) == 2
            assert results[0].success is False
            assert "Network error" in results[0].error_message
            assert results[1].success is True

    def test_skips_disabled_targets(self, mock_env_vars):
        """Test that disabled targets are skipped with error result."""
        from Medic.Core.alert_routing import (
            route_alert, NotificationMode, NotificationTarget, NotificationType
        )

        # Override get_notification_targets to return disabled target
        targets = [
            NotificationTarget(
                target_id=1,
                service_id=123,
                target_type=NotificationType.SLACK,
                config={"channel_id": "C123"},
                priority=0,
                enabled=False  # Disabled
            ),
            NotificationTarget(
                target_id=2,
                service_id=123,
                target_type=NotificationType.PAGERDUTY,
                config={"service_key": "key123"},
                priority=1,
                enabled=True
            ),
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True

        with patch(
            "Medic.Core.alert_routing.get_notification_targets_for_service"
        ) as mock_get:
            mock_get.return_value = targets

            results = route_alert(
                123,
                {"alert": "test"},
                mode=NotificationMode.NOTIFY_ALL,
                sender=mock_sender
            )

            # Disabled target should have result but not be called
            assert len(results) == 2
            assert results[0].success is False
            assert "disabled" in results[0].error_message.lower()
            assert results[1].success is True
            # Only enabled target should be called
            assert calls == [2]


class TestNotificationModeEnum:
    """Tests for NotificationMode enum."""

    def test_notify_all_value(self):
        """Test NOTIFY_ALL enum value."""
        from Medic.Core.alert_routing import NotificationMode

        assert NotificationMode.NOTIFY_ALL.value == "notify_all"

    def test_notify_until_success_value(self):
        """Test NOTIFY_UNTIL_SUCCESS enum value."""
        from Medic.Core.alert_routing import NotificationMode

        assert NotificationMode.NOTIFY_UNTIL_SUCCESS.value == "notify_until_success"


class TestNotificationTypeEnum:
    """Tests for NotificationType enum."""

    def test_slack_value(self):
        """Test SLACK enum value."""
        from Medic.Core.alert_routing import NotificationType

        assert NotificationType.SLACK.value == "slack"

    def test_pagerduty_value(self):
        """Test PAGERDUTY enum value."""
        from Medic.Core.alert_routing import NotificationType

        assert NotificationType.PAGERDUTY.value == "pagerduty"

    def test_webhook_value(self):
        """Test WEBHOOK enum value."""
        from Medic.Core.alert_routing import NotificationType

        assert NotificationType.WEBHOOK.value == "webhook"


class TestHasNotificationTargets:
    """Tests for has_notification_targets function."""

    def test_returns_true_when_targets_exist(self, mock_env_vars):
        """Test that True is returned when targets exist."""
        from Medic.Core.alert_routing import has_notification_targets

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = has_notification_targets(123)

            assert result is True

    def test_returns_false_when_no_targets(self, mock_env_vars):
        """Test that False is returned when no targets exist."""
        from Medic.Core.alert_routing import has_notification_targets

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = has_notification_targets(123)

            assert result is False


class TestResultHelperFunctions:
    """Tests for result helper functions."""

    def test_get_successful_results(self):
        """Test filtering successful results."""
        from Medic.Core.alert_routing import (
            get_successful_results, NotificationResult, NotificationType
        )

        results = [
            NotificationResult(1, NotificationType.SLACK, True),
            NotificationResult(2, NotificationType.PAGERDUTY, False, "error"),
            NotificationResult(3, NotificationType.WEBHOOK, True),
        ]

        successful = get_successful_results(results)

        assert len(successful) == 2
        assert all(r.success for r in successful)
        assert [r.target_id for r in successful] == [1, 3]

    def test_get_failed_results(self):
        """Test filtering failed results."""
        from Medic.Core.alert_routing import (
            get_failed_results, NotificationResult, NotificationType
        )

        results = [
            NotificationResult(1, NotificationType.SLACK, True),
            NotificationResult(2, NotificationType.PAGERDUTY, False, "error"),
            NotificationResult(3, NotificationType.WEBHOOK, True),
        ]

        failed = get_failed_results(results)

        assert len(failed) == 1
        assert all(not r.success for r in failed)
        assert failed[0].target_id == 2

    def test_all_notifications_succeeded_true(self):
        """Test all_notifications_succeeded returns True when all succeed."""
        from Medic.Core.alert_routing import (
            all_notifications_succeeded, NotificationResult, NotificationType
        )

        results = [
            NotificationResult(1, NotificationType.SLACK, True),
            NotificationResult(2, NotificationType.PAGERDUTY, True),
        ]

        assert all_notifications_succeeded(results) is True

    def test_all_notifications_succeeded_false(self):
        """Test all_notifications_succeeded returns False when any fails."""
        from Medic.Core.alert_routing import (
            all_notifications_succeeded, NotificationResult, NotificationType
        )

        results = [
            NotificationResult(1, NotificationType.SLACK, True),
            NotificationResult(2, NotificationType.PAGERDUTY, False, "err"),
        ]

        assert all_notifications_succeeded(results) is False

    def test_all_notifications_succeeded_empty(self):
        """Test all_notifications_succeeded returns False for empty list."""
        from Medic.Core.alert_routing import all_notifications_succeeded

        assert all_notifications_succeeded([]) is False

    def test_any_notification_succeeded_true(self):
        """Test any_notification_succeeded returns True when one succeeds."""
        from Medic.Core.alert_routing import (
            any_notification_succeeded, NotificationResult, NotificationType
        )

        results = [
            NotificationResult(1, NotificationType.SLACK, False, "err"),
            NotificationResult(2, NotificationType.PAGERDUTY, True),
        ]

        assert any_notification_succeeded(results) is True

    def test_any_notification_succeeded_false(self):
        """Test any_notification_succeeded returns False when all fail."""
        from Medic.Core.alert_routing import (
            any_notification_succeeded, NotificationResult, NotificationType
        )

        results = [
            NotificationResult(1, NotificationType.SLACK, False, "err1"),
            NotificationResult(2, NotificationType.PAGERDUTY, False, "err2"),
        ]

        assert any_notification_succeeded(results) is False

    def test_any_notification_succeeded_empty(self):
        """Test any_notification_succeeded returns False for empty list."""
        from Medic.Core.alert_routing import any_notification_succeeded

        assert any_notification_succeeded([]) is False


class TestDefaultNotificationSender:
    """Tests for default_notification_sender function."""

    def test_slack_requires_channel_id(self, mock_env_vars):
        """Test Slack notification requires channel_id in config."""
        from Medic.Core.alert_routing import (
            default_notification_sender, NotificationTarget, NotificationType
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.SLACK,
            config={},  # Missing channel_id
            priority=0,
            enabled=True
        )

        result = default_notification_sender(target, {"alert": "test"})

        assert result is False

    def test_pagerduty_requires_service_key(self, mock_env_vars):
        """Test PagerDuty notification requires service_key in config."""
        from Medic.Core.alert_routing import (
            default_notification_sender, NotificationTarget, NotificationType
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.PAGERDUTY,
            config={},  # Missing service_key
            priority=0,
            enabled=True
        )

        result = default_notification_sender(target, {"alert": "test"})

        assert result is False

    def test_webhook_requires_url(self, mock_env_vars):
        """Test webhook notification requires url in config."""
        from Medic.Core.alert_routing import (
            default_notification_sender, NotificationTarget, NotificationType
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.WEBHOOK,
            config={},  # Missing url
            priority=0,
            enabled=True
        )

        result = default_notification_sender(target, {"alert": "test"})

        assert result is False

    def test_slack_returns_true_with_channel_id(self, mock_env_vars):
        """Test Slack notification returns True with valid config."""
        from Medic.Core.alert_routing import (
            default_notification_sender, NotificationTarget, NotificationType
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.SLACK,
            config={"channel_id": "C12345"},
            priority=0,
            enabled=True
        )

        result = default_notification_sender(target, {"alert": "test"})

        assert result is True

    def test_pagerduty_returns_true_with_service_key(self, mock_env_vars):
        """Test PagerDuty notification returns True with valid config."""
        from Medic.Core.alert_routing import (
            default_notification_sender, NotificationTarget, NotificationType
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.PAGERDUTY,
            config={"service_key": "abc123"},
            priority=0,
            enabled=True
        )

        result = default_notification_sender(target, {"alert": "test"})

        assert result is True

    def test_webhook_returns_true_with_url(self, mock_env_vars):
        """Test webhook notification returns True with valid config."""
        from Medic.Core.alert_routing import (
            default_notification_sender, NotificationTarget, NotificationType
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.WEBHOOK,
            config={"url": "https://example.com/webhook"},
            priority=0,
            enabled=True
        )

        result = default_notification_sender(target, {"alert": "test"})

        assert result is True


class TestNotificationPeriodEnum:
    """Tests for NotificationPeriod enum."""

    def test_always_value(self):
        """Test ALWAYS enum value."""
        from Medic.Core.alert_routing import NotificationPeriod

        assert NotificationPeriod.ALWAYS.value == "always"

    def test_during_hours_value(self):
        """Test DURING_HOURS enum value."""
        from Medic.Core.alert_routing import NotificationPeriod

        assert NotificationPeriod.DURING_HOURS.value == "during_hours"

    def test_after_hours_value(self):
        """Test AFTER_HOURS enum value."""
        from Medic.Core.alert_routing import NotificationPeriod

        assert NotificationPeriod.AFTER_HOURS.value == "after_hours"


class TestNotificationTargetPeriod:
    """Tests for NotificationTarget period field."""

    def test_default_period_is_always(self):
        """Test that default period is ALWAYS."""
        from Medic.Core.alert_routing import (
            NotificationTarget, NotificationType, NotificationPeriod
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.SLACK,
            config={"channel_id": "C123"},
            priority=0,
            enabled=True,
        )

        assert target.period == NotificationPeriod.ALWAYS

    def test_can_set_during_hours_period(self):
        """Test setting DURING_HOURS period."""
        from Medic.Core.alert_routing import (
            NotificationTarget, NotificationType, NotificationPeriod
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.SLACK,
            config={"channel_id": "C123"},
            priority=0,
            enabled=True,
            period=NotificationPeriod.DURING_HOURS,
        )

        assert target.period == NotificationPeriod.DURING_HOURS

    def test_can_set_after_hours_period(self):
        """Test setting AFTER_HOURS period."""
        from Medic.Core.alert_routing import (
            NotificationTarget, NotificationType, NotificationPeriod
        )

        target = NotificationTarget(
            target_id=1,
            service_id=123,
            target_type=NotificationType.SLACK,
            config={"channel_id": "C123"},
            priority=0,
            enabled=True,
            period=NotificationPeriod.AFTER_HOURS,
        )

        assert target.period == NotificationPeriod.AFTER_HOURS


class TestGetNotificationTargetsForServiceWithPeriod:
    """Tests for get_notification_targets_for_service with period filter."""

    def test_returns_always_targets_when_during_hours(self, mock_env_vars):
        """Test that 'always' targets are included during business hours."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationPeriod
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "always"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(
                123, period="during_hours"
            )

            assert len(result) == 1
            assert result[0].period == NotificationPeriod.ALWAYS

    def test_returns_during_hours_targets_when_during_hours(self, mock_env_vars):
        """Test that 'during_hours' targets are included during work hours."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationPeriod
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "during_hours"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(
                123, period="during_hours"
            )

            assert len(result) == 1
            assert result[0].period == NotificationPeriod.DURING_HOURS

    def test_returns_after_hours_targets_when_after_hours(self, mock_env_vars):
        """Test that 'after_hours' targets are included after work hours."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationPeriod
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 0,
                "enabled": True,
                "period": "after_hours"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(
                123, period="after_hours"
            )

            assert len(result) == 1
            assert result[0].period == NotificationPeriod.AFTER_HOURS

    def test_query_includes_period_filter(self, mock_env_vars):
        """Test that query filters by period."""
        from Medic.Core.alert_routing import get_notification_targets_for_service

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            get_notification_targets_for_service(123, period="during_hours")

            mock_query.assert_called_once()
            call_args = mock_query.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            # Query should filter by period
            assert "period" in query.lower()
            assert params == (123, "during_hours")

    def test_parses_period_from_database(self, mock_env_vars):
        """Test that period is parsed from database result."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationPeriod
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "during_hours"
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True,
                "period": "after_hours"
            },
            {
                "target_id": 3,
                "service_id": 123,
                "type": "webhook",
                "config": {"url": "https://example.com"},
                "priority": 2,
                "enabled": True,
                "period": "always"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(123)

            assert result[0].period == NotificationPeriod.DURING_HOURS
            assert result[1].period == NotificationPeriod.AFTER_HOURS
            assert result[2].period == NotificationPeriod.ALWAYS

    def test_defaults_to_always_when_period_missing(self, mock_env_vars):
        """Test that period defaults to ALWAYS when not in DB result."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationPeriod
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                # period is missing
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(123)

            assert len(result) == 1
            assert result[0].period == NotificationPeriod.ALWAYS

    def test_defaults_to_always_for_invalid_period(self, mock_env_vars):
        """Test that period defaults to ALWAYS for invalid values."""
        from Medic.Core.alert_routing import (
            get_notification_targets_for_service, NotificationPeriod
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "invalid_period"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_service(123)

            assert len(result) == 1
            assert result[0].period == NotificationPeriod.ALWAYS


class TestGetNotificationTargetsForPeriod:
    """Tests for get_notification_targets_for_period function."""

    def test_returns_targets_for_during_hours(self, mock_env_vars):
        """Test getting targets for during_hours period."""
        from Medic.Core.alert_routing import get_notification_targets_for_period

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "during_hours"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_period(123, "during_hours")

            assert len(result) == 1

    def test_returns_targets_for_after_hours(self, mock_env_vars):
        """Test getting targets for after_hours period."""
        from Medic.Core.alert_routing import get_notification_targets_for_period

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 0,
                "enabled": True,
                "period": "after_hours"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = get_notification_targets_for_period(123, "after_hours")

            assert len(result) == 1


class TestRouteAlertWithSchedule:
    """Tests for route_alert_with_schedule function."""

    def test_routes_to_during_hours_targets_during_work_hours(
        self, mock_env_vars
    ):
        """Test routing to during_hours targets during working hours."""
        from Medic.Core.alert_routing import (
            route_alert_with_schedule, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "during_hours"
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "during_hours"

                results = route_alert_with_schedule(
                    123,
                    {"alert": "test"},
                    mode=NotificationMode.NOTIFY_ALL,
                    sender=mock_sender
                )

                assert len(results) == 1
                assert results[0].success is True
                assert 1 in calls

    def test_routes_to_after_hours_targets_after_work_hours(self, mock_env_vars):
        """Test routing to after_hours targets outside working hours."""
        from Medic.Core.alert_routing import (
            route_alert_with_schedule, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 0,
                "enabled": True,
                "period": "after_hours"
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "after_hours"

                results = route_alert_with_schedule(
                    123,
                    {"alert": "test"},
                    mode=NotificationMode.NOTIFY_ALL,
                    sender=mock_sender
                )

                assert len(results) == 1
                assert results[0].success is True
                assert 1 in calls

    def test_includes_always_targets_during_work_hours(self, mock_env_vars):
        """Test that 'always' targets are included during working hours."""
        from Medic.Core.alert_routing import (
            route_alert_with_schedule, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "always"
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C456"},
                "priority": 1,
                "enabled": True,
                "period": "during_hours"
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "during_hours"

                results = route_alert_with_schedule(
                    123,
                    {"alert": "test"},
                    mode=NotificationMode.NOTIFY_ALL,
                    sender=mock_sender
                )

                assert len(results) == 2
                assert 1 in calls
                assert 2 in calls

    def test_includes_always_targets_after_work_hours(self, mock_env_vars):
        """Test that 'always' targets are included after working hours."""
        from Medic.Core.alert_routing import (
            route_alert_with_schedule, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "always"
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True,
                "period": "after_hours"
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "after_hours"

                results = route_alert_with_schedule(
                    123,
                    {"alert": "test"},
                    mode=NotificationMode.NOTIFY_ALL,
                    sender=mock_sender
                )

                assert len(results) == 2
                assert 1 in calls
                assert 2 in calls

    def test_uses_notify_until_success_mode(self, mock_env_vars):
        """Test notify_until_success mode with schedule."""
        from Medic.Core.alert_routing import (
            route_alert_with_schedule, NotificationMode
        )

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "always"
            },
            {
                "target_id": 2,
                "service_id": 123,
                "type": "pagerduty",
                "config": {"service_key": "key123"},
                "priority": 1,
                "enabled": True,
                "period": "always"
            },
        ]

        calls = []

        def mock_sender(target, payload):
            calls.append(target.target_id)
            return True  # First one succeeds

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "during_hours"

                results = route_alert_with_schedule(
                    123,
                    {"alert": "test"},
                    mode=NotificationMode.NOTIFY_UNTIL_SUCCESS,
                    sender=mock_sender
                )

                # Should stop after first success
                assert len(results) == 1
                assert len(calls) == 1
                assert calls[0] == 1

    def test_returns_empty_when_no_targets_for_period(self, mock_env_vars):
        """Test empty result when no targets for current period."""
        from Medic.Core.alert_routing import route_alert_with_schedule

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "after_hours"

                results = route_alert_with_schedule(123, {"alert": "test"})

                assert results == []

    def test_uses_check_time_parameter(self, mock_env_vars):
        """Test that check_time is passed to get_service_current_period."""
        from Medic.Core.alert_routing import route_alert_with_schedule
        from datetime import datetime

        check_time = datetime(2026, 1, 15, 10, 30)

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])
            with patch(
                "Medic.Core.working_hours.get_service_current_period"
            ) as mock_period:
                mock_period.return_value = "during_hours"

                route_alert_with_schedule(
                    123,
                    {"alert": "test"},
                    check_time=check_time
                )

                mock_period.assert_called_once_with(123, check_time)


class TestHasNotificationTargetsForPeriod:
    """Tests for has_notification_targets_for_period function."""

    def test_returns_true_when_targets_exist(self, mock_env_vars):
        """Test returns True when targets exist for period."""
        from Medic.Core.alert_routing import has_notification_targets_for_period

        targets_data = [
            {
                "target_id": 1,
                "service_id": 123,
                "type": "slack",
                "config": {"channel_id": "C123"},
                "priority": 0,
                "enabled": True,
                "period": "during_hours"
            },
        ]

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps(targets_data)

            result = has_notification_targets_for_period(123, "during_hours")

            assert result is True

    def test_returns_false_when_no_targets(self, mock_env_vars):
        """Test returns False when no targets exist for period."""
        from Medic.Core.alert_routing import has_notification_targets_for_period

        with patch("Medic.Core.alert_routing.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = has_notification_targets_for_period(123, "after_hours")

            assert result is False

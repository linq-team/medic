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

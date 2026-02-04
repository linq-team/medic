"""Unit tests for playbook_triggers module."""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestPlaybookTrigger:
    """Tests for PlaybookTrigger dataclass."""

    def test_trigger_creation(self):
        """Test creating a PlaybookTrigger object."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.trigger_id == 1
        assert trigger.playbook_id == 100
        assert trigger.service_pattern == "worker-*"
        assert trigger.consecutive_failures == 3
        assert trigger.enabled is True

    def test_trigger_to_dict(self):
        """Test converting trigger to dictionary."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        result = trigger.to_dict()

        assert result["trigger_id"] == 1
        assert result["playbook_id"] == 100
        assert result["service_pattern"] == "worker-*"
        assert result["consecutive_failures"] == 3
        assert result["enabled"] is True


class TestGlobPatternMatching:
    """Tests for glob pattern matching on triggers."""

    def test_matches_exact_name(self):
        """Test exact service name match."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-prod-01",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-prod-01") is True
        assert trigger.matches_service("worker-prod-02") is False

    def test_matches_star_wildcard(self):
        """Test asterisk wildcard matching."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-prod-01") is True
        assert trigger.matches_service("worker-staging") is True
        assert trigger.matches_service("worker-") is True
        assert trigger.matches_service("api-prod") is False

    def test_matches_double_star_pattern(self):
        """Test pattern with wildcards on both sides."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="*-prod-*",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-prod-01") is True
        assert trigger.matches_service("api-prod-us-east") is True
        assert trigger.matches_service("prod") is False
        assert trigger.matches_service("worker-staging-01") is False

    def test_matches_question_mark_wildcard(self):
        """Test question mark single character wildcard."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-0?",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-01") is True
        assert trigger.matches_service("worker-02") is True
        assert trigger.matches_service("worker-10") is False
        assert trigger.matches_service("worker-0") is False

    def test_matches_all_services_star(self):
        """Test '*' pattern matches all services."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="*",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-prod-01") is True
        assert trigger.matches_service("api-server") is True
        assert trigger.matches_service("anything") is True

    def test_matches_case_insensitive(self):
        """Test pattern matching is case insensitive."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="Worker-*",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-prod") is True
        assert trigger.matches_service("WORKER-PROD") is True
        assert trigger.matches_service("Worker-Prod") is True

    def test_matches_character_class(self):
        """Test character class pattern matching."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-[0-9]*",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("worker-01") is True
        assert trigger.matches_service("worker-9abc") is True
        assert trigger.matches_service("worker-abc") is False

    def test_matches_empty_service_name(self):
        """Test matching with empty service name returns False."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="*",
            consecutive_failures=1,
            enabled=True,
        )

        assert trigger.matches_service("") is False
        assert trigger.matches_service(None) is False  # type: ignore


class TestFailureThreshold:
    """Tests for failure threshold checking."""

    def test_meets_exact_threshold(self):
        """Test meeting exact failure threshold."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.meets_failure_threshold(3) is True

    def test_meets_exceeded_threshold(self):
        """Test exceeding failure threshold."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.meets_failure_threshold(5) is True

    def test_does_not_meet_threshold(self):
        """Test not meeting failure threshold."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.meets_failure_threshold(2) is False
        assert trigger.meets_failure_threshold(1) is False
        assert trigger.meets_failure_threshold(0) is False


class TestTriggerMatches:
    """Tests for combined trigger matching (service + failures)."""

    def test_matches_both_conditions(self):
        """Test matching when both conditions are met."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.matches("worker-prod-01", 3) is True
        assert trigger.matches("worker-prod-01", 5) is True

    def test_matches_fails_on_service_mismatch(self):
        """Test matching fails when service doesn't match."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.matches("api-prod", 5) is False

    def test_matches_fails_on_threshold_not_met(self):
        """Test matching fails when failure threshold not met."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        assert trigger.matches("worker-prod-01", 2) is False

    def test_matches_fails_when_disabled(self):
        """Test matching fails when trigger is disabled."""
        from Medic.Core.playbook_triggers import PlaybookTrigger

        trigger = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=False,
        )

        assert trigger.matches("worker-prod-01", 5) is False


class TestMatchedPlaybook:
    """Tests for MatchedPlaybook dataclass."""

    def test_matched_playbook_creation(self):
        """Test creating a MatchedPlaybook object."""
        from Medic.Core.playbook_triggers import MatchedPlaybook

        matched = MatchedPlaybook(
            playbook_id=100,
            playbook_name="restart-service",
            trigger_id=1,
            service_pattern="worker-*",
            consecutive_failures=3,
        )

        assert matched.playbook_id == 100
        assert matched.playbook_name == "restart-service"
        assert matched.trigger_id == 1
        assert matched.service_pattern == "worker-*"
        assert matched.consecutive_failures == 3

    def test_matched_playbook_to_dict(self):
        """Test converting MatchedPlaybook to dictionary."""
        from Medic.Core.playbook_triggers import MatchedPlaybook

        matched = MatchedPlaybook(
            playbook_id=100,
            playbook_name="restart-service",
            trigger_id=1,
            service_pattern="worker-*",
            consecutive_failures=3,
        )

        result = matched.to_dict()

        assert result["playbook_id"] == 100
        assert result["playbook_name"] == "restart-service"
        assert result["trigger_id"] == 1
        assert result["service_pattern"] == "worker-*"
        assert result["consecutive_failures"] == 3


class TestGetEnabledTriggers:
    """Tests for get_enabled_triggers function."""

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_empty_list_when_no_triggers(self, mock_query_db):
        """Test returns empty list when no triggers exist."""
        from Medic.Core.playbook_triggers import get_enabled_triggers

        mock_query_db.return_value = '[]'

        result = get_enabled_triggers()

        assert result == []
        mock_query_db.assert_called_once()

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_triggers_ordered_by_failures_desc(self, mock_query_db):
        """Test triggers are returned ordered by consecutive_failures DESC."""
        from Medic.Core.playbook_triggers import get_enabled_triggers

        mock_query_db.return_value = json.dumps([
            {
                "trigger_id": 1,
                "playbook_id": 100,
                "service_pattern": "worker-*",
                "consecutive_failures": 5,
                "enabled": True
            },
            {
                "trigger_id": 2,
                "playbook_id": 101,
                "service_pattern": "*",
                "consecutive_failures": 1,
                "enabled": True
            },
        ])

        result = get_enabled_triggers()

        assert len(result) == 2
        assert result[0].consecutive_failures == 5
        assert result[1].consecutive_failures == 1


class TestFindMatchingTrigger:
    """Tests for find_matching_trigger function."""

    @patch("Medic.Core.playbook_triggers.get_enabled_triggers")
    def test_finds_matching_trigger(self, mock_get_triggers):
        """Test finding a matching trigger."""
        from Medic.Core.playbook_triggers import (
            PlaybookTrigger,
            find_matching_trigger,
        )

        mock_get_triggers.return_value = [
            PlaybookTrigger(
                trigger_id=1,
                playbook_id=100,
                service_pattern="worker-*",
                consecutive_failures=3,
                enabled=True,
            ),
        ]

        result = find_matching_trigger("worker-prod-01", 3)

        assert result is not None
        assert result.trigger_id == 1

    @patch("Medic.Core.playbook_triggers.get_enabled_triggers")
    def test_returns_none_when_no_match(self, mock_get_triggers):
        """Test returns None when no trigger matches."""
        from Medic.Core.playbook_triggers import (
            PlaybookTrigger,
            find_matching_trigger,
        )

        mock_get_triggers.return_value = [
            PlaybookTrigger(
                trigger_id=1,
                playbook_id=100,
                service_pattern="worker-*",
                consecutive_failures=3,
                enabled=True,
            ),
        ]

        result = find_matching_trigger("api-prod", 5)

        assert result is None

    @patch("Medic.Core.playbook_triggers.get_enabled_triggers")
    def test_returns_most_specific_trigger_first(self, mock_get_triggers):
        """Test returns trigger with highest failure threshold first."""
        from Medic.Core.playbook_triggers import (
            PlaybookTrigger,
            find_matching_trigger,
        )

        mock_get_triggers.return_value = [
            PlaybookTrigger(
                trigger_id=2,
                playbook_id=101,
                service_pattern="worker-*",
                consecutive_failures=5,
                enabled=True,
            ),
            PlaybookTrigger(
                trigger_id=1,
                playbook_id=100,
                service_pattern="*",
                consecutive_failures=1,
                enabled=True,
            ),
        ]

        # With 5 failures, should match the more specific trigger first
        result = find_matching_trigger("worker-prod-01", 5)

        assert result is not None
        assert result.trigger_id == 2
        assert result.consecutive_failures == 5

    @patch("Medic.Core.playbook_triggers.get_enabled_triggers")
    def test_falls_through_to_less_specific_trigger(self, mock_get_triggers):
        """Test falls through to less specific trigger when appropriate."""
        from Medic.Core.playbook_triggers import (
            PlaybookTrigger,
            find_matching_trigger,
        )

        mock_get_triggers.return_value = [
            PlaybookTrigger(
                trigger_id=2,
                playbook_id=101,
                service_pattern="worker-*",
                consecutive_failures=5,
                enabled=True,
            ),
            PlaybookTrigger(
                trigger_id=1,
                playbook_id=100,
                service_pattern="*",
                consecutive_failures=1,
                enabled=True,
            ),
        ]

        # With only 2 failures, the 5-failure trigger won't match
        # but the 1-failure catch-all should
        result = find_matching_trigger("worker-prod-01", 2)

        assert result is not None
        assert result.trigger_id == 1
        assert result.consecutive_failures == 1


class TestFindPlaybookForAlert:
    """Tests for find_playbook_for_alert function."""

    @patch("Medic.Core.playbook_triggers.db.query_db")
    @patch("Medic.Core.playbook_triggers.find_matching_trigger")
    def test_finds_playbook_for_matching_trigger(
        self, mock_find_trigger, mock_query_db
    ):
        """Test finding playbook when trigger matches."""
        from Medic.Core.playbook_triggers import (
            PlaybookTrigger,
            find_playbook_for_alert,
        )

        mock_find_trigger.return_value = PlaybookTrigger(
            trigger_id=1,
            playbook_id=100,
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        mock_query_db.return_value = json.dumps([
            {"playbook_id": 100, "name": "restart-service"}
        ])

        result = find_playbook_for_alert("worker-prod-01", 3)

        assert result is not None
        assert result.playbook_id == 100
        assert result.playbook_name == "restart-service"
        assert result.trigger_id == 1

    @patch("Medic.Core.playbook_triggers.find_matching_trigger")
    def test_returns_none_when_no_trigger_matches(self, mock_find_trigger):
        """Test returns None when no trigger matches."""
        from Medic.Core.playbook_triggers import find_playbook_for_alert

        mock_find_trigger.return_value = None

        result = find_playbook_for_alert("api-prod", 5)

        assert result is None

    @patch("Medic.Core.playbook_triggers.db.query_db")
    @patch("Medic.Core.playbook_triggers.find_matching_trigger")
    def test_returns_none_when_playbook_not_found(
        self, mock_find_trigger, mock_query_db
    ):
        """Test returns None when trigger's playbook doesn't exist."""
        from Medic.Core.playbook_triggers import (
            PlaybookTrigger,
            find_playbook_for_alert,
        )

        mock_find_trigger.return_value = PlaybookTrigger(
            trigger_id=1,
            playbook_id=999,  # Non-existent playbook
            service_pattern="worker-*",
            consecutive_failures=3,
            enabled=True,
        )

        mock_query_db.return_value = '[]'

        result = find_playbook_for_alert("worker-prod-01", 3)

        assert result is None


class TestGetConsecutiveFailuresForService:
    """Tests for get_consecutive_failures_for_service function."""

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_failure_count(self, mock_query_db):
        """Test returns correct failure count."""
        from Medic.Core.playbook_triggers import (
            get_consecutive_failures_for_service,
        )

        mock_query_db.return_value = json.dumps([
            {"consecutive_failures": 5}
        ])

        result = get_consecutive_failures_for_service(123)

        assert result == 5

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_zero_when_not_found(self, mock_query_db):
        """Test returns 0 when service not found."""
        from Medic.Core.playbook_triggers import (
            get_consecutive_failures_for_service,
        )

        mock_query_db.return_value = '[]'

        result = get_consecutive_failures_for_service(999)

        assert result == 0

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_zero_when_null(self, mock_query_db):
        """Test returns 0 when consecutive_failures is null."""
        from Medic.Core.playbook_triggers import (
            get_consecutive_failures_for_service,
        )

        mock_query_db.return_value = json.dumps([
            {"consecutive_failures": None}
        ])

        result = get_consecutive_failures_for_service(123)

        assert result == 0


class TestGetServiceNameById:
    """Tests for get_service_name_by_id function."""

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_service_name(self, mock_query_db):
        """Test returns correct service name."""
        from Medic.Core.playbook_triggers import get_service_name_by_id

        mock_query_db.return_value = json.dumps([
            {"name": "worker-prod-01"}
        ])

        result = get_service_name_by_id(123)

        assert result == "worker-prod-01"

    @patch("Medic.Core.playbook_triggers.db.query_db")
    def test_returns_none_when_not_found(self, mock_query_db):
        """Test returns None when service not found."""
        from Medic.Core.playbook_triggers import get_service_name_by_id

        mock_query_db.return_value = '[]'

        result = get_service_name_by_id(999)

        assert result is None


class TestFindPlaybookForServiceAlert:
    """Tests for find_playbook_for_service_alert function."""

    @patch("Medic.Core.playbook_triggers.find_playbook_for_alert")
    @patch("Medic.Core.playbook_triggers.get_consecutive_failures_for_service")
    @patch("Medic.Core.playbook_triggers.get_service_name_by_id")
    def test_finds_playbook_using_service_id(
        self,
        mock_get_name,
        mock_get_failures,
        mock_find_playbook,
    ):
        """Test finding playbook using service ID."""
        from Medic.Core.playbook_triggers import (
            MatchedPlaybook,
            find_playbook_for_service_alert,
        )

        mock_get_name.return_value = "worker-prod-01"
        mock_get_failures.return_value = 3
        mock_find_playbook.return_value = MatchedPlaybook(
            playbook_id=100,
            playbook_name="restart-service",
            trigger_id=1,
            service_pattern="worker-*",
            consecutive_failures=3,
        )

        result = find_playbook_for_service_alert(123)

        assert result is not None
        assert result.playbook_id == 100
        mock_get_name.assert_called_once_with(123)
        mock_get_failures.assert_called_once_with(123)
        mock_find_playbook.assert_called_once_with("worker-prod-01", 3)

    @patch("Medic.Core.playbook_triggers.get_service_name_by_id")
    def test_returns_none_when_service_not_found(self, mock_get_name):
        """Test returns None when service doesn't exist."""
        from Medic.Core.playbook_triggers import find_playbook_for_service_alert

        mock_get_name.return_value = None

        result = find_playbook_for_service_alert(999)

        assert result is None


class TestMatchesGlobPattern:
    """Tests for matches_glob_pattern utility function."""

    def test_matches_simple_pattern(self):
        """Test simple glob pattern matching."""
        from Medic.Core.playbook_triggers import matches_glob_pattern

        assert matches_glob_pattern("worker-*", "worker-prod") is True
        assert matches_glob_pattern("worker-*", "api-prod") is False

    def test_matches_case_insensitive(self):
        """Test case insensitive matching."""
        from Medic.Core.playbook_triggers import matches_glob_pattern

        assert matches_glob_pattern("Worker-*", "worker-prod") is True
        assert matches_glob_pattern("worker-*", "WORKER-PROD") is True

    def test_returns_false_for_empty_inputs(self):
        """Test returns False for empty inputs."""
        from Medic.Core.playbook_triggers import matches_glob_pattern

        assert matches_glob_pattern("", "value") is False
        assert matches_glob_pattern("pattern", "") is False
        assert matches_glob_pattern("", "") is False


class TestTriggerParsing:
    """Tests for _parse_trigger function."""

    def test_parses_trigger_data(self):
        """Test parsing trigger data from database."""
        from Medic.Core.playbook_triggers import _parse_trigger

        data = {
            "trigger_id": 1,
            "playbook_id": 100,
            "service_pattern": "worker-*",
            "consecutive_failures": 3,
            "enabled": True,
        }

        result = _parse_trigger(data)

        assert result.trigger_id == 1
        assert result.playbook_id == 100
        assert result.service_pattern == "worker-*"
        assert result.consecutive_failures == 3
        assert result.enabled is True

    def test_defaults_for_missing_fields(self):
        """Test defaults are applied for missing fields."""
        from Medic.Core.playbook_triggers import _parse_trigger

        data = {
            "trigger_id": 1,
            "playbook_id": 100,
            "service_pattern": "*",
        }

        result = _parse_trigger(data)

        assert result.consecutive_failures == 1  # Default
        assert result.enabled is True  # Default

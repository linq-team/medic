"""
Configuration management for Medic.

This module provides centralized configuration with environment variable
validation and sensible defaults.
"""
import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str
    port: int
    name: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            name=os.environ.get("DB_NAME", "medic"),
            user=os.environ.get("PG_USER", ""),
            password=os.environ.get("PG_PASS", ""),
        )

    def validate(self) -> list:
        """Validate configuration. Returns list of error messages."""
        errors = []
        if not self.host:
            errors.append("DB_HOST is required")
        if not self.name:
            errors.append("DB_NAME is required")
        if not self.user:
            errors.append("PG_USER is required")
        if not self.password:
            errors.append("PG_PASS is required")
        return errors


@dataclass
class SlackConfig:
    """Slack configuration."""
    api_token: str
    channel_id: str

    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Create configuration from environment variables."""
        return cls(
            api_token=os.environ.get("SLACK_API_TOKEN", ""),
            channel_id=os.environ.get("SLACK_CHANNEL_ID", ""),
        )

    def validate(self) -> list:
        """Validate configuration. Returns list of error messages."""
        errors = []
        if not self.api_token:
            errors.append("SLACK_API_TOKEN is required")
        if not self.channel_id:
            errors.append("SLACK_CHANNEL_ID is required")
        return errors

    @property
    def is_configured(self) -> bool:
        """Check if Slack is fully configured."""
        return bool(self.api_token and self.channel_id)


@dataclass
class PagerDutyConfig:
    """PagerDuty configuration."""
    routing_key: str

    @classmethod
    def from_env(cls) -> "PagerDutyConfig":
        """Create configuration from environment variables."""
        return cls(
            routing_key=os.environ.get("PAGERDUTY_ROUTING_KEY", ""),
        )

    def validate(self) -> list:
        """Validate configuration. Returns list of error messages."""
        errors = []
        if not self.routing_key:
            errors.append("PAGERDUTY_ROUTING_KEY is required")
        return errors

    @property
    def is_configured(self) -> bool:
        """Check if PagerDuty is fully configured."""
        return bool(self.routing_key)


@dataclass
class AppConfig:
    """Application configuration."""
    port: int
    base_url: str
    debug: bool
    timezone: str

    # Worker settings
    worker_interval_seconds: int
    alert_auto_unmute_hours: int

    # Retention settings
    heartbeat_retention_days: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        return cls(
            port=int(os.environ.get("PORT", "5000")),
            base_url=os.environ.get("MEDIC_BASE_URL", "http://localhost:5000"),
            debug=os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"),
            timezone=os.environ.get("MEDIC_TIMEZONE", "America/Chicago"),
            worker_interval_seconds=int(os.environ.get("WORKER_INTERVAL_SECONDS", "15")),
            alert_auto_unmute_hours=int(os.environ.get("ALERT_AUTO_UNMUTE_HOURS", "24")),
            heartbeat_retention_days=int(os.environ.get("HEARTBEAT_RETENTION_DAYS", "30")),
        )

    def validate(self) -> list:
        """Validate configuration. Returns list of error messages."""
        errors = []
        if self.port < 1 or self.port > 65535:
            errors.append(f"PORT must be between 1 and 65535, got {self.port}")
        if self.worker_interval_seconds < 1:
            errors.append("WORKER_INTERVAL_SECONDS must be at least 1")
        if self.heartbeat_retention_days < 1:
            errors.append("HEARTBEAT_RETENTION_DAYS must be at least 1")
        return errors


@dataclass
class Config:
    """Complete application configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig.from_env)
    slack: SlackConfig = field(default_factory=SlackConfig.from_env)
    pagerduty: PagerDutyConfig = field(default_factory=PagerDutyConfig.from_env)
    app: AppConfig = field(default_factory=AppConfig.from_env)

    @classmethod
    def from_env(cls) -> "Config":
        """Create complete configuration from environment variables."""
        return cls(
            database=DatabaseConfig.from_env(),
            slack=SlackConfig.from_env(),
            pagerduty=PagerDutyConfig.from_env(),
            app=AppConfig.from_env(),
        )

    def validate(self, strict: bool = False) -> list:
        """
        Validate all configuration.

        Args:
            strict: If True, require all integrations to be configured.
                   If False, only require database and app config.

        Returns:
            List of error messages.
        """
        errors = []
        errors.extend(self.database.validate())
        errors.extend(self.app.validate())

        if strict:
            errors.extend(self.slack.validate())
            errors.extend(self.pagerduty.validate())

        return errors

    def validate_or_exit(self, strict: bool = False):
        """
        Validate configuration and exit if invalid.

        Args:
            strict: If True, require all integrations to be configured.
        """
        errors = self.validate(strict=strict)
        if errors:
            logger.critical("Configuration validation failed:")
            for error in errors:
                logger.critical(f"  - {error}")
            sys.exit(1)

    def log_config(self):
        """Log configuration (without sensitive values)."""
        logger.info("Configuration loaded:")
        logger.info(f"  Database: {self.database.host}:{self.database.port}/{self.database.name}")
        logger.info(f"  App Port: {self.app.port}")
        logger.info(f"  Base URL: {self.app.base_url}")
        logger.info(f"  Timezone: {self.app.timezone}")
        logger.info(f"  Slack: {'configured' if self.slack.is_configured else 'not configured'}")
        logger.info(f"  PagerDuty: {'configured' if self.pagerduty.is_configured else 'not configured'}")


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global _config
    _config = Config.from_env()
    return _config


# Constants that were previously hardcoded
class Constants:
    """Application constants."""

    # HTTP status codes
    HTTP_OK = 200
    HTTP_CREATED = 201
    HTTP_NO_CONTENT = 204
    HTTP_BAD_REQUEST = 400
    HTTP_NOT_FOUND = 404
    HTTP_INTERNAL_ERROR = 500
    HTTP_SERVICE_UNAVAILABLE = 503

    # Database
    DEFAULT_MAX_HEARTBEATS = 250
    DEFAULT_MAX_ALERTS = 100

    # Worker
    WORKER_INTERVAL_SECONDS = 15
    ALERT_CYCLE_DIVISOR = 15  # For calculating notification intervals
    AUTO_UNMUTE_CYCLES = 1440 // 15  # 24 hours / 15 seconds

    # Priority colors (for Slack)
    PRIORITY_COLORS = {
        "p1": "#F35A00",
        "p2": "#e9a820",
        "p3": "#e9a820",
    }
    DEFAULT_PRIORITY_COLOR = "#F35A00"

    # Default values
    DEFAULT_TEAM = "site-reliability"
    DEFAULT_PRIORITY = "p3"
    DEFAULT_THRESHOLD = 1

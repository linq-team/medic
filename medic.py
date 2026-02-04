"""
Medic - Heartbeat Monitoring Service

A Flask-based service for tracking service health through heartbeat monitoring.
"""
import os
import logging
from flask import Flask

import Medic.Core.routes
from Medic.Core.telemetry import init_telemetry
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder=os.path.abspath('Medic/Docs'))

    # Load configuration
    config = get_config()

    # Validate configuration (non-strict for web server)
    errors = config.validate(strict=False)
    if errors:
        for error in errors:
            logger.warning(f"Configuration warning: {error}")

    # Initialize OpenTelemetry instrumentation
    telemetry_enabled = os.environ.get("OTEL_ENABLED", "true").lower() == "true"
    if telemetry_enabled:
        init_telemetry(app)

    # Register routes
    Medic.Core.routes.exposeRoutes(app)

    logger.info("Medic web server initialized")
    logger.info(f"Base URL: {config.app.base_url}")

    return app


# Create the application instance
app = create_app()

if __name__ == "__main__":
    config = get_config()
    config.log_config()

    logger.info(f"Starting Medic on port {config.app.port}")
    app.run(host='0.0.0.0', port=config.app.port, debug=config.app.debug)

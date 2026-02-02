# Contributing to Medic

## Development Setup

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- PostgreSQL 16 (or use Docker)
- Node.js 18+ (for TypeScript client development)

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/linq-team/medic.git
   cd medic
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

5. **Start database**
   ```bash
   docker-compose up -d db
   ```

6. **Run the application**
   ```bash
   python medic.py
   ```

### Using Docker Compose

For a complete local environment:

```bash
docker-compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- Medic web server (port 5000)
- Medic worker

---

## Development Workflow

### Branch Naming

- `feature/<description>` - New features
- `fix/<description>` - Bug fixes
- `refactor/<description>` - Code refactoring
- `docs/<description>` - Documentation changes

### Commit Messages

Follow conventional commits:

```
type(scope): short description

Longer description if needed.

Co-Authored-By: Your Name <your.email@example.com>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Requests

1. Create feature branch from `main`
2. Make changes with tests
3. Run linting and tests locally
4. Open PR with description of changes
5. Request review from maintainers

---

## Available Scripts

### Running the Application

```bash
# Web server
python medic.py

# Worker (in separate terminal)
python Medic/Worker/monitor.py
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=Medic --cov-report=html

# Run specific test categories
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest tests/e2e/                     # End-to-end tests only
pytest -m "not integration"           # Skip integration tests

# Run tests in Docker
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

### Code Quality

```bash
# Format code
black Medic/ tests/
isort Medic/ tests/

# Lint code
flake8 Medic/ tests/

# Type checking
mypy Medic/

# Run all checks
black --check Medic/ tests/ && isort --check Medic/ tests/ && flake8 Medic/ tests/ && mypy Medic/
```

### CLI Tool

```bash
# Install CLI for development
pip install -e cli/

# Or run directly
python cli/medic_cli.py --help

# Example commands
medic-cli service list
medic-cli health
medic-cli heartbeat send my-service
```

### TypeScript Client

```bash
cd Medic/clients/typescript

# Install dependencies
npm install

# Build
npm run build

# Run tests
npm test

# Lint
npm run lint
```

---

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests (no external dependencies)
│   ├── test_heartbeat.py
│   ├── test_routes.py
│   └── test_database.py
├── integration/         # Tests with real database
│   ├── test_api.py
│   └── test_worker.py
└── e2e/                 # Full system tests
    └── test_full_flow.py
```

### Writing Tests

```python
import pytest
from unittest.mock import MagicMock, patch

class TestHeartbeatEndpoint:
    """Group related tests in classes."""

    def test_post_heartbeat_success(self, client, mock_db):
        """Use descriptive test names."""
        # Arrange
        mock_db.query_db.return_value = '[{"id": 1}]'

        # Act
        response = client.post('/heartbeat', json={'name': 'test'})

        # Assert
        assert response.status_code == 201
```

### Fixtures

Common fixtures are defined in `tests/conftest.py`:

- `app` - Flask application instance
- `client` - Flask test client
- `mock_db` - Mocked database connection
- `mock_env_vars` - Test environment variables
- `mock_slack` - Mocked Slack client
- `mock_pagerduty` - Mocked PagerDuty client

### Coverage Requirements

- Target: **80%+ code coverage**
- All new features require tests
- Bug fixes should include regression tests

---

## Code Style

### Python

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use `black` for formatting, `isort` for imports

```python
def query_db(
    query: str,
    params: Optional[Tuple] = None,
    show_columns: bool = True,
) -> str:
    """
    Execute a database query.

    Args:
        query: SQL query string with %s placeholders
        params: Query parameters (prevents SQL injection)
        show_columns: Include column names in response

    Returns:
        JSON string of query results
    """
    ...
```

### TypeScript

- Use TypeScript strict mode
- Export types for public interfaces
- Use async/await over callbacks

---

## Database Migrations

Currently, schema changes are managed manually. When modifying the database:

1. Update `Medic/Docs/schema.sql` (if it exists)
2. Create migration script in `migrations/` (optional)
3. Document changes in PR description
4. Test with fresh database

---

## Debugging

### Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Detailed debugging info")
logger.info("General information")
logger.warning("Something unexpected")
logger.error("Error occurred", exc_info=True)
```

### Environment Variables

```bash
# Enable debug mode
DEBUG=true python medic.py
```

### Database Queries

```bash
# Connect to local database
psql -h localhost -U medic -d medic

# View recent heartbeats
SELECT * FROM "heartbeatEvents" ORDER BY time DESC LIMIT 10;
```

---

## Release Process

1. Update version in relevant files
2. Update CHANGELOG.md
3. Create PR for release
4. After merge, tag release: `git tag v1.x.x`
5. Push tags: `git push --tags`
6. Build and push Docker image

---

## Getting Help

- **Documentation:** `docs/` directory
- **Issues:** https://github.com/linq-team/medic/issues
- **Slack:** #medic-dev

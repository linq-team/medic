# Contributing to Medic

## Development Setup

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- PostgreSQL 16 (or use Docker)
- Redis 7+ (or use Docker)
- Node.js 18+ (for UI and TypeScript client development)

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
   pip install -r Medic/requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

5. **Start database and Redis**
   ```bash
   docker-compose up -d db redis
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
- Redis cache (port 6379)
- Medic web server (port 8080)
- Medic worker

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | Yes | - | PostgreSQL host |
| `DB_PORT` | No | 5432 | PostgreSQL port |
| `DB_NAME` | Yes | - | PostgreSQL database name |
| `PG_USER` | Yes | - | PostgreSQL username |
| `PG_PASS` | Yes | - | PostgreSQL password |
| `PORT` | No | 8080 | Web server port |
| `DEBUG` | No | false | Debug mode |
| `MEDIC_BASE_URL` | No | http://localhost:8080 | Base URL for links |
| `MEDIC_TIMEZONE` | No | America/Chicago | Timezone for scheduling |
| `LOG_LEVEL` | No | INFO | Logging level |
| `WORKER_INTERVAL_SECONDS` | No | 15 | Heartbeat check interval |
| `REDIS_URL` | Conditional | - | Redis connection URL |
| `MEDIC_RATE_LIMITER_TYPE` | No | auto | Rate limiter: auto/redis/memory |
| `SLACK_API_TOKEN` | No | - | Slack Bot token |
| `SLACK_CHANNEL_ID` | No | - | Slack channel for notifications |
| `SLACK_SIGNING_SECRET` | No | - | Slack webhook signature verification |
| `PAGERDUTY_ROUTING_KEY` | No | - | PagerDuty Events API routing key |
| `MEDIC_SECRETS_KEY` | Prod | - | AES-256 key for encrypting secrets |
| `MEDIC_WEBHOOK_SECRET` | Prod | - | Secret for webhook signature validation |

See `.env.example` for a complete template.

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

### Backend (Python)

| Command | Description |
|---------|-------------|
| `python medic.py` | Start web server |
| `python Medic/Worker/monitor.py` | Start worker process |
| `pytest` | Run all tests |
| `pytest --cov=Medic --cov-report=html` | Run tests with coverage |
| `pytest tests/unit/` | Run unit tests only |
| `pytest tests/integration/` | Run integration tests only |
| `black Medic/ tests/` | Format code |
| `isort Medic/ tests/` | Sort imports |
| `flake8 Medic/ tests/` | Lint code |
| `mypy Medic/` | Type checking |

### UI (React/TypeScript)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production (tsc + vite) |
| `npm run test` | Run tests (vitest) |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Run ESLint with auto-fix |
| `npm run format` | Format with Prettier |
| `npm run preview` | Preview production build |
| `npm run typecheck` | TypeScript type checking |

### TypeScript Client

| Command | Description |
|---------|-------------|
| `npm run build` | Build all formats (CJS, ESM, types) |
| `npm run build:cjs` | Build CommonJS |
| `npm run build:esm` | Build ES Modules |
| `npm run build:types` | Build type declarations |
| `npm run clean` | Remove dist/ |
| `npm test` | Run tests (Jest) |

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

### TypeScript/React

- Use TypeScript strict mode
- Export types for public interfaces
- Use async/await over callbacks
- Follow React hooks best practices

---

## Dependencies

### Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| flask | >=3.0.0 | Web framework |
| psycopg2-binary | >=2.9.9 | PostgreSQL driver |
| slack-sdk | >=3.26.0 | Slack integration |
| requests | >=2.31.0 | HTTP client |
| prometheus-client | >=0.19.0 | Metrics |
| argon2-cffi | >=23.1.0 | API key hashing |
| croniter | >=2.0.0 | Cron expression parsing |
| PyYAML | >=6.0 | YAML parsing |
| cryptography | >=42.0.0 | Secrets encryption |

### UI Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^19.2.0 | UI framework |
| @tanstack/react-query | ^5.90.20 | Server state |
| react-router-dom | ^6.30.3 | Routing |
| @radix-ui/* | Various | UI primitives |
| tailwindcss | ^4.1.18 | Styling |
| vite | ^7.2.4 | Build tool |
| vitest | ^4.0.18 | Testing |

---

## Database Migrations

Schema changes are managed via SQL migration files in `migrations/`:

```
migrations/
├── 001_create_api_keys.sql
├── 002_create_webhooks.sql
├── 003_create_teams.sql
├── ...
└── 016_create_secrets.sql
```

When modifying the database:

1. Create new migration file with next sequence number
2. Write idempotent SQL (use `IF NOT EXISTS` where possible)
3. Test with fresh database
4. Document changes in PR description

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

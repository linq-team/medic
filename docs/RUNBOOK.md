# Medic Operational Runbook

## Overview

This runbook provides operational procedures for managing and troubleshooting the Medic heartbeat monitoring service.

## Table of Contents

1. [Service Overview](#service-overview)
2. [Alert Response Procedures](#alert-response-procedures)
3. [Common Issues and Resolutions](#common-issues-and-resolutions)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Escalation Procedures](#escalation-procedures)

---

## Service Overview

### Components

| Component | Description | Port |
|-----------|-------------|------|
| Web Server | Flask API serving heartbeat endpoints | 8080 |
| Worker | Background process monitoring heartbeats | N/A |
| PostgreSQL | Database storing heartbeats and alerts | 5432 |
| Redis | Distributed rate limiting cache | 6379 |

### Health Endpoints

- `/v1/healthcheck/network` - Basic network health (204 response)
- `/health` - Comprehensive health status
- `/health/live` - Kubernetes liveness probe
- `/health/ready` - Kubernetes readiness probe
- `/metrics` - Prometheus metrics

### Environment Variables

#### Database (Required)

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_HOST` | Yes | PostgreSQL host |
| `DB_PORT` | Yes | PostgreSQL port (default: 5432) |
| `DB_NAME` | Yes | PostgreSQL database name |
| `PG_USER` | Yes | PostgreSQL username |
| `PG_PASS` | Yes | PostgreSQL password |

#### Application (Optional)

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No | Web server port (default: 8080) |
| `DEBUG` | No | Debug mode (default: false) |
| `MEDIC_BASE_URL` | No | Base URL for links (default: http://localhost:8080) |
| `MEDIC_TIMEZONE` | No | Timezone for scheduling (default: America/Chicago) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

#### Worker Settings (Optional)

| Variable | Required | Description |
|----------|----------|-------------|
| `WORKER_INTERVAL_SECONDS` | No | Heartbeat check interval (default: 15) |
| `ALERT_AUTO_UNMUTE_HOURS` | No | Hours until auto-unmute (default: 24) |
| `HEARTBEAT_RETENTION_DAYS` | No | Data retention period (default: 30) |

#### Redis (Required for distributed rate limiting)

| Variable | Required | Description |
|----------|----------|-------------|
| `REDIS_URL` | Conditional | Redis connection URL (e.g., redis://localhost:6379/0) |
| `MEDIC_RATE_LIMITER_TYPE` | No | Rate limiter: `auto`, `redis`, or `memory` (default: auto) |
| `REDIS_POOL_SIZE` | No | Redis connection pool size (default: 10) |

#### Integrations (Optional)

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_API_TOKEN` | No | Slack Bot token for notifications |
| `SLACK_CHANNEL_ID` | No | Slack channel for notifications |
| `SLACK_SIGNING_SECRET` | No | Slack webhook signature verification |
| `PAGERDUTY_ROUTING_KEY` | No | PagerDuty Events API routing key |

#### Security (Required for production)

| Variable | Required | Description |
|----------|----------|-------------|
| `MEDIC_SECRETS_KEY` | Prod | AES-256 key for encrypting secrets (32-byte base64) |
| `MEDIC_WEBHOOK_SECRET` | Prod | Secret for webhook signature validation |
| `MEDIC_ALLOWED_WEBHOOK_HOSTS` | No | Comma-separated allowlist for webhook URLs (SSRF prevention) |

---

## Alert Response Procedures

### Heartbeat Failure Alert

**Severity:** Varies by service priority (P1-P5)

**Symptoms:**
- PagerDuty alert: "Medic - Heartbeat failure for [service-name]"
- Slack notification in configured channel

**Investigation Steps:**

1. **Check Service Status**
   ```bash
   medic-cli service get <heartbeat-name>
   ```

2. **Check Recent Heartbeats**
   ```bash
   medic-cli heartbeat list --name <heartbeat-name>
   ```

3. **Check Source Service**
   - Verify the source service is running
   - Check source service logs for errors
   - Verify network connectivity to Medic

4. **Check Medic Health**
   ```bash
   medic-cli health
   curl http://medic-host:5000/health
   ```

**Resolution:**

- If source service is down: Restart source service
- If network issue: Check firewall rules and DNS
- If Medic issue: See [Common Issues](#common-issues-and-resolutions)

**Temporary Mitigation:**
```bash
medic-cli service mute <heartbeat-name>
```

### Database Connection Alert

**Severity:** P1

**Symptoms:**
- Health check shows database as unhealthy
- API returns 500 errors
- Worker logs show connection errors

**Investigation Steps:**

1. **Check Database Connectivity**
   ```bash
   psql -h $DB_HOST -U $PG_USER -d $DB_NAME -c "SELECT 1"
   ```

2. **Check Database Logs**
   ```bash
   kubectl logs -l app=medic-db
   ```

3. **Check Database Resources**
   - CPU/Memory utilization
   - Disk space
   - Connection count

**Resolution:**

- Connection pool exhausted: Restart Medic pods
- Database overloaded: Scale database or optimize queries
- Database down: Follow database recovery procedures

---

## Common Issues and Resolutions

### Issue: Heartbeats Not Being Recorded

**Symptoms:**
- Services report sending heartbeats but none appear in API
- `/heartbeat` POST returns 404

**Cause:** Service not registered

**Resolution:**
```bash
# Register the service
curl -X POST http://medic-host:5000/service \
  -H "Content-Type: application/json" \
  -d '{
    "heartbeat_name": "service-heartbeat",
    "service_name": "my-service",
    "alert_interval": 5,
    "team": "platform"
  }'
```

### Issue: Alerts Not Firing

**Symptoms:**
- Missing heartbeats but no alerts generated
- PagerDuty not receiving events

**Cause:** Configuration issue or service muted

**Investigation:**
```bash
# Check if service is muted
medic-cli service get <heartbeat-name>

# Check PagerDuty configuration
echo $PAGERDUTY_ROUTING_KEY
```

**Resolution:**
- Unmute service: `medic-cli service unmute <name>`
- Verify PagerDuty routing key is correct
- Check worker logs for errors

### Issue: High Memory Usage

**Symptoms:**
- Container OOM kills
- Slow response times

**Cause:** Memory leak or excessive data

**Resolution:**
1. Restart affected pods
2. Check for old data accumulation
3. Verify cleanup job is running

### Issue: Duplicate Alerts

**Symptoms:**
- Multiple PagerDuty incidents for same issue
- Repeated Slack messages

**Cause:** Worker race condition or restart during alert

**Resolution:**
1. Manually close duplicate PagerDuty incidents
2. Check worker logs for restart events
3. Ensure only one worker instance is running

---

## Maintenance Procedures

### Muting a Service for Maintenance

```bash
# Mute before maintenance
medic-cli service mute <heartbeat-name>

# Perform maintenance...

# Unmute after maintenance
medic-cli service unmute <heartbeat-name>
```

### Database Cleanup

The cleanup job runs daily at 00:00 UTC, removing heartbeats older than 30 days.

Manual cleanup:
```sql
DELETE FROM "heartbeatEvents" WHERE time <= (NOW() - INTERVAL '30 days');
```

### Rolling Restart

```bash
# Restart web server pods
kubectl rollout restart deployment/medic-web

# Restart worker pods
kubectl rollout restart deployment/medic-worker
```

### Backup Database

```bash
pg_dump -h $DB_HOST -U $PG_USER -d $DB_NAME > medic_backup_$(date +%Y%m%d).sql
```

---

## Escalation Procedures

### Escalation Matrix

| Severity | Response Time | Escalation Path |
|----------|---------------|-----------------|
| P1 | 15 minutes | On-call -> Team Lead -> Engineering Manager |
| P2 | 1 hour | On-call -> Team Lead |
| P3 | 4 hours | On-call |
| P4/P5 | Next business day | Ticket queue |

### Contact Information

- **On-call Rotation:** Check PagerDuty schedule
- **Slack Channel:** #medic-alerts
- **Documentation:** https://github.com/linq-team/medic

---

## Metrics and Dashboards

### Key Metrics to Monitor

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| `medic_alerts_active` | > 5 | > 10 |
| `medic_http_request_duration_seconds` p95 | > 1s | > 5s |
| `medic_db_connection_errors_total` rate | > 0.1/min | > 1/min |

### Dashboard Location

Grafana: `dashboards/grafana.json`

Import into your Grafana instance and configure the Prometheus datasource.

---

## Python 3.14 Upgrade

### Summary

Medic was upgraded from Python 3.11 to Python 3.14 in February 2026. This section documents the rollback procedure, changes made, and known compatibility notes.

### What Changed

| Component | Before | After |
|-----------|--------|-------|
| CI Python version | 3.11 | 3.14 |
| Dockerfile base image | python:3.11-slim-bookworm | python:3.14-slim-bookworm |
| Type annotations | `typing.Dict`, `typing.List`, etc. | Built-in `dict`, `list`, etc. |
| `typing.Callable` | From `typing` module | From `collections.abc` |
| `datetime.utcnow()` | Used in tests | Replaced with `datetime.now(timezone.utc)` |
| `medic_build_info` metric | No Python version label | Includes `python_version` label |
| `/health` endpoint | No Python version | Includes `python_version` field |

### Dependency Versions (Python 3.14 Compatible)

- `flask>=3.1.0`
- `psycopg2-binary>=2.9.11` (Python 3.14 wheels available since October 2025)
- `cryptography>=44.0.0`
- `mypy>=1.14.0` (mypyc wheels for Python 3.14)
- `opentelemetry-*>=1.39.0`
- `redis>=5.2.0`
- `pytest>=8.3.0`
- `ruff>=0.9.0`

### Rollback Procedure

If issues are discovered after deploying the Python 3.14 upgrade, follow these steps to revert to Python 3.11:

#### 1. Revert the Git Branch

```bash
# Identify the last commit before the Python 3.14 upgrade
git log --oneline main

# Revert the merge commit (if already merged to main)
git revert <merge-commit-sha> --no-edit
git push origin main
```

This will trigger the CI/CD pipeline to build and deploy with the reverted code.

#### 2. Manual Docker Image Rollback (Emergency)

If CI/CD is too slow, manually update the Helm release to use the last known good image:

```bash
# Find the last Python 3.11 image tag in ECR
aws ecr describe-images \
  --repository-name medic \
  --region us-east-1 \
  --query 'imageDetails | sort_by(@, &imagePushedAt) | [-5:].[imageTags[0], imagePushedAt]' \
  --output table

# Update Helm release with the previous image tag
helm upgrade medic helm/medic \
  --namespace medic \
  --set image.tag=<previous-tag> \
  --reuse-values
```

#### 3. Revert Dockerfile (If Building Locally)

```dockerfile
# Change both stages back to Python 3.11
FROM python:3.11-slim-bookworm AS builder
FROM python:3.11-slim-bookworm AS runtime
```

#### 4. Revert CI Workflow

In `.github/workflows/build.yml`:
```yaml
env:
  PYTHON_VERSION: "3.11"
```

#### 5. Revert Type Annotations (Optional)

The type annotation changes (e.g., `list[str]` instead of `List[str]`) are backwards compatible with Python 3.11 (which supports PEP 585 built-in generics since Python 3.9). **No code changes are needed** for type annotations when rolling back.

The only code change that may need reverting is in `tests/unit/test_monitor.py` where `datetime.utcnow()` was replaced. This change is also backwards compatible, so no revert is needed.

### Known Issues and Compatibility Notes

1. **No breaking changes discovered.** All 1304 tests pass on Python 3.14 with no regressions.

2. **Python 3.14 features not adopted.** PEP 758 (bracketless except), PEP 750 (t-strings), and other new features were evaluated but not applied, since they provide no functional benefit to the codebase.

3. **Alpine base image not used.** While `python:3.14-alpine` is 3x smaller (77MB vs 211MB), it uses musl libc which can break prebuilt wheels for `psycopg2-binary` and `cryptography`. Stick with `slim-bookworm`.

4. **3 tests are skipped by design.** These are integration tests requiring `TEST_DATABASE_URL` environment variable. This is expected behavior, not a regression.

5. **OpenTelemetry packages.** The `opentelemetry-*>=1.39.0` packages work with Python 3.14 despite not having the Python 3.14 classifier on PyPI. Functional compatibility has been verified.

6. **`datetime.utcnow()` deprecation.** Python 3.12+ deprecates `datetime.utcnow()`. The test suite has been updated to use `datetime.now(timezone.utc)`. Application code already used timezone-aware datetimes.

### Verification Checklist

After deploying the Python 3.14 upgrade, verify:

- [ ] `/health` endpoint returns `python_version: "3.14.x"`
- [ ] `/metrics` endpoint includes `python_version` label on `medic_build_info`
- [ ] All heartbeat endpoints respond correctly
- [ ] Worker processes are running and checking heartbeats
- [ ] Database connections are healthy
- [ ] Redis rate limiting is functioning
- [ ] Slack and PagerDuty integrations fire correctly

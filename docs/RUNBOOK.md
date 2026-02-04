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

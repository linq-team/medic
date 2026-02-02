# Medic Architecture

## Overview

Medic is a heartbeat monitoring service that tracks the health of services by receiving periodic heartbeat signals. When a service fails to send heartbeats within a configured interval, Medic triggers alerts through PagerDuty and Slack.

## System Architecture

```
                                    ┌─────────────────┐
                                    │   Client Apps   │
                                    │  (Go/Python/    │
                                    │  Ruby/TS)       │
                                    └────────┬────────┘
                                             │
                                             │ POST /heartbeat
                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Medic Service                                │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │   Web Server    │    │      Worker      │    │   Scheduler    │  │
│  │   (Flask)       │    │   (Background)   │    │   (Cron Job)   │  │
│  │                 │    │                  │    │                │  │
│  │ - /heartbeat    │    │ - 15s interval   │    │ - Daily 00:00  │  │
│  │ - /service      │    │ - Check services │    │ - DB cleanup   │  │
│  │ - /alerts       │    │ - Send alerts    │    │                │  │
│  │ - /health       │    │                  │    │                │  │
│  │ - /metrics      │    │                  │    │                │  │
│  └────────┬────────┘    └────────┬─────────┘    └───────┬────────┘  │
│           │                      │                      │           │
└───────────┼──────────────────────┼──────────────────────┼───────────┘
            │                      │                      │
            ▼                      ▼                      ▼
    ┌───────────────────────────────────────────────────────────┐
    │                      PostgreSQL                            │
    │  ┌─────────────┐  ┌──────────────────┐  ┌──────────────┐  │
    │  │  services   │  │  heartbeatEvents │  │    alerts    │  │
    │  └─────────────┘  └──────────────────┘  └──────────────┘  │
    └───────────────────────────────────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  PagerDuty   │   │    Slack     │   │  Prometheus  │
    │  (Alerts)    │   │  (Notifs)    │   │  (Metrics)   │
    └──────────────┘   └──────────────┘   └──────────────┘
```

## Components

### Web Server (Flask)

The web server handles all HTTP API requests:

- **Heartbeat Management**: Receive and store heartbeats from services
- **Service Registration**: Register new heartbeats with alerting configuration
- **Alert Queries**: Retrieve current and historical alerts
- **Health Checks**: Provide health status for load balancers and monitoring
- **Metrics**: Expose Prometheus metrics for observability

**Port:** 5000 (configurable via `PORT` env var)

### Worker

The background worker runs continuously, checking for missing heartbeats:

- **Monitoring Loop**: Every 15 seconds, checks all active services
- **Alert Logic**: Compares heartbeat count against threshold
- **Notification**: Triggers PagerDuty and Slack when thresholds not met
- **Auto-unmute**: Automatically unmutes services after 24 hours

**Key Algorithm:**
```
For each active service:
  1. Query heartbeats in the last `alert_interval` minutes
  2. If count < threshold AND service not muted:
     - Create/update alert in database
     - Send PagerDuty event
     - Send Slack notification
  3. If count >= threshold AND service is down:
     - Resolve alert
     - Send recovery notification
```

### Scheduler (Database Cleanup)

A scheduled job that maintains database hygiene:

- **Schedule**: Daily at 00:00 UTC
- **Action**: Deletes heartbeat events older than 30 days
- **Purpose**: Prevents database bloat

### PostgreSQL Database

Stores all persistent data:

#### Tables

**services**
- Registration info for each heartbeat source
- Alert configuration (interval, threshold, team, priority)
- State tracking (active, muted, down)

**heartbeatEvents**
- Timestamped record of each heartbeat
- Links to service via `service_id`
- Includes status (UP/DOWN/DEGRADED)

**alerts**
- Active and historical alerts
- PagerDuty incident reference
- Alert lifecycle tracking

## Data Flow

### Heartbeat Flow

```
1. Client sends POST /heartbeat
   {heartbeat_name: "svc-hb", status: "UP"}

2. Web server looks up service by heartbeat_name

3. If found and active, inserts into heartbeatEvents

4. Returns 201 Created
```

### Alert Flow

```
1. Worker queries services WHERE active=1

2. For each service, counts recent heartbeats:
   SELECT COUNT(*) FROM heartbeatEvents
   WHERE service_id = X
   AND time >= NOW() - INTERVAL 'Y minutes'

3. If count < threshold:
   a. Mark service as down
   b. Create alert record if not exists
   c. Send PagerDuty trigger event
   d. Send Slack notification

4. If count >= threshold AND service.down = 1:
   a. Mark service as not down
   b. Close alert record
   c. Send PagerDuty resolve event
   d. Send Slack recovery notification
```

## Security Considerations

### SQL Injection Prevention

All database queries use parameterized queries:
```python
# Safe
cur.execute("SELECT * FROM services WHERE name = %s", (name,))

# Unsafe (not used)
cur.execute(f"SELECT * FROM services WHERE name = '{name}'")
```

### Authentication

Currently, the API does not implement authentication. In production:
- Place behind an API gateway with authentication
- Use network policies to restrict access
- Consider adding API key authentication

### Secrets Management

Sensitive data is passed via environment variables:
- `PG_PASS` - Database password
- `SLACK_API_TOKEN` - Slack bot token
- `PAGERDUTY_ROUTING_KEY` - PagerDuty integration key

## Scalability

### Horizontal Scaling

- **Web Server**: Can scale horizontally behind a load balancer
- **Worker**: Should run as single instance to avoid duplicate alerts
- **Database**: Standard PostgreSQL scaling (read replicas, connection pooling)

### Performance Considerations

- Heartbeat inserts are lightweight, single-row operations
- Worker queries are indexed on `service_id` and `time`
- Cleanup job runs during off-peak hours

## Monitoring

### Prometheus Metrics

Key metrics exposed at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `medic_heartbeats_total` | Counter | Total heartbeats received |
| `medic_alerts_active` | Gauge | Currently active alerts |
| `medic_http_request_duration_seconds` | Histogram | API latency |
| `medic_db_query_duration_seconds` | Histogram | Database query latency |

### Health Checks

| Endpoint | Purpose |
|----------|---------|
| `/health` | Comprehensive status |
| `/health/live` | Kubernetes liveness |
| `/health/ready` | Kubernetes readiness |

## Deployment

### Kubernetes

Recommended deployment configuration:

```yaml
Web Server:
  replicas: 2-4
  resources:
    memory: 256Mi
    cpu: 100m
  livenessProbe: /health/live
  readinessProbe: /health/ready

Worker:
  replicas: 1  # Single instance
  resources:
    memory: 384Mi
    cpu: 100m
```

### Docker Compose

For local development, use `docker-compose.yml` which includes:
- PostgreSQL 16
- Web server
- Worker

## Future Considerations

- **Authentication**: Add API key or OAuth support
- **Rate Limiting**: Protect against abuse
- **Clustering**: Support for multi-region deployment
- **Webhooks**: Generic webhook support beyond PagerDuty/Slack

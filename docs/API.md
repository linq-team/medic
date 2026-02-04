# Medic API Documentation

## Overview

The Medic API provides endpoints for heartbeat monitoring, service registration, and alert management.

**Base URL:** `http://localhost:5000` (configurable via `MEDIC_BASE_URL`)

**Content-Type:** `application/json`

---

## Authentication

Currently, the API does not require authentication. In production, it should be placed behind an API gateway with appropriate access controls.

---

## Common Response Format

All endpoints return responses in the following format:

```json
{
  "success": true,
  "message": "Description of result",
  "results": []
}
```

---

## Endpoints

### Health Checks

#### GET /v1/healthcheck/network

Simple network health check.

**Response:** `204 No Content`

---

#### GET /health

Comprehensive health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "2.0.0",
  "components": {
    "database": {
      "status": "healthy"
    },
    "pagerduty": {
      "status": "configured",
      "routing_key_set": true
    },
    "slack": {
      "status": "configured",
      "token_set": true,
      "channel_set": true
    }
  }
}
```

**Status Codes:**
- `200` - All components healthy
- `503` - One or more components unhealthy

---

#### GET /health/live

Kubernetes liveness probe.

**Response:**
```json
{
  "status": "alive",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

#### GET /health/ready

Kubernetes readiness probe.

**Response:**
```json
{
  "status": "ready",
  "timestamp": "2024-01-15T10:30:00Z",
  "database": "healthy"
}
```

**Status Codes:**
- `200` - Service ready
- `503` - Service not ready

---

### Heartbeats

#### POST /heartbeat

Send a heartbeat for a registered service.

**Request Body:**
```json
{
  "heartbeat_name": "staging-my-service-hb",
  "service_name": "my-service",
  "status": "UP"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| heartbeat_name | string | Yes | Registered heartbeat identifier |
| service_name | string | No | Associated service name |
| status | string | Yes | Current status (UP/DOWN/DEGRADED) |

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Heartbeat Posted Successfully.",
  "results": ""
}
```

**Error Responses:**
- `400` - Invalid request data or service inactive
- `404` - Heartbeat name not registered

---

#### GET /heartbeat

Query heartbeat events.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| heartbeat_name | string | Filter by heartbeat name |
| service_name | string | Filter by service name |
| maxCount | integer | Maximum results (default: 250, max: 250) |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "",
  "results": [
    {
      "heartbeat_id": 123,
      "heartbeat_name": "staging-my-service-hb",
      "service_name": "my-service",
      "time": "2024-01-15T10:30:00Z",
      "status": "UP",
      "team": "platform",
      "priority": "p2"
    }
  ]
}
```

---

### Services

#### POST /service

Register a new heartbeat service.

**Request Body:**
```json
{
  "heartbeat_name": "my-service-hb",
  "service_name": "my-service",
  "environment": "staging",
  "alert_interval": 5,
  "threshold": 1,
  "team": "platform",
  "priority": "p2",
  "runbook": "https://docs.example.com/runbook"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| heartbeat_name | string | Yes | Unique identifier for heartbeat |
| service_name | string | Yes | Name of the service |
| environment | string | No | Environment prefix (staging/production) |
| alert_interval | integer | Yes | Time in minutes before alerting |
| threshold | integer | No | Minimum heartbeats in interval (default: 1) |
| team | string | No | Team for alert routing (default: site-reliability) |
| priority | string | No | Alert priority P1-P5 (default: p3) |
| runbook | string | No | URL to troubleshooting documentation |

**Note:** If `environment` is provided, it's prefixed to heartbeat_name: `{environment}-{heartbeat_name}`

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Heartbeat successfully registered.",
  "results": ""
}
```

**Response (200 OK) - Already Registered:**
```json
{
  "success": true,
  "message": "Heartbeat is already registered.",
  "results": ""
}
```

---

#### GET /service

List all registered services.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| service_name | string | Filter by service name |
| active | integer | Filter by active status (0 or 1) |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "",
  "results": [
    {
      "service_id": 1,
      "heartbeat_name": "staging-my-service-hb",
      "service_name": "my-service",
      "active": 1,
      "alert_interval": 5,
      "threshold": 1,
      "team": "platform",
      "priority": "p2",
      "muted": 0,
      "down": 0,
      "runbook": "https://docs.example.com/runbook",
      "date_added": "2024-01-15T10:00:00Z",
      "date_modified": "2024-01-15T10:00:00Z"
    }
  ]
}
```

---

#### GET /service/{heartbeat_name}

Get details for a specific service.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "",
  "results": [
    {
      "service_id": 1,
      "heartbeat_name": "staging-my-service-hb",
      "service_name": "my-service",
      "active": 1,
      "alert_interval": 5,
      "threshold": 1,
      "team": "platform",
      "priority": "p2",
      "muted": 0,
      "down": 0,
      "runbook": "https://docs.example.com/runbook"
    }
  ]
}
```

---

#### POST /service/{heartbeat_name}

Update a registered service.

**Request Body:**
All fields are optional. Only provided fields will be updated.

```json
{
  "service_name": "updated-service-name",
  "active": 1,
  "alert_interval": 10,
  "threshold": 2,
  "team": "new-team",
  "priority": "p1",
  "muted": 1,
  "runbook": "https://docs.example.com/new-runbook"
}
```

| Field | Type | Description |
|-------|------|-------------|
| service_name | string | Update service name |
| active | integer | Enable (1) or disable (0) |
| alert_interval | float | Update alert interval in minutes |
| threshold | integer | Update heartbeat threshold |
| team | string | Update team routing |
| priority | string | Update alert priority |
| muted | integer | Mute (1) or unmute (0) |
| runbook | string | Update runbook URL |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Successfully posted update",
  "results": ""
}
```

---

### Alerts

#### GET /alerts

Query alerts.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| active | integer | Filter by active status (0 or 1) |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "",
  "results": [
    {
      "alert_id": 7,
      "alert_name": "Medic - Heartbeat failure for staging-my-service-hb",
      "service_id": 2,
      "active": 1,
      "external_reference_id": "medic-staging-my-service-hb",
      "alert_cycle": 10,
      "created_date": "2024-01-15T10:00:00Z",
      "closed_date": null
    }
  ]
}
```

---

### Metrics

#### GET /metrics

Prometheus metrics endpoint.

**Response:** `text/plain` format

```
# HELP medic_heartbeats_total Total heartbeats received
# TYPE medic_heartbeats_total counter
medic_heartbeats_total{heartbeat_name="staging-my-service-hb",status="UP"} 42.0

# HELP medic_alerts_active Number of currently active alerts
# TYPE medic_alerts_active gauge
medic_alerts_active 2.0

# HELP medic_http_request_duration_seconds HTTP request latency
# TYPE medic_http_request_duration_seconds histogram
medic_http_request_duration_seconds_bucket{endpoint="heartbeat",method="POST",le="0.01"} 100.0
```

---

### Snapshots

Snapshots provide backup/restore functionality for service configurations. A snapshot is automatically created before any destructive action (deactivate, edit, bulk operations).

#### GET /v2/snapshots

Query service snapshots with flexible filtering.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| service_id | integer | Filter by service ID |
| action_type | string | Filter by action type (see values below) |
| start_date | string | Filter snapshots on or after this date (ISO format) |
| end_date | string | Filter snapshots on or before this date (ISO format) |
| limit | integer | Maximum results (default: 50, max: 250) |
| offset | integer | Number of entries to skip for pagination |

**Action Types:**
- `deactivate` - Before deactivating a service
- `activate` - Before reactivating a service
- `mute` - Before muting alerts
- `unmute` - Before unmuting alerts
- `edit` - Before editing service configuration
- `bulk_edit` - Before bulk operations
- `priority_change` - Before changing priority
- `team_change` - Before changing team assignment
- `delete` - Before deleting a service

**Response (200 OK):**
```json
{
  "success": true,
  "message": "",
  "results": {
    "entries": [
      {
        "snapshot_id": 1,
        "service_id": 42,
        "snapshot_data": {
          "heartbeat_name": "my-service-hb",
          "service_name": "my-service",
          "active": 1,
          "muted": 0,
          "priority": "p2",
          "team": "platform",
          "alert_interval": 5,
          "threshold": 1,
          "runbook": "https://docs.example.com/runbook"
        },
        "action_type": "deactivate",
        "actor": "user@example.com",
        "created_at": "2026-01-15T10:30:00Z",
        "restored_at": null
      }
    ],
    "total_count": 1,
    "limit": 50,
    "offset": 0,
    "has_more": false
  }
}
```

---

#### GET /v2/snapshots/{snapshot_id}

Get a single snapshot by ID.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "",
  "results": {
    "snapshot_id": 1,
    "service_id": 42,
    "snapshot_data": { ... },
    "action_type": "deactivate",
    "actor": "user@example.com",
    "created_at": "2026-01-15T10:30:00Z",
    "restored_at": null
  }
}
```

---

#### POST /v2/snapshots/{snapshot_id}/restore

Restore a service to its previous state from a snapshot.

**Request Headers:**
| Header | Type | Description |
|--------|------|-------------|
| X-Actor | string | Optional. Identifies who performed the restore |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Snapshot restored successfully",
  "results": {
    "snapshot_id": 1,
    "service_id": 42,
    "restored_at": "2026-01-15T11:00:00Z"
  }
}
```

**Error Responses:**
- `400` - Snapshot already restored
- `404` - Snapshot not found or associated service deleted

---

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Health check failed |

---

## Rate Limits

No rate limits are currently enforced. Consider implementing rate limiting in your API gateway for production use.

---

## Examples

### Register and Monitor a Service

```bash
# 1. Register the service
curl -X POST http://localhost:5000/service \
  -H "Content-Type: application/json" \
  -d '{
    "heartbeat_name": "my-app-heartbeat",
    "service_name": "my-app",
    "alert_interval": 5,
    "threshold": 1,
    "team": "platform",
    "priority": "p2"
  }'

# 2. Send heartbeats (call every minute)
curl -X POST http://localhost:5000/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "heartbeat_name": "my-app-heartbeat",
    "status": "UP"
  }'

# 3. Check service status
curl http://localhost:5000/service/my-app-heartbeat

# 4. Mute during maintenance
curl -X POST http://localhost:5000/service/my-app-heartbeat \
  -H "Content-Type: application/json" \
  -d '{"muted": 1}'

# 5. Unmute after maintenance
curl -X POST http://localhost:5000/service/my-app-heartbeat \
  -H "Content-Type: application/json" \
  -d '{"muted": 0}'
```

### Backup and Restore Service Configuration

```bash
# 1. View snapshots for a service (after making changes)
curl "http://localhost:5000/v2/snapshots?service_id=42"

# 2. View a specific snapshot
curl http://localhost:5000/v2/snapshots/1

# 3. Restore to a previous state
curl -X POST http://localhost:5000/v2/snapshots/1/restore \
  -H "X-Actor: admin@example.com"

# 4. Query snapshots by action type (e.g., find all deactivations)
curl "http://localhost:5000/v2/snapshots?action_type=deactivate"

# 5. Query snapshots with date range
curl "http://localhost:5000/v2/snapshots?start_date=2026-01-01T00:00:00Z&end_date=2026-01-31T23:59:59Z"
```

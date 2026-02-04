# Medic Metrics Reference

Medic exposes Prometheus metrics with OpenTelemetry semantic conventions for
observability. This document describes all available metrics, their labels,
and how to use them for monitoring and alerting.

## Overview

Medic metrics follow OTEL (OpenTelemetry) semantic conventions where applicable:

- HTTP metrics use the `http.server.*` namespace
- Database metrics use the `db.client.*` namespace
- Application-specific metrics use the `medic_*` prefix

Metrics are exposed at `/metrics` in **OpenMetrics format**, which supports
exemplars for trace correlation.

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name label for metrics | `medic` |
| `MEDIC_ENVIRONMENT` | Deployment environment label | `development` |
| `MEDIC_VERSION` | Application version label | `unknown` |

## Exemplars and Trace Correlation

Histogram metrics include **exemplars** that contain `trace_id` values. This
enables Grafana to jump directly from a metric spike to an example trace that
contributed to that spike.

To enable exemplar display in Grafana:
1. Enable exemplars in the Prometheus data source settings
2. Use a panel that supports exemplars (e.g., heatmap, histogram)
3. Click on an exemplar point to navigate to the trace in Tempo

Example Prometheus query with exemplars:
```promql
histogram_quantile(0.99, sum(rate(medic_http_server_request_duration_seconds_bucket[5m])) by (le))
```

## Service Information

### medic_build_info

Gauge with value `1` that exposes service metadata as labels. Follows the
Prometheus convention of using `_build_info` suffix for version/build metadata.

**Labels:**
| Label | Description |
|-------|-------------|
| `service_name` | Service name from `OTEL_SERVICE_NAME` |
| `service_version` | Version from `MEDIC_VERSION` |
| `deployment_environment` | Environment from `MEDIC_ENVIRONMENT` |

**Use case:** Join with other metrics to add resource attributes:
```promql
medic_alerts_active * on() group_left(service_version, deployment_environment) medic_build_info
```

### medic_app_info

Info metric with static application metadata.

**Labels:**
| Label | Description |
|-------|-------------|
| `version` | Application version |
| `description` | Application description |

## HTTP Request Metrics

### medic_http_server_request_total

Counter for total HTTP requests received.

**Labels:**
| Label | Description |
|-------|-------------|
| `method` | HTTP method (GET, POST, PUT, DELETE, etc.) |
| `route` | Flask endpoint name |
| `status_code` | HTTP response status code |
| `service_name` | Service name |

**Example queries:**
```promql
# Request rate by endpoint
sum(rate(medic_http_server_request_total[5m])) by (route)

# Error rate (5xx responses)
sum(rate(medic_http_server_request_total{status_code=~"5.."}[5m]))
  / sum(rate(medic_http_server_request_total[5m]))

# Requests by status code
sum(rate(medic_http_server_request_total[5m])) by (status_code)
```

### medic_http_server_request_duration_seconds

Histogram for HTTP request latency with exemplars.

**Labels:**
| Label | Description |
|-------|-------------|
| `method` | HTTP method |
| `route` | Flask endpoint name |
| `service_name` | Service name |

**Buckets:** 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s

**Exemplar:** Contains `trace_id` for trace correlation.

**Example queries:**
```promql
# p99 latency
histogram_quantile(0.99, sum(rate(medic_http_server_request_duration_seconds_bucket[5m])) by (le, route))

# Average latency by endpoint
sum(rate(medic_http_server_request_duration_seconds_sum[5m])) by (route)
  / sum(rate(medic_http_server_request_duration_seconds_count[5m])) by (route)

# Latency heatmap (supports exemplars)
sum(rate(medic_http_server_request_duration_seconds_bucket[5m])) by (le)
```

## Database Metrics

### medic_db_client_operation_duration_seconds

Histogram for database query duration with exemplars.

**Labels:**
| Label | Description |
|-------|-------------|
| `operation` | Database operation type (select, insert, update, delete) |
| `service_name` | Service name |

**Buckets:** 1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s

**Exemplar:** Contains `trace_id` for trace correlation.

**Example queries:**
```promql
# p95 query latency by operation
histogram_quantile(0.95, sum(rate(medic_db_client_operation_duration_seconds_bucket[5m])) by (le, operation))

# Slow queries (> 100ms)
sum(rate(medic_db_client_operation_duration_seconds_bucket{le="0.1"}[5m]))
  / sum(rate(medic_db_client_operation_duration_seconds_count[5m]))
```

### medic_db_connection_errors_total

Counter for database connection errors.

**Example query:**
```promql
rate(medic_db_connection_errors_total[5m])
```

## Heartbeat Metrics

### medic_heartbeats_total

Counter for heartbeats received.

**Labels:**
| Label | Description |
|-------|-------------|
| `heartbeat_name` | Name of the heartbeat service |
| `status` | Heartbeat status (ok, late, missing) |

**Example queries:**
```promql
# Heartbeat rate by service
sum(rate(medic_heartbeats_total[5m])) by (heartbeat_name)

# Missing heartbeats
sum(rate(medic_heartbeats_total{status="missing"}[5m])) by (heartbeat_name)
```

### medic_registered_services

Gauge for total registered heartbeat services.

### medic_active_services

Gauge for currently active heartbeat services.

**Example alert:**
```yaml
- alert: HeartbeatServicesDegraded
  expr: medic_active_services / medic_registered_services < 0.9
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Less than 90% of services are active"
```

## Alert Metrics

### medic_alerts_total

Counter for alerts triggered.

**Labels:**
| Label | Description |
|-------|-------------|
| `priority` | Alert priority (P1, P2, P3, P4) |
| `team` | Team assigned to the alert |

### medic_alerts_active

Gauge for currently active alerts.

### medic_alerts_resolved_total

Counter for alerts resolved.

**Example queries:**
```promql
# Alert rate by priority
sum(rate(medic_alerts_total[1h])) by (priority)

# MTTR (Mean Time To Resolve) - requires recording rules
```

## Playbook Metrics

### medic_playbook_executions_total

Counter for playbook executions.

**Labels:**
| Label | Description |
|-------|-------------|
| `playbook` | Playbook name |
| `status` | Execution status (completed, failed, cancelled) |
| `service_name` | Service name |

### medic_playbook_execution_duration_seconds

Histogram for playbook execution duration with exemplars.

**Labels:**
| Label | Description |
|-------|-------------|
| `playbook` | Playbook name |
| `service_name` | Service name |

**Buckets:** 1s, 5s, 10s, 30s, 1m, 2m, 5m, 10m, 30m, 1h

**Exemplar:** Contains `trace_id` for trace correlation.

**Example queries:**
```promql
# p95 playbook execution time
histogram_quantile(0.95, sum(rate(medic_playbook_execution_duration_seconds_bucket[1h])) by (le, playbook))

# Failed playbook rate
sum(rate(medic_playbook_executions_total{status="failed"}[1h])) by (playbook)
  / sum(rate(medic_playbook_executions_total[1h])) by (playbook)
```

### medic_playbook_executions_pending_approval

Gauge for playbook executions waiting for approval.

## Circuit Breaker Metrics

### medic_circuit_breaker_trips_total

Counter for circuit breaker trips.

**Labels:**
| Label | Description |
|-------|-------------|
| `service_id` | Service ID that was blocked |

### medic_circuit_breaker_open

Gauge for services with open circuit breakers.

**Example alert:**
```yaml
- alert: CircuitBreakerTripped
  expr: medic_circuit_breaker_open > 0
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "{{ $value }} circuit breakers are open"
```

## Worker Metrics

### medic_worker_cycle_duration_seconds

Histogram for worker monitoring cycle duration.

**Buckets:** 100ms, 500ms, 1s, 2.5s, 5s, 10s, 30s

### medic_worker_services_checked_total

Counter for services checked by the worker.

## Authentication Metrics

### medic_auth_failures_total

Counter for authentication failures.

**Labels:**
| Label | Description |
|-------|-------------|
| `reason` | Failure reason (invalid_key, expired_key, insufficient_scope) |

**Example alert:**
```yaml
- alert: HighAuthFailureRate
  expr: sum(rate(medic_auth_failures_total[5m])) > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High authentication failure rate"
```

## External Service Metrics

### medic_pagerduty_requests_total

Counter for PagerDuty API requests.

**Labels:**
| Label | Description |
|-------|-------------|
| `action` | API action (trigger, acknowledge, resolve) |
| `status` | Request status (success, failure) |

### medic_slack_requests_total

Counter for Slack API requests.

**Labels:**
| Label | Description |
|-------|-------------|
| `status` | Request status (success, failure) |

## Health Metrics

### medic_health_status

Gauge for component health (1 = healthy, 0 = unhealthy).

**Labels:**
| Label | Description |
|-------|-------------|
| `component` | Component name (database, redis, pagerduty, slack) |

**Example alert:**
```yaml
- alert: ComponentUnhealthy
  expr: medic_health_status == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Component {{ $labels.component }} is unhealthy"
```

## Duration Alert Metrics

### medic_duration_alerts_total

Counter for duration threshold alerts.

**Labels:**
| Label | Description |
|-------|-------------|
| `alert_type` | Alert type (exceeded, stale) |

### medic_stale_jobs_current

Gauge for jobs exceeding their maximum duration.

## Grafana Dashboard Tips

### Trace Correlation with Exemplars

1. Create a histogram panel showing request latency
2. Enable "Exemplars" in the panel options
3. Configure the exemplar data source to link to Tempo
4. Click on exemplar points to view the associated trace

### Log Correlation

Logs include `trace_id` and `span_id` fields. Use Grafana's Explore view to:
1. View a trace in Tempo
2. Click "Logs for this span" to see related logs in Loki
3. Filter logs by `trace_id` to see the complete request journey

### Useful Dashboard Panels

1. **Request Rate & Error Rate**: `medic_http_server_request_total`
2. **Latency Heatmap**: `medic_http_server_request_duration_seconds_bucket`
3. **Service Health**: `medic_health_status`
4. **Active Alerts**: `medic_alerts_active`
5. **Playbook Success Rate**: Ratio of completed vs failed executions

## Recording Rules

Recommended recording rules for improved query performance:

```yaml
groups:
  - name: medic.rules
    rules:
      - record: medic:http_request_rate:5m
        expr: sum(rate(medic_http_server_request_total[5m])) by (route)

      - record: medic:http_error_rate:5m
        expr: |
          sum(rate(medic_http_server_request_total{status_code=~"5.."}[5m]))
          / sum(rate(medic_http_server_request_total[5m]))

      - record: medic:http_latency_p99:5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(medic_http_server_request_duration_seconds_bucket[5m])) by (le, route)
          )
```

## Metric Naming Migration

If upgrading from a previous version, note these metric name changes:

| Old Name | New Name (OTEL) |
|----------|-----------------|
| `medic_http_requests_total` | `medic_http_server_request_total` |
| `medic_http_request_duration_seconds` | `medic_http_server_request_duration_seconds` |
| `medic_db_query_duration_seconds` | `medic_db_client_operation_duration_seconds` |

The old names are still available as aliases for backwards compatibility.

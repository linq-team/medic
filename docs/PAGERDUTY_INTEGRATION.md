# PagerDuty Integration

This guide covers how to set up PagerDuty integration for Medic to send heartbeat failure alerts.

---

## Overview

Medic integrates with PagerDuty using the **Events API v2** to:
- Trigger incidents when heartbeats fail
- Automatically resolve incidents when heartbeats recover
- Include service metadata and runbook links in alerts

---

## Getting the Routing Key

### Step 1: Create or Select a Service

1. Log in to your PagerDuty account
2. Go to **Services** → **Service Directory**
3. Either:
   - Click on an existing service, OR
   - Click **+ New Service** to create one

### Step 2: Create a New Service (If Needed)

If creating a new service:

1. **Name:** `Medic Heartbeat Alerts` (or your preferred name)
2. **Description:** `Alerts from Medic heartbeat monitoring system`
3. **Escalation Policy:** Select your team's escalation policy
4. Click **Next** through the remaining steps

### Step 3: Add Events API v2 Integration

1. On the service page, go to the **Integrations** tab
2. Click **+ Add Integration**
3. Search for **Events API v2**
4. Select **Events API v2** and click **Add**

### Step 4: Copy the Integration Key

1. After adding the integration, you'll see it listed under Integrations
2. Click on **Events API v2** to expand it
3. Copy the **Integration Key** (also called Routing Key)
   - It looks like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

---

## Environment Configuration

Set this environment variable in your Medic deployment:

```bash
# Integration Key from Step 4
PAGERDUTY_ROUTING_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

---

## Alert Format

### Incident Triggered

When a heartbeat fails, Medic creates a PagerDuty incident with:

| Field | Value |
|-------|-------|
| **Summary** | `Heartbeat failure: {service_name}` |
| **Severity** | Based on service priority (P1=critical, P2=error, P3=warning, P4=info) |
| **Source** | `medic` |
| **Component** | Service name |
| **Group** | Team name |
| **Class** | `heartbeat_failure` |

**Custom Details Include:**
- Service slug
- Team name
- Priority level
- Missed heartbeat count
- Last seen timestamp
- Threshold configuration
- Runbook URL (if configured)

### Incident Resolved

When the heartbeat recovers, Medic automatically resolves the PagerDuty incident using the same dedup key.

---

## Deduplication

Medic uses a consistent deduplication key format:

```
medic-heartbeat-{service_slug}
```

This ensures:
- Multiple failures for the same service don't create duplicate incidents
- Recovery events resolve the correct incident
- Flapping services don't create incident storms

---

## Testing the Integration

### Manual Test with curl

```bash
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "routing_key": "YOUR_ROUTING_KEY_HERE",
    "event_action": "trigger",
    "dedup_key": "medic-test-alert",
    "payload": {
      "summary": "Medic test alert - integration working!",
      "severity": "info",
      "source": "medic-test",
      "component": "test-service",
      "group": "test-team",
      "class": "test"
    }
  }'
```

A successful response looks like:

```json
{
  "status": "success",
  "message": "Event processed",
  "dedup_key": "medic-test-alert"
}
```

### Resolve the Test Alert

```bash
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "routing_key": "YOUR_ROUTING_KEY_HERE",
    "event_action": "resolve",
    "dedup_key": "medic-test-alert"
  }'
```

---

## Priority Mapping

Medic maps service priorities to PagerDuty severities:

| Medic Priority | PagerDuty Severity | Description |
|----------------|-------------------|-------------|
| P1 | `critical` | Business-critical service down |
| P2 | `error` | Major functionality impacted |
| P3 | `warning` | Minor impact, needs attention |
| P4 | `info` | Low priority, informational |

---

## Troubleshooting

### "Invalid Routing Key" Error

**Cause:** The routing key is incorrect or the integration was deleted

**Fix:**
1. Go to PagerDuty → Services → Your Service → Integrations
2. Verify the Events API v2 integration exists
3. Copy the integration key again
4. Update `PAGERDUTY_ROUTING_KEY` in your environment

### Alerts Not Creating Incidents

**Cause:** Service may be disabled or in maintenance mode

**Fix:**
1. Check if the service is enabled in PagerDuty
2. Check if there's an active maintenance window
3. Verify the escalation policy has on-call users
4. Check Medic logs for PagerDuty API errors

### Duplicate Incidents

**Cause:** Dedup key mismatch or multiple Medic instances

**Fix:**
1. Ensure all Medic instances use the same service slug
2. Check for duplicate service configurations
3. Verify the dedup key in PagerDuty incident details

### Incidents Not Auto-Resolving

**Cause:** Recovery event not sent or dedup key mismatch

**Fix:**
1. Check Medic logs for recovery event errors
2. Verify the service actually recovered (heartbeat received)
3. Manually resolve if needed and investigate logs

---

## Advanced Configuration

### Multiple Services

You can route different Medic services to different PagerDuty services by:

1. Creating multiple PagerDuty services with their own routing keys
2. Configuring notification targets in Medic to use different routing keys per team/service

### Maintenance Windows

To prevent alerts during planned maintenance:

1. Create a maintenance window in PagerDuty for the service
2. OR use Medic's maintenance window feature to pause monitoring

### Custom Severity Mapping

If you need different severity mappings, you can configure this at the service level in Medic's notification target settings.

---

## Security Best Practices

1. **Key Storage:** Never commit routing keys to git. Use environment variables or secrets management (AWS Secrets Manager, Vault, etc.)

2. **Key Rotation:** PagerDuty integration keys don't expire, but you can regenerate them:
   - Go to the integration settings
   - Delete and re-add the Events API v2 integration
   - Update `PAGERDUTY_ROUTING_KEY` in your deployment

3. **Access Control:** Limit who can view/modify the PagerDuty service and integration settings

4. **Audit Logs:** PagerDuty maintains audit logs of all API events - review periodically

---

## Related Documentation

- [PagerDuty Events API v2 Documentation](https://developer.pagerduty.com/docs/events-api-v2/overview/)
- [Medic Slack Integration](SLACK_INTEGRATION.md)
- [Medic Runbook](RUNBOOK.md)
- [Medic Architecture](ARCHITECTURE.md)

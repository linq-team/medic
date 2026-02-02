# Medic Troubleshooting Guide

## Quick Diagnostics

### Check Overall Health

```bash
# Using CLI
medic-cli health

# Using curl
curl http://medic-host:5000/health | jq
```

### Check Logs

```bash
# Web server logs
kubectl logs -l app=medic-web -f

# Worker logs
kubectl logs -l app=medic-worker -f

# Database logs
kubectl logs -l app=medic-db -f
```

---

## Common Problems

### Problem: "Connection refused" when sending heartbeats

**Symptoms:**
- Client receives connection error
- Health check fails

**Possible Causes:**
1. Medic web server is not running
2. Incorrect host/port
3. Network/firewall blocking connection

**Solutions:**

1. **Check if service is running:**
   ```bash
   kubectl get pods -l app=medic-web
   ```

2. **Verify DNS resolution:**
   ```bash
   nslookup medic-host
   ```

3. **Test connectivity:**
   ```bash
   curl -v http://medic-host:5000/v1/healthcheck/network
   ```

4. **Check firewall rules:**
   - Ensure port 5000 is open
   - Check network policies

---

### Problem: Heartbeat returns 404 "not registered"

**Symptoms:**
- POST /heartbeat returns 404
- Message: "heartbeat_name is not listed as a registered service"

**Cause:** The heartbeat name is not registered in Medic

**Solution:**

Register the service first:
```bash
curl -X POST http://medic-host:5000/service \
  -H "Content-Type: application/json" \
  -d '{
    "heartbeat_name": "your-heartbeat-name",
    "service_name": "your-service-name",
    "alert_interval": 5,
    "team": "your-team"
  }'
```

---

### Problem: Heartbeat returns 400 "inactive"

**Symptoms:**
- POST /heartbeat returns 400
- Message: "heartbeat_name was located, but is marked inactive"

**Cause:** The service is registered but deactivated

**Solution:**

Reactivate the service:
```bash
curl -X POST http://medic-host:5000/service/your-heartbeat-name \
  -H "Content-Type: application/json" \
  -d '{"active": 1}'
```

---

### Problem: No alerts being generated

**Symptoms:**
- Service missing heartbeats
- No PagerDuty/Slack notifications

**Diagnosis Steps:**

1. **Check if service is muted:**
   ```bash
   medic-cli service get <heartbeat-name>
   # Look for: Muted: Yes/No
   ```

2. **Check if worker is running:**
   ```bash
   kubectl get pods -l app=medic-worker
   kubectl logs -l app=medic-worker --tail=100
   ```

3. **Check PagerDuty configuration:**
   ```bash
   kubectl exec -it <medic-pod> -- env | grep PAGERDUTY
   ```

4. **Check Slack configuration:**
   ```bash
   kubectl exec -it <medic-pod> -- env | grep SLACK
   ```

**Solutions:**

- **If muted:** Unmute with `medic-cli service unmute <name>`
- **If worker down:** Restart worker deployment
- **If missing config:** Set required environment variables

---

### Problem: Duplicate alerts

**Symptoms:**
- Multiple PagerDuty incidents for same issue
- Repeated Slack messages

**Possible Causes:**
1. Multiple worker instances running
2. Worker restarted during alert processing

**Solutions:**

1. **Ensure single worker:**
   ```bash
   kubectl get pods -l app=medic-worker
   # Should show only ONE pod

   # If multiple:
   kubectl scale deployment medic-worker --replicas=1
   ```

2. **Check for restarts:**
   ```bash
   kubectl describe pod -l app=medic-worker | grep Restart
   ```

---

### Problem: Database connection errors

**Symptoms:**
- Health check shows database unhealthy
- Logs show "Failed to connect to database"

**Diagnosis:**

1. **Check database is running:**
   ```bash
   kubectl get pods -l app=medic-db
   ```

2. **Test direct connection:**
   ```bash
   kubectl exec -it <medic-pod> -- psql -h $DB_HOST -U $PG_USER -d $DB_NAME -c "SELECT 1"
   ```

3. **Check connection count:**
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'medic';
   ```

**Solutions:**

- **If database down:** Restart database pod
- **If too many connections:** Restart Medic pods to release connections
- **If credentials wrong:** Verify environment variables

---

### Problem: High API latency

**Symptoms:**
- Slow response times
- Timeouts on heartbeat requests
- `medic_http_request_duration_seconds` p95 > 1s

**Diagnosis:**

1. **Check database query times:**
   ```bash
   # Look at metrics
   curl http://medic-host:5000/metrics | grep db_query_duration
   ```

2. **Check database load:**
   ```sql
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   ```

3. **Check pod resources:**
   ```bash
   kubectl top pods -l app=medic-web
   ```

**Solutions:**

- **If database slow:** Check for missing indexes, long-running queries
- **If pod resource limited:** Increase CPU/memory limits
- **If too much data:** Run cleanup manually

---

### Problem: Memory leaks / OOM kills

**Symptoms:**
- Pods being killed with OOMKilled
- Memory usage growing over time

**Diagnosis:**

```bash
# Check for OOM kills
kubectl describe pod <pod-name> | grep -A5 "Last State"

# Monitor memory
kubectl top pods -l app=medic-web --watch
```

**Solutions:**

1. **Immediate:** Restart pods
2. **Long-term:**
   - Increase memory limits
   - Check for connection leaks in logs
   - Verify cleanup job is running

---

### Problem: Alerts not resolving

**Symptoms:**
- Heartbeats being received
- Service still shows as "down"
- Alert stays active

**Diagnosis:**

1. **Check heartbeat count:**
   ```bash
   medic-cli heartbeat list --name <heartbeat-name> --limit 10
   ```

2. **Verify threshold:**
   ```bash
   medic-cli service get <heartbeat-name>
   # Check: Threshold and Alert Interval
   ```

3. **Check worker logs:**
   ```bash
   kubectl logs -l app=medic-worker --tail=200 | grep <heartbeat-name>
   ```

**Common Issues:**

- Heartbeat count equals threshold but doesn't exceed
- Worker hasn't run since heartbeat received
- Service is muted (alerts won't auto-close when muted)

---

## Log Analysis

### Important Log Patterns

**Successful Heartbeat:**
```
Heartbeat: test-hb was posted successfully.
```

**Alert Triggered:**
```
Thread starting.
... Alert created for test-hb
```

**Alert Resolved:**
```
Heartbeat: test-hb is current.
... Alert closed for test-hb
```

**Database Error:**
```
Failed to connect to medic ... Error: connection refused
Unable to perform query ... An Error has occurred
```

### Enabling Debug Logging

Edit `Medic/Helpers/logSettings.py`:
```python
def logSetup():
    return 10  # DEBUG level (was 30 for WARNING)
```

---

## Recovery Procedures

### Full Service Restart

```bash
# Scale down
kubectl scale deployment medic-web --replicas=0
kubectl scale deployment medic-worker --replicas=0

# Wait for termination
kubectl get pods -l app=medic-web

# Scale up
kubectl scale deployment medic-web --replicas=2
kubectl scale deployment medic-worker --replicas=1
```

### Database Recovery

```bash
# Backup current state
pg_dump -h $DB_HOST -U $PG_USER -d $DB_NAME > backup.sql

# Restore from backup
psql -h $DB_HOST -U $PG_USER -d $DB_NAME < backup.sql
```

### Clear All Alerts

**Warning:** Use only in emergencies

```sql
-- Close all active alerts
UPDATE alerts SET active = 0, closed_date = NOW() WHERE active = 1;

-- Reset all services to healthy
UPDATE services SET down = 0, muted = 0;
```

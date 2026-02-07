import os
from datetime import datetime
import pytz
import threading
import time
import logging
import psycopg2
from Medic.Core.logging_config import configure_logging, get_logger
from Medic.Worker import slack_client as slack
from Medic.Worker import pagerduty_client as pagerduty

# Import telemetry
try:
    from Medic.Core.telemetry import (
        init_worker_telemetry,
        get_tracer,
        shutdown_telemetry,
    )
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    init_worker_telemetry = None  # type: ignore[misc, assignment]
    get_tracer = None  # type: ignore[misc, assignment]
    shutdown_telemetry = None  # type: ignore[misc, assignment]
    trace = None  # type: ignore[misc, assignment]

# Import maintenance window checker
try:
    from Medic.Core.maintenance_windows import (
        is_service_in_maintenance,
        get_active_maintenance_window_for_service,
    )

    MAINTENANCE_WINDOWS_AVAILABLE = True
except ImportError:
    MAINTENANCE_WINDOWS_AVAILABLE = False
    is_service_in_maintenance = None  # type: ignore[misc, assignment]
    get_active_maintenance_window_for_service = None  # type: ignore[misc, assignment]

# Import duration threshold checker
try:
    from Medic.Core.job_runs import (
        get_stale_runs_exceeding_max_duration,
        mark_stale_run_alerted,
        DurationAlert,
    )

    DURATION_ALERTS_AVAILABLE = True
except ImportError:
    DURATION_ALERTS_AVAILABLE = False
    get_stale_runs_exceeding_max_duration = None  # type: ignore[misc, assignment]
    mark_stale_run_alerted = None  # type: ignore[misc, assignment]
    DurationAlert = None  # type: ignore[misc, assignment]

# Import metrics
try:
    from prometheus_client import start_http_server as start_metrics_server

    from Medic.Core.metrics import (
        record_duration_alert,
        update_stale_jobs_count,
        record_alert_created,
        record_alert_resolved,
        WORKER_CYCLE_DURATION,
        WORKER_SERVICES_CHECKED,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    start_metrics_server = None  # type: ignore[misc, assignment]
    record_duration_alert = None  # type: ignore[misc, assignment]
    update_stale_jobs_count = None  # type: ignore[misc, assignment]
    record_alert_created = None  # type: ignore[misc, assignment]
    record_alert_resolved = None  # type: ignore[misc, assignment]
    WORKER_CYCLE_DURATION = None  # type: ignore[misc, assignment]
    WORKER_SERVICES_CHECKED = None  # type: ignore[misc, assignment]

# Default metrics server port
DEFAULT_METRICS_PORT = 9091

# Import playbook alert integration
try:
    from Medic.Core.playbook_alert_integration import (
        trigger_playbook_for_alert,
        get_alert_consecutive_failures,
    )

    PLAYBOOK_TRIGGERS_AVAILABLE = True
except ImportError:
    PLAYBOOK_TRIGGERS_AVAILABLE = False
    trigger_playbook_for_alert = None  # type: ignore[misc, assignment]
    get_alert_consecutive_failures = None  # type: ignore[misc, assignment]

# Log Setup
configure_logging()
logger = get_logger(__name__)

# Initialize tracer (will be set up in main)
_tracer = None


def _get_tracer():
    """Get the tracer instance, initializing if needed."""
    global _tracer
    if _tracer is None and TELEMETRY_AVAILABLE and get_tracer is not None:
        _tracer = get_tracer("medic.worker")
    return _tracer


def connect_db():
    user = os.environ["PG_USER"]
    password = os.environ["PG_PASS"]
    dbname = os.environ["DB_NAME"]
    dbhost = os.environ["DB_HOST"]
    try:
        conn = psycopg2.connect(
            user=user, password=password, host=dbhost, port="5432", database=dbname
        )
        logger.log(
            level=20,
            msg="Connected to "
            + dbhost
            + ":5432\\"
            + dbname
            + " with user: "
            + user
            + " successfully.",
        )
        return conn
    except psycopg2.Error as e:
        logger.log(
            level=50,
            msg="Failed to connect to "
            + dbname
            + " with supplied credentials. Is it running and do you have access? Error: "
            + str(e),
        )
        raise ConnectionError


def to_json(rows, columns):
    data = []
    for r in rows:
        d = {}
        for c in range(len(columns)):
            d[columns[c]] = r[c]
        data.append(d)
    return data


def query_db(query, params=None, show_columns=True):
    client = None
    cur = None
    try:
        client = connect_db()
        cur = client.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        if show_columns:
            col_names = [elt[0] for elt in cur.description]
            return to_json(rows, col_names)
        else:
            return rows
    except psycopg2.Error as e:
        logger.log(
            level=30, msg="Unable to perform query. An Error has occurred: " + str(e)
        )
        return None
    finally:
        if cur:
            cur.close()
        if client:
            client.close()


def insert_db(query, params=None):
    client = None
    cur = None
    try:
        client = connect_db()
        cur = client.cursor()
        cur.execute(query, params)
        client.commit()
        return True
    except psycopg2.Error as e:
        logger.log(level=30, msg="Unable to perform insert: " + str(e))
        return False
    finally:
        if cur:
            cur.close()
        if client:
            client.close()


def queryForNoHeartbeat():
    start_time = time.time()
    tracer = _get_tracer()
    try:
        if tracer:
            with tracer.start_as_current_span(
                "heartbeat_check_cycle",
                attributes={"worker.operation": "heartbeat_check"},
            ) as span:
                try:
                    _queryForNoHeartbeat_impl(span)
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        else:
            _queryForNoHeartbeat_impl(None)
    finally:
        # Record cycle duration metric
        if METRICS_AVAILABLE and WORKER_CYCLE_DURATION is not None:
            duration = time.time() - start_time
            WORKER_CYCLE_DURATION.observe(duration)


def _queryForNoHeartbeat_impl(span):
    # Setup main timezone
    tz = pytz.timezone("America/Chicago")

    # Setup the main loop for active services to check
    res = query_db(
        "SELECT * FROM services WHERE active = 1 AND service_name <> %s",
        ("fakeservice",),
        show_columns=True,
    )
    if res is None or res == []:
        logger.log(level=20, msg="No Services configured for heartbeats.")
        if span:
            span.set_attribute("services.checked", 0)
        return

    if span:
        span.set_attribute("services.checked", len(res))

    # Record services checked metric
    if METRICS_AVAILABLE and WORKER_SERVICES_CHECKED is not None:
        WORKER_SERVICES_CHECKED.inc(len(res))

    for heartbeat in res:
        s_id = heartbeat["service_id"]
        name = heartbeat["heartbeat_name"]
        s_name = heartbeat["service_name"]
        interval = heartbeat["alert_interval"]
        threshold = heartbeat["threshold"]
        team = heartbeat["team"]
        priority = heartbeat["priority"]
        muted = heartbeat["muted"]
        down = heartbeat["down"]
        runbook = heartbeat.get("runbook")
        grace_period = heartbeat.get("grace_period_seconds", 0) or 0
        fmt = "%Y-%m-%d %H:%M:%S"
        now_cdt = datetime.now(tz).strftime(fmt)

        # Query for recent heartbeat(s) with parameterized query
        query = """
            SELECT time, (
                SELECT COUNT(service_id)
                FROM "heartbeatEvents"
                WHERE service_id = %s
                AND time >= NOW() - INTERVAL '%s minutes'
                GROUP BY service_id
            )
            FROM "heartbeatEvents"
            WHERE service_id = %s
            ORDER BY time DESC
            LIMIT 1
        """
        last_hbeat = query_db(query, (s_id, interval, s_id), show_columns=False)
        logger.log(level=20, msg=str(last_hbeat))

        if last_hbeat is None or last_hbeat == []:
            logger.log(level=40, msg="ERROR: No results found for " + name)
            if muted != 1:
                message = (
                    ":elmofire: `"
                    + str(name)
                    + "` has been registered in medic but has not yet "
                    "sent a heartbeat. This message will repeat until muted. :elmofire:"
                )
                slack.send_message(message)
        else:
            last_hbeat_count = last_hbeat[0][1] if last_hbeat[0][1] is not None else 0
            lh_cvtd = (last_hbeat[0][0]).astimezone(tz).strftime(fmt)

            if int(last_hbeat_count) < int(threshold):
                # Check grace period before alerting
                # Grace period adds additional delay after expected heartbeat window
                if grace_period > 0:
                    last_hbeat_time = last_hbeat[0][0]
                    now_utc = datetime.now(pytz.UTC)
                    # Ensure last_hbeat_time is timezone-aware
                    if last_hbeat_time.tzinfo is None:
                        last_hbeat_time = pytz.UTC.localize(last_hbeat_time)
                    time_since_last = (now_utc - last_hbeat_time).total_seconds()
                    # Alert interval is in minutes, grace period is in seconds
                    interval_seconds = int(interval) * 60
                    required_delay = interval_seconds + grace_period
                    if time_since_last < required_delay:
                        grace_remaining = int(required_delay - time_since_last)
                        logger.log(
                            level=20,
                            msg=f"Alert delayed for {name}: grace period "
                            f"({grace_remaining}s remaining)",
                        )
                        continue

                # Check if service is in maintenance window before alerting
                if MAINTENANCE_WINDOWS_AVAILABLE and is_service_in_maintenance(s_id):
                    window = get_active_maintenance_window_for_service(s_id)
                    window_name = window.name if window else "Unknown"
                    logger.log(
                        level=20,
                        msg=f"Alert suppressed for {name}: service is in maintenance window '{window_name}'",
                    )
                else:
                    sendAlert(
                        s_id,
                        s_name,
                        name,
                        lh_cvtd,
                        interval,
                        team,
                        priority,
                        muted,
                        now_cdt,
                        runbook,
                    )
            elif int(last_hbeat_count) >= int(threshold) and down == 1:
                logger.log(level=20, msg="Heartbeat: " + str(name) + " is current.")
                closeAlert(name, s_name, s_id, lh_cvtd, team, muted, now_cdt)
            else:
                logger.log(level=20, msg="Heartbeat: " + str(name) + " is current.")


def sendAlert(
    service_id,
    service_name,
    heartbeat_name,
    last_seen,
    interval,
    team,
    priority,
    muted,
    current_time,
    runbook=None,
):
    # Convert interval to seconds from minutes
    interval_seconds = int(interval) * 60

    # Check for active alert
    result = query_db(
        "SELECT * FROM alerts WHERE active = 1 AND service_id = %s ORDER BY alert_id DESC LIMIT 1",
        (service_id,),
        show_columns=False,
    )

    # Mark service down in DB
    insert_db("UPDATE services SET down = 1 WHERE service_id = %s", (service_id,))

    alert_message = "Medic - Heartbeat failure for " + str(heartbeat_name)

    if result is None or result == []:
        # No active alert is present - create one
        insert_db(
            "INSERT INTO alerts(alert_name, service_id, active, alert_cycle, created_date) VALUES(%s, %s, 1, 1, %s)",
            (alert_message, service_id, current_time),
        )
        alert_cycle = 1  # New alert starts at cycle 1

        # Record alert created metric
        if METRICS_AVAILABLE and record_alert_created is not None:
            record_alert_created(priority=priority, team=team)

        if muted == 1:
            logger.log(
                level=20, msg=str(heartbeat_name) + " is muted. No alert will be sent."
            )
        else:
            # Send PagerDuty alert
            pd_key = pagerduty.create_alert(
                alert_message=alert_message,
                service_name=service_name,
                heartbeat_name=heartbeat_name,
                team=team,
                priority=priority,
                runbook=runbook,
            )

            # Update the alert with the PagerDuty dedup key
            if pd_key:
                insert_db(
                    "UPDATE alerts SET external_reference_id = %s WHERE service_id = %s AND active = 1",
                    (pd_key, service_id),
                )

            # Send slack message
            message = (
                ":broken_heart: No heartbeat has been detected for `"
                + str(heartbeat_name)
                + "` for service `"
                + str(service_name)
                + "` since "
                + str(last_seen)
                + ". Alert is being routed to `"
                + str(team)
                + "`"
            )
            slack.send_message(message)

            # Check for playbook triggers
            _check_playbook_triggers(service_id, service_name, alert_cycle)
    else:
        # Active alert exists
        alert_cycle = int(result[0][5])
        count = alert_cycle + 1

        # Update alert_cycle counter in db
        insert_db(
            "UPDATE alerts SET alert_cycle = %s WHERE alert_id = %s",
            (count, result[0][0]),
        )

        if muted == 1:
            logger.log(
                level=20,
                msg="Alert already active for "
                + str(heartbeat_name)
                + ", but muted. Checking Expiration...",
            )
            if alert_cycle % (1440 / 15) == 0:
                # 24 Hours have passed. Auto-unmute alert.
                insert_db(
                    "UPDATE services SET muted = 0, date_muted = NULL WHERE service_id = %s",
                    (service_id,),
                )
        else:
            # Calculate notification interval
            if alert_cycle % (interval_seconds / 15) == 0:
                message = (
                    ":broken_heart: No heartbeat has been detected for `"
                    + str(heartbeat_name)
                    + "` for service `"
                    + str(service_name)
                    + "` since "
                    + str(last_seen)
                    + ". Alert has been routed to `"
                    + str(team)
                    + "`"
                )
                slack.send_message(message)

            # Check for playbook triggers on subsequent cycles
            _check_playbook_triggers(service_id, service_name, count)


def _check_playbook_triggers(service_id, service_name, alert_cycle):
    """
    Check if any playbook should be triggered for an alerting service.

    This function checks the playbook triggers to find a matching playbook
    and starts execution based on the playbook's approval settings:
    - approval=none: Starts execution immediately
    - approval=required: Creates pending_approval execution

    Args:
        service_id: ID of the alerting service
        service_name: Name of the alerting service
        alert_cycle: Current alert cycle count (consecutive failures)
    """
    if not PLAYBOOK_TRIGGERS_AVAILABLE:
        return

    try:
        # Convert alert_cycle to consecutive failures
        consecutive_failures = get_alert_consecutive_failures(alert_cycle)

        # Try to trigger a playbook
        result = trigger_playbook_for_alert(
            service_id=service_id,
            service_name=service_name,
            consecutive_failures=consecutive_failures,
            alert_context={
                "ALERT_CYCLE": alert_cycle,
            },
        )

        if result.triggered:
            logger.log(
                level=20,
                msg=f"Playbook triggered for {service_name}: "
                f"{result.message} (execution_id: "
                f"{result.execution.execution_id if result.execution else 'N/A'})",
            )

            # Send Slack notification about playbook execution
            if result.status == "running":
                playbook_msg = (
                    f":robot_face: Auto-remediation playbook "
                    f"'{result.playbook.playbook_name}' started for "
                    f"`{service_name}` (execution: {result.execution.execution_id})"
                )
                slack.send_message(playbook_msg)
            elif result.status == "pending_approval":
                playbook_msg = (
                    f":hourglass: Auto-remediation playbook "
                    f"'{result.playbook.playbook_name}' awaiting approval for "
                    f"`{service_name}` (execution: {result.execution.execution_id})"
                )
                slack.send_message(playbook_msg)

    except Exception as e:
        logger.log(
            level=40,
            msg=f"Error checking playbook triggers for {service_name}: {str(e)}",
        )


def closeAlert(
    heartbeat_name, service_name, service_id, last_seen, team, muted, current_time
):
    # Find the active alert
    ar = query_db(
        "SELECT * FROM alerts WHERE active = 1 AND service_id = %s ORDER BY alert_id DESC LIMIT 1",
        (service_id,),
        show_columns=False,
    )

    if ar is None or ar == []:
        logger.log(level=20, msg="No active alert to close for " + str(heartbeat_name))
        return

    # Close the alert in the DB
    insert_db(
        "UPDATE services SET down = 0, muted = 0 WHERE service_id = %s", (service_id,)
    )
    insert_db(
        "UPDATE alerts SET active = 0, closed_date = %s WHERE alert_id = %s",
        (current_time, ar[0][0]),
    )

    # Record alert resolved metric
    if METRICS_AVAILABLE and record_alert_resolved is not None:
        record_alert_resolved()

    if muted == 1:
        logger.log(
            level=20, msg=str(heartbeat_name) + " is muted. No alert will be sent."
        )
    else:
        message = (
            ":green_heart: Heartbeat has recovered for `"
            + str(heartbeat_name)
            + "` belonging to service `"
            + str(service_name)
            + "` as of "
            + str(last_seen)
        )
        slack.send_message(message)

    # Close PagerDuty alert if one exists
    pd_key = ar[0][4]
    if pd_key and pd_key != "" and pd_key != "NULL":
        pagerduty.close_alert(pd_key)
    else:
        logger.log(level=20, msg="No PagerDuty alert to close for alert: " + str(ar[0]))


def color_code(severity):
    if severity == "p1":
        return "#F35A00"
    elif severity == "p2":
        return "#e9a820"
    elif severity == "p3":
        return "#e9a820"
    else:
        return "#F35A00"


def checkForStaleJobs():
    """
    Check for jobs that started but haven't completed within max_duration.

    Sends alerts for stale jobs and marks them as alerted to prevent
    duplicate notifications.
    """
    if not DURATION_ALERTS_AVAILABLE:
        return

    try:
        stale_alerts = get_stale_runs_exceeding_max_duration()
        update_stale_jobs_count(len(stale_alerts))

        for alert in stale_alerts:
            # Check if service is in maintenance window
            if MAINTENANCE_WINDOWS_AVAILABLE and is_service_in_maintenance(
                alert.service_id
            ):
                window = get_active_maintenance_window_for_service(alert.service_id)
                window_name = window.name if window else "Unknown"
                logger.log(
                    level=20,
                    msg=f"Stale job alert suppressed for {alert.service_name}: "
                    f"service is in maintenance window '{window_name}'",
                )
                continue

            # Send alert for stale job
            sendStaleJobAlert(alert)

            # Mark as alerted to prevent duplicate alerts
            mark_stale_run_alerted(alert.service_id, alert.run_id)

            # Record metric
            record_duration_alert("stale")

    except Exception as e:
        logger.log(level=40, msg=f"Error checking for stale jobs: {str(e)}")


def sendStaleJobAlert(alert):
    """
    Send an alert for a stale job that has exceeded max_duration.

    Args:
        alert: DurationAlert object containing stale job information
    """
    # Get service info for team routing
    service_info = query_db(
        "SELECT team, priority, muted FROM services WHERE service_id = %s",
        (alert.service_id,),
        show_columns=True,
    )

    if not service_info:
        logger.log(
            level=30,
            msg=f"Could not find service info for stale job alert: "
            f"service_id={alert.service_id}",
        )
        return

    service = service_info[0]
    team = service.get("team", "site-reliability")
    priority = service.get("priority", "p3")
    muted = service.get("muted", 0)

    if muted == 1:
        logger.log(
            level=20,
            msg=f"Stale job alert suppressed for {alert.service_name}: "
            f"service is muted",
        )
        return

    # Calculate elapsed time in human-readable format
    elapsed_seconds = (alert.duration_ms or 0) // 1000
    elapsed_minutes = elapsed_seconds // 60
    elapsed_hours = elapsed_minutes // 60

    if elapsed_hours > 0:
        elapsed_str = f"{elapsed_hours}h {elapsed_minutes % 60}m"
    elif elapsed_minutes > 0:
        elapsed_str = f"{elapsed_minutes}m {elapsed_seconds % 60}s"
    else:
        elapsed_str = f"{elapsed_seconds}s"

    max_seconds = alert.max_duration_ms // 1000
    max_minutes = max_seconds // 60

    if max_minutes > 0:
        max_str = f"{max_minutes}m {max_seconds % 60}s"
    else:
        max_str = f"{max_seconds}s"

    alert_message = f"Medic - Stale job detected for {alert.service_name}"

    # Send PagerDuty alert
    pagerduty.create_alert(
        alert_message=alert_message,
        service_name=alert.service_name,
        heartbeat_name=alert.service_name,
        team=team,
        priority=priority,
        runbook=None,
    )

    # Send Slack message
    message = (
        f":hourglass: Stale job detected for `{alert.service_name}` "
        f"(run_id: `{alert.run_id}`). "
        f"Job has been running for {elapsed_str}, "
        f"exceeding max duration of {max_str}. "
        f"Alert routed to `{team}`."
    )
    slack.send_message(message)

    logger.log(
        level=30,
        msg=f"Stale job alert sent for {alert.service_name} "
        f"(run_id: {alert.run_id})",
    )


def thread_function():
    t = threading.Thread(target=queryForNoHeartbeat)
    logger.log(level=20, msg="Thread starting.")
    t.start()

    # Also check for stale jobs
    if DURATION_ALERTS_AVAILABLE:
        t2 = threading.Thread(target=checkForStaleJobs)
        t2.start()


if __name__ == "__main__":
    # Initialize telemetry for the worker
    if TELEMETRY_AVAILABLE and init_worker_telemetry is not None:
        telemetry_enabled = os.environ.get("OTEL_ENABLED", "true").lower() == "true"
        init_worker_telemetry(service_name="medic-worker", enable=telemetry_enabled)
        logger.log(
            level=20, msg=f"Worker telemetry initialized (enabled={telemetry_enabled})"
        )

    # Start metrics HTTP server for Prometheus scraping
    if METRICS_AVAILABLE and start_metrics_server is not None:
        metrics_port = int(os.environ.get("METRICS_PORT", DEFAULT_METRICS_PORT))
        try:
            start_metrics_server(metrics_port)
            logger.log(level=20, msg=f"Metrics server started on port {metrics_port}")
        except Exception as e:
            logger.log(level=40, msg=f"Failed to start metrics server: {e}")

    try:
        while True:
            thread_function()
            time.sleep(15)
    except KeyboardInterrupt:
        logger.log(level=20, msg="Worker shutting down...")
        if TELEMETRY_AVAILABLE and shutdown_telemetry is not None:
            shutdown_telemetry()

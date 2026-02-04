"""Job runs tracking for duration statistics.

This module handles tracking job durations by correlating STARTED and
COMPLETED/FAILED signals. It stores job run data in the medic.job_runs
table for duration statistics and timeout detection.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

import pytz

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


@dataclass
class JobRun:
    """Represents a job run with duration tracking."""
    run_id_pk: Optional[int]
    service_id: int
    run_id: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: str = "STARTED"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id_pk": self.run_id_pk,
            "service_id": self.service_id,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_ms": self.duration_ms,
            "status": self.status
        }


def record_job_start(
    service_id: int,
    run_id: str,
    started_at: Optional[datetime] = None
) -> Optional[JobRun]:
    """
    Record the start of a job run.

    Creates a new entry in the job_runs table with STARTED status.
    If a run with the same service_id and run_id already exists,
    returns None (duplicate start).

    Args:
        service_id: The service ID
        run_id: Client-provided run identifier
        started_at: Optional start time (defaults to now)

    Returns:
        JobRun object on success, None on failure or duplicate
    """
    if started_at is None:
        started_at = datetime.now(pytz.timezone('America/Chicago'))

    # Check if run already exists
    existing = db.query_db(
        "SELECT run_id_pk FROM medic.job_runs "
        "WHERE service_id = %s AND run_id = %s",
        (service_id, run_id),
        show_columns=True
    )

    if existing and existing != '[]':
        logger.log(
            level=20,
            msg=f"Job run already exists for service {service_id}, "
                f"run_id {run_id}"
        )
        return None

    # Insert new job run
    result = db.insert_db(
        "INSERT INTO medic.job_runs "
        "(service_id, run_id, started_at, status) "
        "VALUES (%s, %s, %s, %s)",
        (service_id, run_id, started_at, "STARTED")
    )

    if not result:
        logger.log(
            level=40,
            msg=f"Failed to insert job run for service {service_id}, "
                f"run_id {run_id}"
        )
        return None

    logger.log(
        level=10,
        msg=f"Recorded job start for service {service_id}, run_id {run_id}"
    )

    return JobRun(
        run_id_pk=None,  # Not fetched, would need RETURNING clause
        service_id=service_id,
        run_id=run_id,
        started_at=started_at,
        status="STARTED"
    )


def record_job_completion(
    service_id: int,
    run_id: str,
    status: str,
    completed_at: Optional[datetime] = None
) -> Optional[JobRun]:
    """
    Record the completion of a job run.

    Updates an existing job run with completion time and calculates duration.
    If no matching STARTED run exists, creates a new record with only
    completion data (duration will be NULL).

    Args:
        service_id: The service ID
        run_id: Client-provided run identifier
        status: Final status (COMPLETED or FAILED)
        completed_at: Optional completion time (defaults to now)

    Returns:
        JobRun object on success, None on failure
    """
    if status not in ("COMPLETED", "FAILED"):
        logger.log(level=30, msg=f"Invalid completion status: {status}")
        return None

    if completed_at is None:
        completed_at = datetime.now(pytz.timezone('America/Chicago'))

    # Find existing STARTED run
    import json
    existing = db.query_db(
        "SELECT run_id_pk, started_at FROM medic.job_runs "
        "WHERE service_id = %s AND run_id = %s AND status = 'STARTED'",
        (service_id, run_id),
        show_columns=True
    )

    if existing and existing != '[]':
        # Update existing run with completion
        runs = json.loads(str(existing))
        if runs:
            run_data = runs[0]
            started_at = run_data['started_at']

            # Parse started_at if it's a string
            if isinstance(started_at, str):
                # Handle various timestamp formats
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S.%f%z",
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%d %H:%M:%S %Z",
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S"
                ]:
                    try:
                        started_at = datetime.strptime(started_at, fmt)
                        break
                    except ValueError:
                        continue

            # Calculate duration in milliseconds
            if isinstance(started_at, datetime):
                # Ensure both datetimes are timezone-aware for comparison
                if started_at.tzinfo is None:
                    started_at = pytz.timezone('America/Chicago').localize(
                        started_at
                    )
                if completed_at.tzinfo is None:
                    completed_at = pytz.timezone('America/Chicago').localize(
                        completed_at
                    )
                duration_delta = completed_at - started_at
                duration_ms = int(duration_delta.total_seconds() * 1000)
            else:
                duration_ms = None

            # Update the run
            result = db.insert_db(
                "UPDATE medic.job_runs SET "
                "completed_at = %s, duration_ms = %s, status = %s, "
                "updated_at = NOW() "
                "WHERE service_id = %s AND run_id = %s AND status = 'STARTED'",
                (completed_at, duration_ms, status, service_id, run_id)
            )

            if result:
                logger.log(
                    level=10,
                    msg=f"Recorded job completion for service {service_id}, "
                        f"run_id {run_id}, duration_ms={duration_ms}"
                )
                # started_at may be datetime or None at this point
                final_started: Optional[datetime] = (
                    started_at if isinstance(started_at, datetime) else None
                )
                return JobRun(
                    run_id_pk=run_data['run_id_pk'],
                    service_id=service_id,
                    run_id=run_id,
                    started_at=final_started,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    status=status
                )
    else:
        # No STARTED run found, create a new record with only completion
        logger.log(
            level=20,
            msg=f"No STARTED run found for service {service_id}, "
                f"run_id {run_id}. Creating completion-only record."
        )
        result = db.insert_db(
            "INSERT INTO medic.job_runs "
            "(service_id, run_id, started_at, completed_at, status) "
            "VALUES (%s, %s, %s, %s, %s)",
            (service_id, run_id, completed_at, completed_at, status)
        )

        if result:
            return JobRun(
                run_id_pk=None,
                service_id=service_id,
                run_id=run_id,
                started_at=completed_at,
                completed_at=completed_at,
                duration_ms=0,  # No start time, so duration is 0
                status=status
            )

    logger.log(
        level=40,
        msg=f"Failed to record job completion for service {service_id}, "
            f"run_id {run_id}"
    )
    return None


def get_job_run(service_id: int, run_id: str) -> Optional[JobRun]:
    """
    Get a job run by service_id and run_id.

    Args:
        service_id: The service ID
        run_id: Client-provided run identifier

    Returns:
        JobRun object if found, None otherwise
    """
    import json
    result = db.query_db(
        "SELECT run_id_pk, service_id, run_id, started_at, completed_at, "
        "duration_ms, status FROM medic.job_runs "
        "WHERE service_id = %s AND run_id = %s",
        (service_id, run_id),
        show_columns=True
    )

    if not result or result == '[]':
        return None

    runs = json.loads(str(result))
    if not runs:
        return None

    run_data = runs[0]
    return _parse_job_run(run_data)


def get_completed_runs_for_service(
    service_id: int,
    limit: int = 100
) -> List[JobRun]:
    """
    Get completed job runs for a service, ordered by completion time desc.

    Only returns runs where duration_ms is not NULL (i.e., has valid timing).

    Args:
        service_id: The service ID
        limit: Maximum number of runs to return (default 100)

    Returns:
        List of JobRun objects
    """
    import json
    result = db.query_db(
        "SELECT run_id_pk, service_id, run_id, started_at, completed_at, "
        "duration_ms, status FROM medic.job_runs "
        "WHERE service_id = %s AND completed_at IS NOT NULL "
        "AND duration_ms IS NOT NULL "
        "ORDER BY completed_at DESC LIMIT %s",
        (service_id, limit),
        show_columns=True
    )

    if not result or result == '[]':
        return []

    runs = json.loads(str(result))
    return [jr for jr in (_parse_job_run(r) for r in runs if r) if jr]


def get_stale_runs(
    service_id: Optional[int] = None,
    older_than_seconds: int = 3600
) -> List[JobRun]:
    """
    Get job runs that started but haven't completed within the threshold.

    Args:
        service_id: Optional service ID to filter by
        older_than_seconds: Threshold in seconds (default 1 hour)

    Returns:
        List of stale JobRun objects
    """
    import json
    if service_id is not None:
        result = db.query_db(
            "SELECT run_id_pk, service_id, run_id, started_at, completed_at, "
            "duration_ms, status FROM medic.job_runs "
            "WHERE service_id = %s AND status = 'STARTED' "
            "AND completed_at IS NULL "
            "AND started_at < NOW() - INTERVAL '%s seconds' "
            "ORDER BY started_at ASC",
            (service_id, older_than_seconds),
            show_columns=True
        )
    else:
        result = db.query_db(
            "SELECT run_id_pk, service_id, run_id, started_at, completed_at, "
            "duration_ms, status FROM medic.job_runs "
            "WHERE status = 'STARTED' AND completed_at IS NULL "
            "AND started_at < NOW() - INTERVAL '%s seconds' "
            "ORDER BY started_at ASC",
            (older_than_seconds,),
            show_columns=True
        )

    if not result or result == '[]':
        return []

    runs = json.loads(str(result))
    return [jr for jr in (_parse_job_run(r) for r in runs if r) if jr]


def _parse_job_run(data: Dict[str, Any]) -> Optional[JobRun]:
    """Parse a database row into a JobRun object."""
    try:
        started_at = data.get('started_at')
        completed_at = data.get('completed_at')

        # Parse datetime strings if needed
        if isinstance(started_at, str):
            started_at = _parse_datetime(started_at)
        if isinstance(completed_at, str):
            completed_at = _parse_datetime(completed_at)

        return JobRun(
            run_id_pk=data.get('run_id_pk'),
            service_id=data['service_id'],
            run_id=data['run_id'],
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=data.get('duration_ms'),
            status=data.get('status', 'STARTED')
        )
    except (KeyError, TypeError) as e:
        logger.log(level=30, msg=f"Failed to parse job run data: {e}")
        return None


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse a datetime string in various formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


@dataclass
class DurationStatistics:
    """Duration statistics for a service's job runs."""
    service_id: int
    run_count: int
    avg_duration_ms: Optional[float] = None
    p50_duration_ms: Optional[int] = None
    p95_duration_ms: Optional[int] = None
    p99_duration_ms: Optional[int] = None
    min_duration_ms: Optional[int] = None
    max_duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_id": self.service_id,
            "run_count": self.run_count,
            "avg_duration_ms": self.avg_duration_ms,
            "p50_duration_ms": self.p50_duration_ms,
            "p95_duration_ms": self.p95_duration_ms,
            "p99_duration_ms": self.p99_duration_ms,
            "min_duration_ms": self.min_duration_ms,
            "max_duration_ms": self.max_duration_ms
        }


def get_duration_statistics(
    service_id: int,
    min_runs: int = 5,
    max_runs: int = 100
) -> DurationStatistics:
    """
    Calculate duration statistics for a service's job runs.

    Returns avg, p50, p95, p99 durations from the last max_runs completed runs.
    Returns empty stats if fewer than min_runs runs are available.

    Args:
        service_id: The service ID
        min_runs: Minimum number of runs required for stats (default 5)
        max_runs: Maximum number of runs to consider (default 100)

    Returns:
        DurationStatistics object with calculated percentiles
    """
    runs = get_completed_runs_for_service(service_id, limit=max_runs)

    if len(runs) < min_runs:
        return DurationStatistics(
            service_id=service_id,
            run_count=len(runs)
        )

    # Extract duration values, filtering out None
    durations = [
        r.duration_ms for r in runs
        if r.duration_ms is not None and r.duration_ms >= 0
    ]

    if len(durations) < min_runs:
        return DurationStatistics(
            service_id=service_id,
            run_count=len(runs)
        )

    # Sort for percentile calculations
    durations_sorted = sorted(durations)
    n = len(durations_sorted)

    # Calculate statistics
    avg_duration = sum(durations) / n
    min_duration = durations_sorted[0]
    max_duration = durations_sorted[-1]

    # Percentile calculation using linear interpolation
    p50 = _percentile(durations_sorted, 50)
    p95 = _percentile(durations_sorted, 95)
    p99 = _percentile(durations_sorted, 99)

    return DurationStatistics(
        service_id=service_id,
        run_count=n,
        avg_duration_ms=round(avg_duration, 2),
        p50_duration_ms=p50,
        p95_duration_ms=p95,
        p99_duration_ms=p99,
        min_duration_ms=min_duration,
        max_duration_ms=max_duration
    )


def _percentile(sorted_data: List[int], p: float) -> int:
    """
    Calculate the p-th percentile of sorted data.

    Uses linear interpolation (same as numpy's default).

    Args:
        sorted_data: Sorted list of values
        p: Percentile to calculate (0-100)

    Returns:
        Percentile value as integer
    """
    n = len(sorted_data)
    if n == 0:
        return 0
    if n == 1:
        return sorted_data[0]

    # Calculate index using linear interpolation
    k = (n - 1) * (p / 100.0)
    f = int(k)
    c = f + 1 if f + 1 < n else f

    # Linear interpolation between floor and ceiling values
    if f == c:
        return sorted_data[f]

    d = k - f
    return int(sorted_data[f] * (1 - d) + sorted_data[c] * d)


@dataclass
class DurationAlert:
    """Represents a duration threshold alert."""
    service_id: int
    service_name: str
    run_id: str
    alert_type: str  # "exceeded" or "stale"
    duration_ms: Optional[int]
    max_duration_ms: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "run_id": self.run_id,
            "alert_type": self.alert_type,
            "duration_ms": self.duration_ms,
            "max_duration_ms": self.max_duration_ms,
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            )
        }


def get_service_max_duration(service_id: int) -> Optional[int]:
    """
    Get the max_duration_ms for a service.

    Args:
        service_id: The service ID

    Returns:
        max_duration_ms if configured, None otherwise
    """
    import json
    result = db.query_db(
        "SELECT max_duration_ms FROM services WHERE service_id = %s",
        (service_id,),
        show_columns=True
    )

    if not result or result == '[]':
        return None

    services = json.loads(str(result))
    if not services:
        return None

    return services[0].get('max_duration_ms')


def check_duration_threshold(
    job_run: JobRun,
    max_duration_ms: Optional[int] = None
) -> Optional[DurationAlert]:
    """
    Check if a completed job's duration exceeds the threshold.

    Args:
        job_run: The completed JobRun to check
        max_duration_ms: Optional override for max duration threshold.
                        If not provided, fetches from service config.

    Returns:
        DurationAlert if threshold exceeded, None otherwise
    """
    if job_run.duration_ms is None:
        return None

    # Get max_duration from service config if not provided
    if max_duration_ms is None:
        max_duration_ms = get_service_max_duration(job_run.service_id)

    if max_duration_ms is None or max_duration_ms <= 0:
        # No threshold configured
        return None

    if job_run.duration_ms > max_duration_ms:
        # Get service name for alert
        import json
        service_result = db.query_db(
            "SELECT heartbeat_name FROM services WHERE service_id = %s",
            (job_run.service_id,),
            show_columns=True
        )
        service_name = "Unknown"
        if service_result and service_result != '[]':
            services = json.loads(str(service_result))
            if services:
                service_name = services[0].get('heartbeat_name', 'Unknown')

        logger.log(
            level=30,
            msg=f"Duration threshold exceeded for service {service_name} "
                f"(ID: {job_run.service_id}): {job_run.duration_ms}ms > "
                f"{max_duration_ms}ms (run_id: {job_run.run_id})"
        )

        return DurationAlert(
            service_id=job_run.service_id,
            service_name=service_name,
            run_id=job_run.run_id,
            alert_type="exceeded",
            duration_ms=job_run.duration_ms,
            max_duration_ms=max_duration_ms,
            started_at=job_run.started_at,
            completed_at=job_run.completed_at
        )

    return None


def get_stale_runs_exceeding_max_duration(
    check_time: Optional[datetime] = None
) -> List[DurationAlert]:
    """
    Find jobs that started but haven't completed and have exceeded
    their service's max_duration threshold.

    This is used to detect hung/stale jobs that are taking too long.

    Args:
        check_time: Optional time to check against (defaults to now)

    Returns:
        List of DurationAlert objects for stale jobs exceeding threshold
    """
    import json
    if check_time is None:
        check_time = datetime.now(pytz.timezone('America/Chicago'))

    # Query for STARTED jobs with services that have max_duration configured
    # Join with services to get max_duration_ms and heartbeat_name
    result = db.query_db(
        """
        SELECT jr.run_id_pk, jr.service_id, jr.run_id, jr.started_at,
               jr.completed_at, jr.duration_ms, jr.status,
               s.max_duration_ms, s.heartbeat_name
        FROM medic.job_runs jr
        JOIN services s ON s.service_id = jr.service_id
        WHERE jr.status = 'STARTED'
          AND jr.completed_at IS NULL
          AND s.max_duration_ms IS NOT NULL
          AND s.max_duration_ms > 0
        ORDER BY jr.started_at ASC
        """,
        show_columns=True
    )

    if not result or result == '[]':
        return []

    alerts: List[DurationAlert] = []
    runs = json.loads(str(result))

    for run_data in runs:
        started_at = run_data.get('started_at')
        max_duration_ms = run_data.get('max_duration_ms')

        if started_at is None or max_duration_ms is None:
            continue

        # Parse started_at if string
        if isinstance(started_at, str):
            started_at = _parse_datetime(started_at)

        if started_at is None:
            continue

        # Ensure timezone awareness
        if started_at.tzinfo is None:
            started_at = pytz.timezone('America/Chicago').localize(started_at)
        if check_time.tzinfo is None:
            check_time = pytz.timezone('America/Chicago').localize(check_time)

        # Calculate elapsed time
        elapsed_ms = int((check_time - started_at).total_seconds() * 1000)

        if elapsed_ms > max_duration_ms:
            logger.log(
                level=30,
                msg=f"Stale job detected for service "
                    f"{run_data.get('heartbeat_name', 'Unknown')} "
                    f"(ID: {run_data['service_id']}): running for "
                    f"{elapsed_ms}ms > {max_duration_ms}ms max "
                    f"(run_id: {run_data['run_id']})"
            )

            alerts.append(DurationAlert(
                service_id=run_data['service_id'],
                service_name=run_data.get('heartbeat_name', 'Unknown'),
                run_id=run_data['run_id'],
                alert_type="stale",
                duration_ms=elapsed_ms,
                max_duration_ms=max_duration_ms,
                started_at=started_at,
                completed_at=None
            ))

    return alerts


def mark_stale_run_alerted(service_id: int, run_id: str) -> bool:
    """
    Mark a stale run as having been alerted to prevent duplicate alerts.

    Updates the job run status to 'STALE_ALERTED'.

    Args:
        service_id: The service ID
        run_id: The run ID

    Returns:
        True if updated successfully, False otherwise
    """
    result = db.insert_db(
        "UPDATE medic.job_runs SET status = 'STALE_ALERTED', "
        "updated_at = NOW() "
        "WHERE service_id = %s AND run_id = %s AND status = 'STARTED'",
        (service_id, run_id)
    )

    if result:
        logger.log(
            level=20,
            msg=f"Marked stale run as alerted: service {service_id}, "
                f"run_id {run_id}"
        )

    return result if result else False

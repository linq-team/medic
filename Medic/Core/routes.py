"""Flask routes for Medic API."""
from flask import request, send_file, Response
from flask_swagger_ui import get_swaggerui_blueprint
from datetime import datetime
import pytz
from cerberus import Validator
import os
import json
import logging

import Medic.Core.database as db
import Medic.Core.metrics as metrics
import Medic.Core.health as health
import Medic.Core.job_runs as job_runs
import Medic.Helpers.heartbeat as hbeat
import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


def exposeRoutes(app):
    """Register all routes with the Flask app."""
    ### swagger config ###
    SWAGGER_URL = '/docs'
    API_URL = '/docs/swagger.json'
    SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            'app_name': "Medic"
        }
    )
    app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)
    ### end swagger config ###

    @app.route('/v1/healthcheck/network')
    def healthcheck():
        return '{"success":true,"message":"","results":""}', 204

    @app.route('/health')
    def health_check():
        """Comprehensive health check endpoint."""
        status = health.get_full_health_status()
        http_status = 200 if status["status"] == "healthy" else 503
        return json.dumps(status), http_status

    @app.route('/health/live')
    def liveness():
        """Kubernetes liveness probe endpoint."""
        return json.dumps(health.get_liveness_status()), 200

    @app.route('/health/ready')
    def readiness():
        """Kubernetes readiness probe endpoint."""
        status = health.get_readiness_status()
        http_status = 200 if status["status"] == "ready" else 503
        return json.dumps(status), http_status

    @app.route('/metrics')
    def prometheus_metrics():
        """Prometheus metrics endpoint."""
        return Response(
            metrics.get_metrics(),
            mimetype=metrics.get_metrics_content_type()
        )

    @app.route('/heartbeat', methods=['POST', 'GET'])
    def heartbeat():
        if request.method == 'POST':
            data = request.data
            jData = json.loads(data)
            request_schema = {
                'heartbeat_name': {'type': 'string', 'required': True},
                'service_name': {'type': 'string', 'required': False},
                'status': {'type': 'string', 'required': True}
            }
            if validateRequestData(request_schema, jData):
                heartbeat_name = jData['heartbeat_name']
                status = jData['status']

                # Use parameterized query
                heartbeat_check = db.query_db(
                    "SELECT * FROM services WHERE LOWER(heartbeat_name) = LOWER(%s) LIMIT 1",
                    (heartbeat_name,),
                    show_columns=True
                )
                if heartbeat_check and heartbeat_check != '[]':
                    heartbeats = json.loads(heartbeat_check)
                    for h in heartbeats:
                        active = h['active']
                        s_id = h['service_id']
                        if not h:
                            logger.log(level=30, msg=f"Unable to locate heartbeat: {heartbeat_name}. Does it exist?")
                            return json.dumps({
                                "success": False,
                                "message": f"{heartbeat_name} is not listed as a registered heartbeat.",
                                "results": ""
                            }), 404
                        else:
                            if int(active) == 0:
                                logger.log(level=30, msg=f"{heartbeat_name} was located, but is marked inactive. Unable to post heartbeat.")
                                return json.dumps({
                                    "success": False,
                                    "message": f"{heartbeat_name} was located, but is marked inactive. Does this need to be re-enabled?",
                                    "results": ""
                                }), 400
                            else:
                                my_heartbeat = hbeat.Heartbeat(s_id, heartbeat_name, status)
                                res = hbeat.addHeartbeat(my_heartbeat)
                                if res:
                                    logger.log(level=10, msg=f"{heartbeat_name} was posted successfully.")
                                    return json.dumps({
                                        "success": True,
                                        "message": "Heartbeat Posted Successfully.",
                                        "results": ""
                                    }), 201
                                else:
                                    logger.log(level=40, msg=f"{heartbeat_name} Failed to post heartbeat.")
                                    return json.dumps({
                                        "success": False,
                                        "message": "Failed to post heartbeat.",
                                        "results": ""
                                    }), 400
                else:
                    logger.log(level=30, msg=f"No matches found for service {heartbeat_name}")
                    return json.dumps({
                        "success": False,
                        "message": f"{heartbeat_name} is not listed as a registered service.",
                        "results": ""
                    }), 404
            else:
                logger.log(level=30, msg="Submitted invalid parameters. Aborting request.")
                return json.dumps({
                    "success": False,
                    "message": "You have provided invalid request data. Please ensure your request contains data in both `heartbeat_name` and `status` JSON fields.",
                    "results": ""
                }), 400
        else:
            # GET request for targeted lookup
            heartbeat_name = request.args.get('heartbeat_name')
            service_name = request.args.get('service_name')
            max_count = request.args.get('maxCount')

            # Validate and set maxCount
            if max_count:
                try:
                    max_count = min(int(max_count), 250)
                except ValueError:
                    max_count = 250
            else:
                max_count = 250

            base_query = """
                SELECT heartbeat_id, services.heartbeat_name, services.service_name,
                       time, status, team, priority
                FROM "heartbeatEvents" h
                JOIN services ON services.service_id = h.service_id
            """

            if service_name and heartbeat_name:
                query = base_query + " WHERE services.heartbeat_name = %s AND services.service_name = %s ORDER BY h.time DESC LIMIT %s"
                results = db.query_db(query, (heartbeat_name, service_name, max_count), show_columns=True)
            elif heartbeat_name:
                query = base_query + " WHERE services.heartbeat_name = %s ORDER BY h.time DESC LIMIT %s"
                results = db.query_db(query, (heartbeat_name, max_count), show_columns=True)
            elif service_name:
                query = base_query + " WHERE services.service_name = %s ORDER BY h.time DESC LIMIT %s"
                results = db.query_db(query, (service_name, max_count), show_columns=True)
            else:
                query = base_query + " ORDER BY h.time DESC LIMIT %s"
                results = db.query_db(query, (max_count,), show_columns=True)

            logger.log(level=10, msg=f"Heartbeat query results: {results}")
            return json.dumps({
                "success": True,
                "message": "",
                "results": json.loads(results) if results else []
            }), 200

    @app.route('/service', methods=['POST', 'GET'])
    def service():
        if request.method == 'POST':
            data = request.data
            jData = json.loads(data)
            r_schema = {
                'heartbeat_name': {'type': 'string', 'required': True},
                'service_name': {'type': 'string', 'required': True},
                'environment': {'type': 'string', 'required': False},
                'alert_interval': {'type': 'integer', 'required': True},
                'threshold': {'type': 'integer', 'required': False},
                'team': {'type': 'string', 'required': False},
                'priority': {'type': 'string', 'required': False},
                'runbook': {'type': 'string', 'required': False}
            }
            if validateRequestData(r_schema, jData):
                environment = jData.get("environment", "")
                if environment:
                    environment = environment + "-"
                heartbeat_name = environment + jData["heartbeat_name"]
                service_name = jData["service_name"]
                alert_interval = jData["alert_interval"]

                # Set non-required variables to defaults
                team = jData.get("team", "site-reliability")
                priority = jData.get("priority", "p3")
                threshold = jData.get("threshold", 1)
                runbook = jData.get("runbook")

                # Check if service is already registered
                check_result = db.query_db(
                    "SELECT COUNT(heartbeat_name) FROM services WHERE heartbeat_name = %s",
                    (heartbeat_name,),
                    show_columns=False
                )
                if check_result and int(check_result[0][0]) < 1:
                    # Service is not registered, register it
                    now = datetime.now(pytz.timezone('America/Chicago')).strftime("%Y-%m-%d %H:%M:%S %Z")
                    db.insert_db(
                        """INSERT INTO services(heartbeat_name, service_name, active, alert_interval,
                           threshold, team, priority, runbook, date_added)
                           VALUES(%s, %s, 1, %s, %s, %s, %s, %s, %s)""",
                        (heartbeat_name, service_name, alert_interval, threshold, team, priority, runbook, now)
                    )
                    return json.dumps({
                        "success": True,
                        "message": "Heartbeat successfully registered.",
                        "results": ""
                    }), 201
                else:
                    return json.dumps({
                        "success": True,
                        "message": "Heartbeat is already registered.",
                        "results": ""
                    }), 200
            else:
                logger.log(level=30, msg="Submitted invalid parameters. Aborting request.")
                return json.dumps({
                    "success": False,
                    "message": "You have provided invalid request data. Please ensure your request contains the following required JSON fields - `heartbeat_name`, `service_name`, `alert_interval` & `environment`",
                    "results": ""
                }), 400
        else:
            # GET request
            service_name = request.args.get('service_name')
            active = request.args.get('active')

            if service_name and active is not None:
                # Validate active is integer
                try:
                    active_int = int(active)
                except ValueError:
                    return json.dumps({
                        "success": False,
                        "message": "Invalid 'active' parameter",
                        "results": ""
                    }), 400
                query = "SELECT * FROM services WHERE service_name = %s AND active = %s"
                res = db.query_db(query, (service_name, active_int), show_columns=True)
            elif service_name:
                query = "SELECT * FROM services WHERE service_name = %s"
                res = db.query_db(query, (service_name,), show_columns=True)
            elif active is not None:
                try:
                    active_int = int(active)
                except ValueError:
                    return json.dumps({
                        "success": False,
                        "message": "Invalid 'active' parameter",
                        "results": ""
                    }), 400
                query = "SELECT * FROM services WHERE active = %s"
                res = db.query_db(query, (active_int,), show_columns=True)
            else:
                query = "SELECT * FROM services"
                res = db.query_db(query, show_columns=True)

            return json.dumps({
                "success": True,
                "message": "",
                "results": json.loads(res) if res else []
            }), 200

    @app.route('/service/<string:heartbeat_name>', methods=['GET', 'POST'])
    def serviceByHeartbeatName(heartbeat_name):
        if request.method == 'POST':
            # Verify Service Name
            s = db.query_db(
                "SELECT service_id FROM services WHERE LOWER(heartbeat_name) = LOWER(%s) LIMIT 1",
                (heartbeat_name,),
                show_columns=True
            )
            if not s or s == '[]':
                return json.dumps({
                    "success": False,
                    "message": f"The heartbeat registration specified: {heartbeat_name} was not located. Does it exist?",
                    "results": ""
                }), 200

            service_result = json.loads(s)
            service_id = service_result[0]['service_id']

            data = request.data
            jData = json.loads(data)
            s_schema = {
                'service_name': {'type': 'string', 'required': False},
                'muted': {'type': 'integer', 'required': False},
                'active': {'type': 'integer', 'required': False},
                'alert_interval': {'type': 'float', 'required': False},
                'threshold': {'type': 'integer', 'required': False},
                'team': {'type': 'string', 'required': False},
                'priority': {'type': 'string', 'required': False},
                'runbook': {'type': 'string', 'required': False},
                'down': {'type': 'integer', 'required': False}
            }
            if validateRequestData(s_schema, jData):
                # Build update dynamically using parameterized queries
                updates = []
                params = []

                if 'service_name' in jData:
                    updates.append("service_name = %s")
                    params.append(jData['service_name'])

                if 'muted' in jData:
                    updates.append("muted = %s")
                    params.append(jData['muted'])
                    if jData['muted'] == 0:
                        updates.append("date_muted = NULL")
                    else:
                        updates.append("date_muted = %s")
                        params.append(datetime.now(pytz.timezone('America/Chicago')).strftime("%Y-%m-%d %H:%M:%S %Z"))

                if 'active' in jData:
                    updates.append("active = %s")
                    params.append(jData['active'])

                if 'alert_interval' in jData:
                    updates.append("alert_interval = %s")
                    params.append(jData['alert_interval'])

                if 'threshold' in jData:
                    updates.append("threshold = %s")
                    params.append(jData['threshold'])

                if 'team' in jData:
                    updates.append("team = %s")
                    params.append(jData['team'])

                if 'priority' in jData:
                    updates.append("priority = %s")
                    params.append(jData['priority'])

                if 'runbook' in jData:
                    updates.append("runbook = %s")
                    params.append(jData['runbook'])

                if 'down' in jData:
                    updates.append("down = %s")
                    params.append(jData['down'])

                # Always update date_modified
                updates.append("date_modified = %s")
                params.append(datetime.now(pytz.timezone('America/Chicago')).strftime("%Y-%m-%d %H:%M:%S %Z"))

                # Add service_id to params
                params.append(service_id)

                if updates:
                    query = f"UPDATE services SET {', '.join(updates)} WHERE service_id = %s"
                    logger.log(level=10, msg=f"Update query: {query}")
                    db.insert_db(query, tuple(params))

                return json.dumps({
                    "success": True,
                    "message": "Successfully posted update",
                    "results": ""
                }), 200
            else:
                logger.log(level=30, msg="Submitted invalid parameters. Aborting request.")
                return json.dumps({
                    "success": False,
                    "message": "You have provided invalid request data. Please ensure your request contains data in the correct JSON fields.",
                    "results": ""
                }), 400
        else:
            # GET
            res = db.query_db(
                "SELECT * FROM services WHERE LOWER(heartbeat_name) = LOWER(%s)",
                (heartbeat_name,),
                show_columns=True
            )
            logger.log(level=10, msg=f"Service query results: {res}")
            return json.dumps({
                "success": True,
                "message": "",
                "results": json.loads(res) if res else []
            }), 200

    @app.route('/alerts', methods=['GET'])
    def alerts():
        a_query = request.args.get('active')
        if a_query is not None:
            try:
                active_int = int(a_query)
            except ValueError:
                return json.dumps({
                    "success": False,
                    "message": "Invalid 'active' parameter",
                    "results": ""
                }), 400
            query = "SELECT * FROM alerts WHERE active = %s ORDER BY alert_id DESC"
            res = db.query_db(query, (active_int,), show_columns=True)
        else:
            query = "SELECT * FROM alerts ORDER BY alert_id DESC LIMIT 100"
            res = db.query_db(query, show_columns=True)

        return json.dumps({
            "success": True,
            "message": "",
            "results": json.loads(res) if res else []
        }), 200

    @app.route('/docs/swagger.json')
    def swaggerDocs():
        try:
            return send_file(os.path.abspath('Medic/Docs/swagger.json'))
        except Exception as e:
            logger.log(level=40, msg=f"Unable to load swagger file: {str(e)}")
            return json.dumps({
                "success": False,
                "message": "Unable to load swagger file",
                "results": ""
            }), 500

    # V2 API Endpoints for Start/Complete/Fail Signals
    @app.route('/v2/heartbeat/<int:service_id>/start', methods=['POST'])
    def heartbeat_start(service_id):
        """Record a STARTED status for a service with optional run_id."""
        return _record_job_signal(
            service_id,
            hbeat.HeartbeatStatus.STARTED.value
        )

    @app.route('/v2/heartbeat/<int:service_id>/complete', methods=['POST'])
    def heartbeat_complete(service_id):
        """Record a COMPLETED status for a service with optional run_id."""
        return _record_job_signal(
            service_id,
            hbeat.HeartbeatStatus.COMPLETED.value
        )

    @app.route('/v2/heartbeat/<int:service_id>/fail', methods=['POST'])
    def heartbeat_fail(service_id):
        """Record a FAILED status for a service with optional run_id."""
        return _record_job_signal(
            service_id,
            hbeat.HeartbeatStatus.FAILED.value
        )

    @app.route('/v2/services/<int:service_id>/stats', methods=['GET'])
    def service_duration_stats(service_id):
        """
        Get duration statistics for a service's job runs.

        Returns avg, p50, p95, p99 durations from the last 100 completed runs.
        Returns empty stats (null values) if fewer than 5 runs are available.
        """
        # Verify service exists
        service_check = db.query_db(
            "SELECT service_id, heartbeat_name FROM services "
            "WHERE service_id = %s LIMIT 1",
            (service_id,),
            show_columns=True
        )

        if not service_check or service_check == '[]':
            logger.log(
                level=30,
                msg=f"Service ID {service_id} not found for stats request"
            )
            return json.dumps({
                "success": False,
                "message": f"Service ID {service_id} not found.",
                "results": ""
            }), 404

        # Get duration statistics
        stats = job_runs.get_duration_statistics(service_id)

        logger.log(
            level=10,
            msg=f"Duration stats for service {service_id}: "
                f"count={stats.run_count}"
        )

        return json.dumps({
            "success": True,
            "message": "",
            "results": stats.to_dict()
        }), 200

    def _record_job_signal(service_id, status):
        """
        Internal helper to record a job signal (start/complete/fail).

        Args:
            service_id: The service ID to record the signal for
            status: The HeartbeatStatus value (STARTED, COMPLETED, FAILED)

        Returns:
            JSON response tuple (body, status_code)
        """
        # Verify service exists and is active
        service_check = db.query_db(
            "SELECT service_id, heartbeat_name, active FROM services "
            "WHERE service_id = %s LIMIT 1",
            (service_id,),
            show_columns=True
        )

        if not service_check or service_check == '[]':
            logger.log(
                level=30,
                msg=f"Service ID {service_id} not found for job signal"
            )
            return json.dumps({
                "success": False,
                "message": f"Service ID {service_id} not found.",
                "results": ""
            }), 404

        service_data = json.loads(service_check)
        if not service_data:
            return json.dumps({
                "success": False,
                "message": f"Service ID {service_id} not found.",
                "results": ""
            }), 404

        service = service_data[0]
        heartbeat_name = service['heartbeat_name']
        active = service['active']

        if int(active) == 0:
            logger.log(
                level=30,
                msg=f"Service {heartbeat_name} (ID: {service_id}) is inactive"
            )
            return json.dumps({
                "success": False,
                "message": f"Service {heartbeat_name} is inactive.",
                "results": ""
            }), 400

        # Parse optional run_id from request body
        run_id = None
        if request.data:
            try:
                jData = json.loads(request.data)
                run_id = jData.get('run_id')
            except (json.JSONDecodeError, ValueError):
                pass  # run_id is optional, ignore parse errors

        # Create and save heartbeat
        my_heartbeat = hbeat.Heartbeat(
            service_id,
            heartbeat_name,
            status,
            run_id=run_id
        )
        res = hbeat.addHeartbeat(my_heartbeat)

        if res:
            # Track job run for duration statistics if run_id is provided
            job_run_result = None
            duration_alert = None
            if run_id:
                if status == hbeat.HeartbeatStatus.STARTED.value:
                    job_run_result = job_runs.record_job_start(
                        service_id, run_id
                    )
                elif status in (
                    hbeat.HeartbeatStatus.COMPLETED.value,
                    hbeat.HeartbeatStatus.FAILED.value
                ):
                    job_run_result = job_runs.record_job_completion(
                        service_id, run_id, status
                    )
                    # Check duration threshold for completed jobs
                    if job_run_result:
                        duration_alert = job_runs.check_duration_threshold(
                            job_run_result
                        )
                        if duration_alert:
                            # Record metric for duration exceeded
                            metrics.record_duration_alert("exceeded")

            logger.log(
                level=10,
                msg=f"Job signal {status} recorded for {heartbeat_name}"
                    f" (run_id: {run_id})"
            )

            # Build response with optional duration info
            results = {
                "service_id": service_id,
                "heartbeat_name": heartbeat_name,
                "status": status,
                "run_id": run_id
            }
            if job_run_result and job_run_result.duration_ms is not None:
                results["duration_ms"] = job_run_result.duration_ms
            if duration_alert:
                results["duration_alert"] = {
                    "alert_type": duration_alert.alert_type,
                    "max_duration_ms": duration_alert.max_duration_ms,
                    "exceeded_by_ms": (
                        (duration_alert.duration_ms or 0) -
                        duration_alert.max_duration_ms
                    )
                }

            return json.dumps({
                "success": True,
                "message": f"Job signal {status} recorded successfully.",
                "results": results
            }), 201
        else:
            logger.log(
                level=40,
                msg=f"Failed to record job signal {status} for {heartbeat_name}"
            )
            return json.dumps({
                "success": False,
                "message": f"Failed to record job signal {status}.",
                "results": ""
            }), 500

    # =========================================================================
    # Audit Log Query API
    # =========================================================================

    @app.route('/v2/audit-logs', methods=['GET'])
    def audit_logs():
        """
        Query and export audit logs with flexible filtering.

        Query parameters:
            execution_id: Filter by execution ID
            service_id: Filter by service ID
            action_type: Filter by action type (e.g., execution_started,
                         step_completed, approved)
            actor: Filter by actor (user who performed action)
            start_date: Filter logs on or after this date (ISO format)
            end_date: Filter logs on or before this date (ISO format)
            limit: Maximum entries to return (default 50, max 250)
            offset: Number of entries to skip for pagination

        Headers:
            Accept: application/json (default) or text/csv for CSV export

        Returns:
            JSON with entries, pagination info, or CSV data
        """
        from Medic.Core.audit_log import (
            AuditActionType,
            audit_logs_to_csv,
            query_audit_logs,
        )

        # Parse query parameters
        execution_id = request.args.get('execution_id', type=int)
        service_id = request.args.get('service_id', type=int)
        action_type = request.args.get('action_type')
        actor = request.args.get('actor')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)

        # Validate action_type if provided
        if action_type and not AuditActionType.is_valid(action_type):
            valid_types = [t.value for t in AuditActionType]
            return json.dumps({
                "success": False,
                "message": f"Invalid action_type. Must be one of: "
                           f"{', '.join(valid_types)}",
                "results": ""
            }), 400

        # Parse date parameters
        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.fromisoformat(
                    start_date_str.replace('Z', '+00:00')
                )
            except ValueError:
                return json.dumps({
                    "success": False,
                    "message": "Invalid start_date format. Use ISO format "
                               "(e.g., 2026-01-01T00:00:00Z)",
                    "results": ""
                }), 400

        if end_date_str:
            try:
                end_date = datetime.fromisoformat(
                    end_date_str.replace('Z', '+00:00')
                )
            except ValueError:
                return json.dumps({
                    "success": False,
                    "message": "Invalid end_date format. Use ISO format "
                               "(e.g., 2026-01-31T23:59:59Z)",
                    "results": ""
                }), 400

        # Query audit logs
        result = query_audit_logs(
            execution_id=execution_id,
            service_id=service_id,
            action_type=action_type,
            actor=actor,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

        logger.log(
            level=10,
            msg=f"Audit log query: count={len(result.entries)}, "
                f"total={result.total_count}"
        )

        # Check Accept header for export format
        accept_header = request.headers.get('Accept', 'application/json')

        if 'text/csv' in accept_header:
            # Return CSV format
            csv_content = audit_logs_to_csv(result.entries)
            return Response(
                csv_content,
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; '
                                           'filename=audit_logs.csv',
                    'X-Total-Count': str(result.total_count),
                    'X-Limit': str(result.limit),
                    'X-Offset': str(result.offset),
                    'X-Has-More': str(result.has_more).lower(),
                }
            )

        # Return JSON format (default)
        return json.dumps({
            "success": True,
            "message": "",
            "results": result.to_dict()
        }), 200

    # =========================================================================
    # Playbook Execution API
    # =========================================================================

    @app.route('/v2/playbooks/<int:playbook_id>/execute', methods=['POST'])
    def execute_playbook(playbook_id):
        """
        Trigger a playbook execution via API.

        Request body (JSON):
            service_id: Optional service ID for the execution context
            variables: Optional dictionary of variables to pass to playbook

        Returns:
            JSON with execution_id and status on success

        Rate limited to 10 requests per minute per API key.
        """
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            get_playbook_by_id,
            start_playbook_execution,
        )
        from Medic.Core.rate_limiter import RateLimitConfig
        from Medic.Core.rate_limit_middleware import verify_rate_limit

        # Apply rate limiting: 10 req/min for playbook executions
        playbook_rate_config = RateLimitConfig(
            heartbeat_limit=100,  # Not used for this endpoint
            management_limit=10,  # 10 req/min for playbook executions
            window_seconds=60,
        )
        rate_limit_response = verify_rate_limit(
            endpoint_type="management",
            config=playbook_rate_config,
        )
        if rate_limit_response is not None:
            body, status, headers = rate_limit_response
            return body, status, headers

        # Verify playbook exists
        playbook = get_playbook_by_id(playbook_id)
        if not playbook:
            logger.log(
                level=30,
                msg=f"Playbook ID {playbook_id} not found for API execution"
            )
            return json.dumps({
                "success": False,
                "message": f"Playbook ID {playbook_id} not found.",
                "results": ""
            }), 404

        # Parse request body
        service_id = None
        variables = {}

        if request.data:
            try:
                jData = json.loads(request.data)
                service_id = jData.get('service_id')
                variables = jData.get('variables', {})

                # Validate service_id if provided
                if service_id is not None:
                    if not isinstance(service_id, int):
                        try:
                            service_id = int(service_id)
                        except (ValueError, TypeError):
                            return json.dumps({
                                "success": False,
                                "message": "service_id must be an integer.",
                                "results": ""
                            }), 400

                    # Verify service exists if provided
                    service_check = db.query_db(
                        "SELECT service_id, heartbeat_name FROM services "
                        "WHERE service_id = %s LIMIT 1",
                        (service_id,),
                        show_columns=True
                    )
                    if not service_check or service_check == '[]':
                        return json.dumps({
                            "success": False,
                            "message": f"Service ID {service_id} not found.",
                            "results": ""
                        }), 404

                # Validate variables is a dictionary
                if variables and not isinstance(variables, dict):
                    return json.dumps({
                        "success": False,
                        "message": "variables must be a dictionary.",
                        "results": ""
                    }), 400

            except (json.JSONDecodeError, ValueError) as e:
                logger.log(
                    level=30,
                    msg=f"Invalid JSON in playbook execute request: {e}"
                )
                return json.dumps({
                    "success": False,
                    "message": "Invalid JSON in request body.",
                    "results": ""
                }), 400

        # Build execution context from variables
        context = dict(variables) if variables else {}
        context['trigger'] = 'api'

        # Start playbook execution
        # Note: skip_approval=False so approval settings in playbook are respected
        execution = start_playbook_execution(
            playbook_id=playbook_id,
            service_id=service_id,
            context=context,
            skip_approval=False,
        )

        if not execution:
            logger.log(
                level=40,
                msg=f"Failed to start playbook execution for playbook "
                    f"{playbook_id}"
            )
            return json.dumps({
                "success": False,
                "message": "Failed to start playbook execution.",
                "results": ""
            }), 500

        logger.log(
            level=20,
            msg=f"Started playbook execution {execution.execution_id} for "
                f"playbook '{playbook.name}' via API"
        )

        # Build response
        response_data = {
            "execution_id": execution.execution_id,
            "playbook_id": playbook_id,
            "playbook_name": playbook.name,
            "status": execution.status.value,
            "service_id": service_id,
        }

        # Include approval info if pending
        if execution.status == ExecutionStatus.PENDING_APPROVAL:
            response_data["message"] = (
                "Playbook requires approval before execution. "
                "Approve via Slack or API."
            )

        return json.dumps({
            "success": True,
            "message": "Playbook execution started successfully.",
            "results": response_data
        }), 201

    # =========================================================================
    # Slack Interaction Webhook Endpoint
    # =========================================================================

    # =========================================================================
    # Webhook Playbook Trigger Endpoint
    # =========================================================================

    @app.route('/v2/webhooks/playbooks/<int:playbook_id>/trigger', methods=['POST'])
    def webhook_trigger_playbook(playbook_id):
        """
        Trigger a playbook execution via webhook from external systems.

        Authentication is via webhook secret in X-Webhook-Secret header.
        The secret must match the MEDIC_WEBHOOK_SECRET environment variable.

        Request body (JSON):
            service_id: Optional service ID for the execution context
            variables: Optional dictionary of variables to pass to playbook

        Returns:
            JSON with execution_id and status on success

        Rate limited to 10 requests per minute per source IP.
        """
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            get_playbook_by_id,
            start_playbook_execution,
        )
        from Medic.Core.rate_limiter import RateLimitConfig
        from Medic.Core.rate_limit_middleware import verify_rate_limit

        # =====================================================================
        # Authenticate via webhook secret
        # =====================================================================
        webhook_secret = os.environ.get("MEDIC_WEBHOOK_SECRET")
        if not webhook_secret:
            logger.log(
                level=40,
                msg="MEDIC_WEBHOOK_SECRET not configured for webhook endpoint"
            )
            return json.dumps({
                "success": False,
                "message": "Webhook endpoint not configured",
                "results": ""
            }), 503

        # Get secret from header
        provided_secret = request.headers.get("X-Webhook-Secret")
        if not provided_secret:
            logger.log(
                level=30,
                msg="Webhook trigger request missing X-Webhook-Secret header"
            )
            return json.dumps({
                "success": False,
                "message": "Missing X-Webhook-Secret header",
                "results": ""
            }), 401

        # Use constant-time comparison to prevent timing attacks
        import hmac
        if not hmac.compare_digest(webhook_secret, provided_secret):
            logger.log(
                level=30,
                msg="Webhook trigger request with invalid secret"
            )
            return json.dumps({
                "success": False,
                "message": "Invalid webhook secret",
                "results": ""
            }), 401

        # =====================================================================
        # Apply rate limiting: 10 req/min per IP for webhooks
        # =====================================================================
        webhook_rate_config = RateLimitConfig(
            heartbeat_limit=100,  # Not used for this endpoint
            management_limit=10,  # 10 req/min for webhook triggers
            window_seconds=60,
        )

        # Use IP-based rate limiting for webhooks since no API key
        remote_ip = request.remote_addr or "unknown"
        rate_key = f"webhook:{remote_ip}"

        rate_limit_response = verify_rate_limit(
            endpoint_type="management",
            config=webhook_rate_config,
            key_override=rate_key,
        )
        if rate_limit_response is not None:
            body, status, headers = rate_limit_response
            return body, status, headers

        # =====================================================================
        # Verify playbook exists
        # =====================================================================
        playbook = get_playbook_by_id(playbook_id)
        if not playbook:
            logger.log(
                level=30,
                msg=f"Playbook ID {playbook_id} not found for webhook trigger"
            )
            return json.dumps({
                "success": False,
                "message": f"Playbook ID {playbook_id} not found.",
                "results": ""
            }), 404

        # =====================================================================
        # Parse request body
        # =====================================================================
        service_id = None
        variables = {}

        if request.data:
            try:
                jData = json.loads(request.data)
                service_id = jData.get('service_id')
                variables = jData.get('variables', {})

                # Validate service_id if provided
                if service_id is not None:
                    if not isinstance(service_id, int):
                        try:
                            service_id = int(service_id)
                        except (ValueError, TypeError):
                            return json.dumps({
                                "success": False,
                                "message": "service_id must be an integer.",
                                "results": ""
                            }), 400

                    # Verify service exists if provided
                    service_check = db.query_db(
                        "SELECT service_id, heartbeat_name FROM services "
                        "WHERE service_id = %s LIMIT 1",
                        (service_id,),
                        show_columns=True
                    )
                    if not service_check or service_check == '[]':
                        return json.dumps({
                            "success": False,
                            "message": f"Service ID {service_id} not found.",
                            "results": ""
                        }), 404

                # Validate variables is a dictionary
                if variables and not isinstance(variables, dict):
                    return json.dumps({
                        "success": False,
                        "message": "variables must be a dictionary.",
                        "results": ""
                    }), 400

            except (json.JSONDecodeError, ValueError) as e:
                logger.log(
                    level=30,
                    msg=f"Invalid JSON in webhook trigger request: {e}"
                )
                return json.dumps({
                    "success": False,
                    "message": "Invalid JSON in request body.",
                    "results": ""
                }), 400

        # =====================================================================
        # Build execution context and start playbook
        # =====================================================================
        context = dict(variables) if variables else {}
        context['trigger'] = 'webhook'
        context['source_ip'] = remote_ip

        # Note: skip_approval=False so approval settings are respected
        execution = start_playbook_execution(
            playbook_id=playbook_id,
            service_id=service_id,
            context=context,
            skip_approval=False,
        )

        if not execution:
            logger.log(
                level=40,
                msg=f"Failed to start playbook execution via webhook for "
                    f"playbook {playbook_id}"
            )
            return json.dumps({
                "success": False,
                "message": "Failed to start playbook execution.",
                "results": ""
            }), 500

        logger.log(
            level=20,
            msg=f"Started playbook execution {execution.execution_id} for "
                f"playbook '{playbook.name}' via webhook from {remote_ip}"
        )

        # Build response
        response_data = {
            "execution_id": execution.execution_id,
            "playbook_id": playbook_id,
            "playbook_name": playbook.name,
            "status": execution.status.value,
            "service_id": service_id,
        }

        # Include approval info if pending
        if execution.status == ExecutionStatus.PENDING_APPROVAL:
            response_data["message"] = (
                "Playbook requires approval before execution. "
                "Approve via Slack or API."
            )

        return json.dumps({
            "success": True,
            "message": "Playbook execution started successfully.",
            "results": response_data
        }), 201

    @app.route('/v2/slack/interactions', methods=['POST'])
    def slack_interactions():
        """
        Handle Slack interactive component callbacks.

        This endpoint receives webhook callbacks when users click interactive
        buttons in Slack messages, such as the approve/reject buttons for
        playbook executions.

        The payload comes as form-urlencoded data with a 'payload' field
        containing JSON.

        Slack signature verification is performed if SLACK_SIGNING_SECRET is
        configured.
        """
        # Import here to avoid circular imports
        from Medic.Core.slack_approval import (
            get_slack_signing_secret,
            handle_slack_interaction,
            verify_slack_signature,
        )

        # Get raw body for signature verification
        raw_body = request.get_data(as_text=True)

        # Verify Slack signature if signing secret is configured
        signing_secret = get_slack_signing_secret()
        if signing_secret:
            timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
            signature = request.headers.get('X-Slack-Signature', '')

            if not verify_slack_signature(
                signing_secret, timestamp, raw_body, signature
            ):
                logger.log(
                    level=30,
                    msg="Slack signature verification failed"
                )
                return json.dumps({
                    "success": False,
                    "message": "Invalid signature"
                }), 401

        # Parse the payload
        try:
            # Slack sends the payload as form-urlencoded with a 'payload' field
            payload_str = request.form.get('payload')
            if not payload_str:
                logger.log(
                    level=30,
                    msg="No payload in Slack interaction request"
                )
                return json.dumps({
                    "success": False,
                    "message": "Missing payload"
                }), 400

            payload = json.loads(payload_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.log(
                level=30,
                msg=f"Failed to parse Slack interaction payload: {e}"
            )
            return json.dumps({
                "success": False,
                "message": "Invalid payload format"
            }), 400

        # Handle the interaction
        result = handle_slack_interaction(payload)

        if result.success:
            # Slack expects an empty 200 response for successful actions
            # when we update the message ourselves
            return '', 200
        else:
            logger.log(
                level=30,
                msg=f"Slack interaction handling failed: {result.message}"
            )
            # Return error message that will be shown to user
            return json.dumps({
                "response_type": "ephemeral",
                "text": f"Error: {result.message}"
            }), 200  # Slack expects 200 even for errors


def validateRequestData(schema, jData):
    """Validate request data against a schema."""
    try:
        v = Validator(schema)
        result = v.validate(jData)
    except Exception as e:
        logger.log(level=40, msg=f"Validation Error: {str(e)}")
        return False
    return result

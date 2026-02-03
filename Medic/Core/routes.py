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


def validateRequestData(schema, jData):
    """Validate request data against a schema."""
    try:
        v = Validator(schema)
        result = v.validate(jData)
    except Exception as e:
        logger.log(level=40, msg=f"Validation Error: {str(e)}")
        return False
    return result

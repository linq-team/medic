import os
from datetime import datetime
import pytz
import threading
import time
import logging
import psycopg2
import slack_client as slack
import pagerduty_client as pagerduty

# Log Setup
logging.basicConfig(level=logging.WARNING, format='%(relativeCreated)6d %(threadName)s %(message)s')
logger = logging.getLogger(__name__)


def connect_db():
    user = os.environ["PG_USER"]
    password = os.environ["PG_PASS"]
    dbname = os.environ["DB_NAME"]
    dbhost = os.environ["DB_HOST"]
    try:
        conn = psycopg2.connect(user=user, password=password, host=dbhost, port="5432", database=dbname)
        logger.log(level=20, msg="Connected to " + dbhost + ":5432\\" + dbname + " with user: " + user + " successfully.")
        return conn
    except psycopg2.Error as e:
        logger.log(level=50, msg="Failed to connect to " + dbname + " with supplied credentials. Is it running and do you have access? Error: " + str(e))
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
        logger.log(level=30, msg="Unable to perform query. An Error has occurred: " + str(e))
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
    # Setup main timezone
    tz = pytz.timezone('America/Chicago')

    # Setup the main loop for active services to check
    res = query_db(
        "SELECT * FROM services WHERE active = 1 AND service_name <> %s",
        ('fakeservice',),
        show_columns=True
    )
    if res is None or res == []:
        logger.log(level=20, msg="No Services configured for heartbeats.")
        return

    for heartbeat in res:
        s_id = heartbeat['service_id']
        name = heartbeat['heartbeat_name']
        s_name = heartbeat['service_name']
        interval = heartbeat['alert_interval']
        threshold = heartbeat['threshold']
        team = heartbeat['team']
        priority = heartbeat['priority']
        muted = heartbeat['muted']
        down = heartbeat['down']
        runbook = heartbeat.get('runbook')
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
                message = ':elmofire: `' + str(name) + '` has been registered in medic but has not yet ' \
                          'sent a heartbeat. This message will repeat until muted. :elmofire:'
                slack.send_message(message)
        else:
            last_hbeat_count = last_hbeat[0][1] if last_hbeat[0][1] is not None else 0
            lh_cvtd = (last_hbeat[0][0]).astimezone(tz).strftime(fmt)

            if int(last_hbeat_count) < int(threshold):
                sendAlert(s_id, s_name, name, lh_cvtd, interval, team, priority, muted, now_cdt, runbook)
            elif int(last_hbeat_count) >= int(threshold) and down == 1:
                logger.log(level=20, msg="Heartbeat: " + str(name) + " is current.")
                closeAlert(name, s_name, s_id, lh_cvtd, team, muted, now_cdt)
            else:
                logger.log(level=20, msg="Heartbeat: " + str(name) + " is current.")


def sendAlert(service_id, service_name, heartbeat_name, last_seen, interval, team, priority, muted, current_time, runbook=None):
    # Convert interval to seconds from minutes
    interval_seconds = int(interval) * 60

    # Check for active alert
    result = query_db(
        "SELECT * FROM alerts WHERE active = 1 AND service_id = %s ORDER BY alert_id DESC LIMIT 1",
        (service_id,),
        show_columns=False
    )

    # Mark service down in DB
    insert_db("UPDATE services SET down = 1 WHERE service_id = %s", (service_id,))

    alert_message = 'Medic - Heartbeat failure for ' + str(heartbeat_name)

    if result is None or result == []:
        # No active alert is present - create one
        insert_db(
            "INSERT INTO alerts(alert_name, service_id, active, alert_cycle, created_date) VALUES(%s, %s, 1, 1, %s)",
            (alert_message, service_id, current_time)
        )

        if muted == 1:
            logger.log(level=20, msg=str(heartbeat_name) + " is muted. No alert will be sent.")
        else:
            # Send PagerDuty alert
            pd_key = pagerduty.create_alert(
                alert_message=alert_message,
                service_name=service_name,
                heartbeat_name=heartbeat_name,
                team=team,
                priority=priority,
                runbook=runbook
            )

            # Update the alert with the PagerDuty dedup key
            if pd_key:
                insert_db(
                    "UPDATE alerts SET external_reference_id = %s WHERE service_id = %s AND active = 1",
                    (pd_key, service_id)
                )

            # Send slack message
            message = ':broken_heart: No heartbeat has been detected for `' + str(heartbeat_name) + '` for service `' + str(service_name) + '` since ' + str(last_seen) + '. Alert is being routed to `' + str(team) + '`'
            slack.send_message(message)
    else:
        # Active alert exists
        alert_cycle = int(result[0][5])
        count = alert_cycle + 1

        # Update alert_cycle counter in db
        insert_db("UPDATE alerts SET alert_cycle = %s WHERE alert_id = %s", (count, result[0][0]))

        if muted == 1:
            logger.log(level=20, msg="Alert already active for " + str(heartbeat_name) + ", but muted. Checking Expiration...")
            if alert_cycle % (1440 / 15) == 0:
                # 24 Hours have passed. Auto-unmute alert.
                insert_db("UPDATE services SET muted = 0, date_muted = NULL WHERE service_id = %s", (service_id,))
        else:
            # Calculate notification interval
            if alert_cycle % (interval_seconds / 15) == 0:
                message = ':broken_heart: No heartbeat has been detected for `' + str(heartbeat_name) + '` for service `' + str(service_name) + '` since ' + str(last_seen) + '. Alert has been routed to `' + str(team) + '`'
                slack.send_message(message)


def closeAlert(heartbeat_name, service_name, service_id, last_seen, team, muted, current_time):
    # Find the active alert
    ar = query_db(
        "SELECT * FROM alerts WHERE active = 1 AND service_id = %s ORDER BY alert_id DESC LIMIT 1",
        (service_id,),
        show_columns=False
    )

    if ar is None or ar == []:
        logger.log(level=20, msg="No active alert to close for " + str(heartbeat_name))
        return

    # Close the alert in the DB
    insert_db("UPDATE services SET down = 0, muted = 0 WHERE service_id = %s", (service_id,))
    insert_db("UPDATE alerts SET active = 0, closed_date = %s WHERE alert_id = %s", (current_time, ar[0][0]))

    if muted == 1:
        logger.log(level=20, msg=str(heartbeat_name) + " is muted. No alert will be sent.")
    else:
        message = ':green_heart: Heartbeat has recovered for `' + str(heartbeat_name) + '` belonging to service `' + str(service_name) + '` as of ' + str(last_seen)
        slack.send_message(message)

    # Close PagerDuty alert if one exists
    pd_key = ar[0][4]
    if pd_key and pd_key != '' and pd_key != 'NULL':
        pagerduty.close_alert(pd_key)
    else:
        logger.log(level=20, msg="No PagerDuty alert to close for alert: " + str(ar[0]))


def color_code(severity):
    if severity == 'p1':
        return "#F35A00"
    elif severity == 'p2':
        return "#e9a820"
    elif severity == "p3":
        return "#e9a820"
    else:
        return "#F35A00"


def thread_function():
    t = threading.Thread(target=queryForNoHeartbeat)
    logger.log(level=20, msg="Thread starting.")
    t.start()


if __name__ == "__main__":
    while True:
        thread_function()
        time.sleep(15)

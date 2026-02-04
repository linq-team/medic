<p align="center">
  <img src="docs/assets/medic-icon-all-green.png" alt="Medic Logo" width="200">
</p>

# Medic
Help is just a heartbeat away

# Table of Contents

* [Maintainers](#Maintainers)
* [Overview](#Overview)
  * [Architecture](#architecture)
  * [Dependencies](#dependencies)
  * [Terminology](#terminology)
* [Deployment and Configuration](#deployment-and-configuration)
  * [Environmental Variables](#environmental-variables)
  * [Metrics and Telemetry](#metrics-and-telemetry)
  * [Logging](#logging)
  * [Analytics](#analytics)
  * [Versioning](#versioning)
  * [CI/CD](#cicd)
* [Developer Details](#developer-details)
  * [Installation](#installation)
  * [Integration](#integration)
  * [File Linting](#file-linting)
  * [Git, Pull Requests and Reviews Process](#git-pull-requests-and-reviews-process)
  * [Testing](#testing)
  * [Resources](#resources)
  * [Environments](#environments)
  * [Unit Testing](#unit-testing)
</details>

<br>

# Maintainers
- Corey Jones ([@coreyjones](https://github.com/coreyjones))

# Overview
Medic is a heartbeat monitoring service consisting of 3 main objects: the server, the client and the worker. The server's responsibility is to be available and accept incoming API requests for storing or retrieving heartbeat data. The client's job is to be included in a service and post a heartbeat at a defined interval >= 1 min. The job of the worker is to query the API to look for alertable data and then to notify the appropriate channels. When combined the system provides a full-service system of heartbeat management.

## Architecture
Medic is comprised of a Webserver container, built via python3 Flask, and a worker container running python3 code. The Webserver accepts incoming requests and logs those to a postgres DB running in the platform account named `medic`. The worker queries this DB and looks for heartbeats that are missing in which it can alert on.

<a href="https://drive.google.com/file/d/1tMVzoTiqBftWjdU0Qu44P2zSjNcpLumM/view?usp=sharing">Architecture</a>

Full Interactive API documentation is available via swagger at your deployed Medic instance (e.g., `https://your-medic-host/docs`).

## Dependencies
- Install Python Dependencies: `pip3 install -r requirements.txt`
- POSTGRES DB

## Terminology


# Deployment and Configuration
Postgres tables required:
`alerts`
```
CREATE TABLE medic.alerts
(
    alert_id SERIAL,
    alert_name text COLLATE pg_catalog."default",
    service_id integer NOT NULL,
    active integer NOT NULL DEFAULT 1,
    external_reference_id text COLLATE pg_catalog."default",
    alert_cycle integer NOT NULL,
    created_date timestamp with time zone,
    closed_date timestamp with time zone,
    CONSTRAINT alert_id PRIMARY KEY (alert_id)
)
WITH (
    OIDS = FALSE
);
```

`heartbeatEvents`
```
CREATE TABLE medic."heartbeatEvents"
(
    heartbeat_id SERIAL,
    "time" timestamp with time zone NOT NULL,
    status text COLLATE pg_catalog."default" NOT NULL,
    service_id integer NOT NULL,
    CONSTRAINT heartbeat_id PRIMARY KEY (heartbeat_id)
)
WITH (
    OIDS = FALSE
);
```

`services`
```
CREATE TABLE medic.services
(
    service_id SERIAL,
    heartbeat_name text COLLATE pg_catalog."default" NOT NULL,
    active integer NOT NULL,
    alert_interval integer NOT NULL,
    team text COLLATE pg_catalog."default" NOT NULL DEFAULT 'site-reliabilty'::text,
    priority text COLLATE pg_catalog."default" NOT NULL DEFAULT 'p3'::text,
    muted integer NOT NULL DEFAULT 0,
    down integer NOT NULL DEFAULT 0,
    threshold integer NOT NULL DEFAULT 1,
    service_name text COLLATE pg_catalog."default",
    runbook text COLLATE pg_catalog."default",
    date_added timestamp with time zone,
    date_modified timestamp with time zone,
    date_muted timestamp with time zone,
    CONSTRAINT service_id PRIMARY KEY (service_id),
    CONSTRAINT heartbeat_name UNIQUE (heartbeat_name)

)
WITH (
    OIDS = FALSE
);
```

`api_keys`
```
CREATE TABLE medic.api_keys
(
    api_key_id SERIAL,
    name text COLLATE pg_catalog."default" NOT NULL,
    key_hash text COLLATE pg_catalog."default" NOT NULL,
    scopes text[] NOT NULL DEFAULT ARRAY['read']::text[],
    expires_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL DEFAULT NOW(),
    updated_at timestamp with time zone NOT NULL DEFAULT NOW(),
    CONSTRAINT api_key_id PRIMARY KEY (api_key_id),
    CONSTRAINT api_keys_name_unique UNIQUE (name),
    CONSTRAINT api_keys_scopes_check CHECK (
        scopes <@ ARRAY['read', 'write', 'admin']::text[]
    )
)
WITH (
    OIDS = FALSE
);

CREATE INDEX idx_api_keys_key_hash ON medic.api_keys(key_hash);
```

## Running Locally

### Quick Start

```bash
# 1. Clone and navigate to the repo
git clone https://github.com/linq-team/medic.git
cd medic

# 2. Copy the example environment file
cp .env.example .env

# 3. Generate required secrets (paste output into .env)
python -c "import secrets; import base64; print('MEDIC_SECRETS_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())"
python -c "import secrets; print('MEDIC_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"

# 4. Start all services
docker-compose up -d

# 5. View logs (optional)
docker-compose logs -f
```

### Accessing Services

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8080 | REST API |
| API Docs | http://localhost:8080/docs | Swagger UI |
| UI | http://localhost:80 | React dashboard |

### Stopping Services

```bash
docker-compose down          # Stop containers
docker-compose down -v       # Stop and remove volumes (resets database)
```

### Optional Integrations

For Slack notifications, see [docs/SLACK_INTEGRATION.md](docs/SLACK_INTEGRATION.md)

For PagerDuty alerts, see [docs/PAGERDUTY_INTEGRATION.md](docs/PAGERDUTY_INTEGRATION.md)

## Environmental Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `PG_USER` | PostgreSQL username | `medic` |
| `PG_PASS` | PostgreSQL password | `your-secure-password` |
| `DB_NAME` | Database name | `medic` |
| `DB_HOST` | Database host | `localhost` or `postgres` (in Docker) |
| `MEDIC_SECRETS_KEY` | 32-byte base64 key for encryption | Generate with Python (see Quick Start) |

### Optional - Application

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | API server port | `8080` |
| `MEDIC_BASE_URL` | Base URL for API | `http://localhost:8080` |
| `MEDIC_TIMEZONE` | Timezone for schedules | `America/Chicago` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DEBUG` | Enable debug mode | `false` |

### Optional - Integrations

| Variable | Description | How to Get |
|----------|-------------|------------|
| `SLACK_API_TOKEN` | Slack bot token | [Slack Integration Guide](docs/SLACK_INTEGRATION.md) |
| `SLACK_CHANNEL_ID` | Slack channel ID | [Slack Integration Guide](docs/SLACK_INTEGRATION.md) |
| `SLACK_SIGNING_SECRET` | Slack signing secret | [Slack Integration Guide](docs/SLACK_INTEGRATION.md) |
| `PAGERDUTY_ROUTING_KEY` | PagerDuty Events API key | [PagerDuty Integration Guide](docs/PAGERDUTY_INTEGRATION.md) |

See `.env.example` for a complete list of all configuration options.

## Metrics and Telemetry
- Graphs provided by Cartographer

## Logging
- Logging is enabled at the Warning level, via python's logging module. You can increase or decrease verbosity by edting the level in `Medic/Helpers/logSettings.py`. The current logs are posted to Scalyr

## Analytics


## Versioning
Production : origin/master branch

Staging: origin/development

## CI/CD
Tests TBD

# Developer Details

## Installation 
Everything is contained within Docker, except for the postgres db. If you are testing locally you'll need to also pull a local postgres docker image and create the DB with tables needed.

## Integration
In order to get started with Medic, you will first need to register your heartbeat with the system. Once registered, you may begin sending your heartbeats. You can register multiple heartbeats to a single service, but each heartbeat name must be unique. Tying your heartbeat to your service name allows for easy lookups in the system, but does not provide any functional difference within Medic. Think of it more as a tag in which you can use to locate heartbeats with.

You can find available client packages and sample code for integrating Medic to your service [here](https://github.com/linq-team/medic/tree/main/Medic/clients)

## File Linting

## Git, Pull Requests and Reviews Process
Preferred: create a branch off of development and commit changes, then create a PR to merge into master. Once the changes are vetted in staging, merge development into the master branch to push to production. Branch protection is enabled on the development and master branches.

## Testing
TBD

## Resources

There is also a cron job configured through infraspec that runs every day at 12:00AM to delete heartbeats older than 30 days from the system. This is done in order to keep the db size as low as posisble.


## Environments
- Staging K8s
- Production K8s


## Unit Testing


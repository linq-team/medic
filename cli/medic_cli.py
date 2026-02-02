#!/usr/bin/env python3
"""
Medic CLI - Command-line interface for Medic heartbeat monitoring service.

Usage:
    medic-cli service list [--active] [--team=<team>]
    medic-cli service get <name>
    medic-cli service mute <name> [--duration=<duration>]
    medic-cli service unmute <name>
    medic-cli heartbeat send <name> [--status=<status>]
    medic-cli heartbeat list [--name=<name>] [--limit=<limit>]
    medic-cli alerts list [--active]
    medic-cli health

Options:
    -h --help               Show this help message
    --active                Filter for active items only
    --team=<team>          Filter by team name
    --duration=<duration>   Mute duration (e.g., "1h", "30m", "1d") [default: 24h]
    --status=<status>       Heartbeat status [default: UP]
    --name=<name>          Filter by heartbeat name
    --limit=<limit>        Maximum results to return [default: 50]
"""
import os
import sys
import json
import argparse
import requests
from typing import Optional, Dict, Any
from datetime import datetime


def get_base_url() -> str:
    """Get the Medic API base URL from environment."""
    url = os.environ.get("MEDIC_BASE_URL", "http://localhost:5000")
    return url.rstrip("/")


def api_request(
    method: str,
    endpoint: str,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Dict[str, Any]:
    """Make an API request to Medic."""
    url = f"{get_base_url()}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        return response.json()
    except requests.RequestException as e:
        return {"success": False, "message": str(e), "results": []}
    except json.JSONDecodeError:
        return {"success": False, "message": "Invalid JSON response", "results": []}


def format_table(headers: list, rows: list) -> str:
    """Format data as a table."""
    if not rows:
        return "No results found."

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Build header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * w for w in widths)

    # Build rows
    row_lines = []
    for row in rows:
        row_lines.append(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))

    return f"{header_line}\n{separator}\n" + "\n".join(row_lines)


def cmd_service_list(args: argparse.Namespace) -> int:
    """List all services."""
    params = {}
    if args.active:
        params["active"] = 1

    result = api_request("GET", "/service", params=params)

    if not result.get("success", False) and isinstance(result.get("results"), str):
        print(f"Error: {result.get('message', 'Unknown error')}")
        return 1

    services = result.get("results", [])
    if isinstance(services, str):
        services = json.loads(services)

    if args.team:
        services = [s for s in services if s.get("team") == args.team]

    headers = ["Name", "Service", "Active", "Interval", "Team", "Priority", "Muted", "Down"]
    rows = []
    for s in services:
        rows.append([
            s.get("heartbeat_name", ""),
            s.get("service_name", ""),
            "Yes" if s.get("active") == 1 else "No",
            f"{s.get('alert_interval', 0)}m",
            s.get("team", ""),
            s.get("priority", ""),
            "Yes" if s.get("muted") == 1 else "No",
            "Yes" if s.get("down") == 1 else "No",
        ])

    print(format_table(headers, rows))
    return 0


def cmd_service_get(args: argparse.Namespace) -> int:
    """Get details for a specific service."""
    result = api_request("GET", f"/service/{args.name}")

    if not result.get("success", False):
        print(f"Error: {result.get('message', 'Service not found')}")
        return 1

    services = result.get("results", [])
    if isinstance(services, str):
        services = json.loads(services)

    if not services:
        print(f"Service '{args.name}' not found.")
        return 1

    service = services[0]
    print(f"Heartbeat Name: {service.get('heartbeat_name')}")
    print(f"Service Name:   {service.get('service_name')}")
    print(f"Active:         {'Yes' if service.get('active') == 1 else 'No'}")
    print(f"Alert Interval: {service.get('alert_interval')} minutes")
    print(f"Threshold:      {service.get('threshold')}")
    print(f"Team:           {service.get('team')}")
    print(f"Priority:       {service.get('priority')}")
    print(f"Muted:          {'Yes' if service.get('muted') == 1 else 'No'}")
    print(f"Down:           {'Yes' if service.get('down') == 1 else 'No'}")
    print(f"Runbook:        {service.get('runbook') or 'Not set'}")
    return 0


def cmd_service_mute(args: argparse.Namespace) -> int:
    """Mute a service."""
    result = api_request("POST", f"/service/{args.name}", data={"muted": 1})

    if result.get("success", False):
        print(f"Service '{args.name}' has been muted.")
        return 0
    else:
        print(f"Error: {result.get('message', 'Failed to mute service')}")
        return 1


def cmd_service_unmute(args: argparse.Namespace) -> int:
    """Unmute a service."""
    result = api_request("POST", f"/service/{args.name}", data={"muted": 0})

    if result.get("success", False):
        print(f"Service '{args.name}' has been unmuted.")
        return 0
    else:
        print(f"Error: {result.get('message', 'Failed to unmute service')}")
        return 1


def cmd_heartbeat_send(args: argparse.Namespace) -> int:
    """Send a heartbeat."""
    data = {
        "heartbeat_name": args.name,
        "status": args.status
    }
    result = api_request("POST", "/heartbeat", data=data)

    if result.get("success", False):
        print(f"Heartbeat sent successfully for '{args.name}' (status: {args.status})")
        return 0
    else:
        print(f"Error: {result.get('message', 'Failed to send heartbeat')}")
        return 1


def cmd_heartbeat_list(args: argparse.Namespace) -> int:
    """List heartbeats."""
    params = {"maxCount": args.limit}
    if args.name:
        params["heartbeat_name"] = args.name

    result = api_request("GET", "/heartbeat", params=params)

    if not result.get("success", False):
        print(f"Error: {result.get('message', 'Unknown error')}")
        return 1

    heartbeats = result.get("results", [])
    if isinstance(heartbeats, str):
        heartbeats = json.loads(heartbeats)

    headers = ["ID", "Name", "Service", "Time", "Status"]
    rows = []
    for h in heartbeats:
        rows.append([
            h.get("heartbeat_id", ""),
            h.get("heartbeat_name", ""),
            h.get("service_name", ""),
            h.get("time", ""),
            h.get("status", ""),
        ])

    print(format_table(headers, rows))
    return 0


def cmd_alerts_list(args: argparse.Namespace) -> int:
    """List alerts."""
    params = {}
    if args.active:
        params["active"] = 1

    result = api_request("GET", "/alerts", params=params)

    if not result.get("success", False):
        print(f"Error: {result.get('message', 'Unknown error')}")
        return 1

    alerts = result.get("results", [])
    if isinstance(alerts, str):
        alerts = json.loads(alerts)

    headers = ["ID", "Name", "Active", "Cycle", "Created", "Closed"]
    rows = []
    for a in alerts:
        rows.append([
            a.get("alert_id", ""),
            a.get("alert_name", "")[:50],
            "Yes" if a.get("active") == 1 else "No",
            a.get("alert_cycle", ""),
            a.get("created_date", ""),
            a.get("closed_date") or "-",
        ])

    print(format_table(headers, rows))
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Check Medic health status."""
    try:
        response = requests.get(f"{get_base_url()}/health", timeout=10)
        health_data = response.json()

        print(f"Overall Status: {health_data.get('status', 'unknown').upper()}")
        print(f"Timestamp:      {health_data.get('timestamp', 'unknown')}")
        print(f"Version:        {health_data.get('version', 'unknown')}")
        print()
        print("Components:")

        components = health_data.get("components", {})
        for name, info in components.items():
            status = info.get("status", "unknown")
            status_icon = "OK" if status in ["healthy", "configured"] else "WARN"
            print(f"  {name}: [{status_icon}] {status}")

        return 0 if health_data.get("status") == "healthy" else 1
    except requests.RequestException as e:
        print(f"Error connecting to Medic: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Medic CLI - Command-line interface for Medic heartbeat monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Service commands
    service_parser = subparsers.add_parser("service", help="Service management")
    service_subparsers = service_parser.add_subparsers(dest="subcommand")

    list_parser = service_subparsers.add_parser("list", help="List all services")
    list_parser.add_argument("--active", action="store_true", help="Show only active services")
    list_parser.add_argument("--team", help="Filter by team")

    get_parser = service_subparsers.add_parser("get", help="Get service details")
    get_parser.add_argument("name", help="Heartbeat name")

    mute_parser = service_subparsers.add_parser("mute", help="Mute a service")
    mute_parser.add_argument("name", help="Heartbeat name")
    mute_parser.add_argument("--duration", default="24h", help="Mute duration")

    unmute_parser = service_subparsers.add_parser("unmute", help="Unmute a service")
    unmute_parser.add_argument("name", help="Heartbeat name")

    # Heartbeat commands
    heartbeat_parser = subparsers.add_parser("heartbeat", help="Heartbeat operations")
    heartbeat_subparsers = heartbeat_parser.add_subparsers(dest="subcommand")

    send_parser = heartbeat_subparsers.add_parser("send", help="Send a heartbeat")
    send_parser.add_argument("name", help="Heartbeat name")
    send_parser.add_argument("--status", default="UP", help="Status (UP/DOWN/DEGRADED)")

    hb_list_parser = heartbeat_subparsers.add_parser("list", help="List heartbeats")
    hb_list_parser.add_argument("--name", help="Filter by heartbeat name")
    hb_list_parser.add_argument("--limit", type=int, default=50, help="Max results")

    # Alerts commands
    alerts_parser = subparsers.add_parser("alerts", help="Alert management")
    alerts_subparsers = alerts_parser.add_subparsers(dest="subcommand")

    alerts_list_parser = alerts_subparsers.add_parser("list", help="List alerts")
    alerts_list_parser.add_argument("--active", action="store_true", help="Show only active alerts")

    # Health command
    subparsers.add_parser("health", help="Check Medic health status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate command
    if args.command == "service":
        if args.subcommand == "list":
            return cmd_service_list(args)
        elif args.subcommand == "get":
            return cmd_service_get(args)
        elif args.subcommand == "mute":
            return cmd_service_mute(args)
        elif args.subcommand == "unmute":
            return cmd_service_unmute(args)
        else:
            service_parser.print_help()
            return 1
    elif args.command == "heartbeat":
        if args.subcommand == "send":
            return cmd_heartbeat_send(args)
        elif args.subcommand == "list":
            return cmd_heartbeat_list(args)
        else:
            heartbeat_parser.print_help()
            return 1
    elif args.command == "alerts":
        if args.subcommand == "list":
            return cmd_alerts_list(args)
        else:
            alerts_parser.print_help()
            return 1
    elif args.command == "health":
        return cmd_health(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())

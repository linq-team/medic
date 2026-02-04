"""URL validation module for SSRF prevention.

This module provides URL validation functionality to prevent Server-Side
Request Forgery (SSRF) attacks. It validates URLs before making HTTP requests
to ensure they don't target internal services, cloud metadata endpoints, or
private IP ranges.

Security features:
- Blocks private IP ranges (RFC 1918, loopback, link-local)
- Blocks cloud metadata endpoints (169.254.169.254)
- Blocks localhost and 0.0.0.0
- Only allows http/https schemes
- Performs DNS resolution to catch DNS rebinding attacks
- Supports explicit allowlist via MEDIC_ALLOWED_WEBHOOK_HOSTS

Usage:
    from Medic.Core.url_validator import validate_url, InvalidURLError

    try:
        validate_url("https://api.example.com/webhook")
    except InvalidURLError as e:
        # Handle invalid URL
        pass
"""

import ipaddress
import logging
import os
import socket
from typing import List, Optional, Set
from urllib.parse import urlparse

import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


class InvalidURLError(Exception):
    """Exception raised when a URL fails validation.

    This exception intentionally does not expose internal details
    to prevent information leakage about the internal network.
    """

    def __init__(self, message: str = "Invalid webhook URL"):
        self.message = message
        super().__init__(self.message)


# Allowed URL schemes
ALLOWED_SCHEMES: Set[str] = {"http", "https"}

# Private IP networks that should be blocked (RFC 1918 + special ranges)
BLOCKED_IP_NETWORKS: List[ipaddress.IPv4Network] = [
    ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
    ipaddress.IPv4Network("10.0.0.0/8"),  # Private Class A
    ipaddress.IPv4Network("172.16.0.0/12"),  # Private Class B
    ipaddress.IPv4Network("192.168.0.0/16"),  # Private Class C
    ipaddress.IPv4Network("169.254.0.0/16"),  # Link-local (includes cloud metadata)
    ipaddress.IPv4Network("0.0.0.0/8"),  # "This" network
]

# IPv6 blocked networks
BLOCKED_IPV6_NETWORKS: List[ipaddress.IPv6Network] = [
    ipaddress.IPv6Network("::1/128"),  # Loopback
    ipaddress.IPv6Network("fc00::/7"),  # Unique local
    ipaddress.IPv6Network("fe80::/10"),  # Link-local
    ipaddress.IPv6Network("::/128"),  # Unspecified
]

# Specific IPs that should always be blocked
BLOCKED_IPS: Set[str] = {
    "0.0.0.0",
    "127.0.0.1",
    "localhost",
    "169.254.169.254",  # AWS/GCP/Azure metadata endpoint
    "metadata.google.internal",
    "metadata",
}

# Default DNS resolution timeout in seconds
DNS_TIMEOUT: float = 5.0


def get_allowed_hosts() -> Optional[Set[str]]:
    """Get the explicit allowlist of webhook hosts from environment.

    Returns:
        Set of allowed hostnames/IPs, or None if no allowlist is configured.
        When None, all non-private hosts are allowed.
    """
    env_value = os.environ.get("MEDIC_ALLOWED_WEBHOOK_HOSTS", "").strip()
    if not env_value:
        return None

    # Parse comma-separated list of hosts
    hosts = set()
    for host in env_value.split(","):
        host = host.strip().lower()
        if host:
            hosts.add(host)

    return hosts if hosts else None


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private/blocked range.

    This function checks the IP against:
    - Private RFC 1918 ranges (10.x, 172.16-31.x, 192.168.x)
    - Loopback (127.x)
    - Link-local (169.254.x)
    - "This" network (0.x)
    - IPv6 private/local ranges

    Args:
        ip: IP address string to check

    Returns:
        True if the IP is private/blocked, False otherwise
    """
    try:
        # Handle IPv4 addresses
        try:
            ip_obj = ipaddress.IPv4Address(ip)

            # Check against blocked IPv4 networks
            for network in BLOCKED_IP_NETWORKS:
                if ip_obj in network:
                    return True

            return False

        except ipaddress.AddressValueError:
            pass

        # Handle IPv6 addresses
        try:
            ip_obj_v6 = ipaddress.IPv6Address(ip)

            # Check against blocked IPv6 networks
            for ipv6_network in BLOCKED_IPV6_NETWORKS:
                if ip_obj_v6 in ipv6_network:
                    return True

            # Also check if it's an IPv4-mapped IPv6 address
            if ip_obj_v6.ipv4_mapped:
                return is_private_ip(str(ip_obj_v6.ipv4_mapped))

            return False

        except ipaddress.AddressValueError:
            pass

        # If we can't parse it as an IP, it's not a valid IP
        return False

    except Exception:
        # If any error occurs during parsing, treat as potentially unsafe
        return True


def resolve_hostname(hostname: str, timeout: float = DNS_TIMEOUT) -> List[str]:
    """Resolve a hostname to its IP addresses.

    This is used to catch DNS rebinding attacks where a hostname
    initially resolves to a public IP but later resolves to a
    private IP.

    Args:
        hostname: The hostname to resolve
        timeout: DNS resolution timeout in seconds

    Returns:
        List of resolved IP addresses

    Raises:
        InvalidURLError: If DNS resolution fails
    """
    # Set socket timeout for DNS resolution
    original_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)

        # Try to resolve the hostname
        try:
            addr_info = socket.getaddrinfo(
                hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
            # Extract unique IP addresses from results
            ips: List[str] = list(set(str(info[4][0]) for info in addr_info))
            return ips
        except socket.gaierror as e:
            logger.log(level=30, msg=f"DNS resolution failed for {hostname}: {e}")
            raise InvalidURLError("Invalid webhook URL")
        except socket.timeout:
            logger.log(level=30, msg=f"DNS resolution timed out for {hostname}")
            raise InvalidURLError("Invalid webhook URL")

    finally:
        socket.setdefaulttimeout(original_timeout)


def validate_url(url: str, skip_dns_check: bool = False) -> bool:
    """Validate a URL for SSRF prevention.

    This function performs comprehensive URL validation:
    1. Parses and validates URL structure
    2. Checks scheme is http/https only
    3. Checks hostname is not in blocklist
    4. Resolves hostname to IPs (DNS rebinding prevention)
    5. Checks all resolved IPs are not in private ranges
    6. Optionally checks against explicit allowlist

    Args:
        url: The URL to validate
        skip_dns_check: Skip DNS resolution (for testing)

    Returns:
        True if the URL is valid and safe

    Raises:
        InvalidURLError: If the URL fails any validation check
    """
    if not url:
        logger.log(level=30, msg="URL validation failed: empty URL")
        raise InvalidURLError("Invalid webhook URL")

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception:
        logger.log(level=30, msg="URL validation failed: malformed URL")
        raise InvalidURLError("Invalid webhook URL")

    # Check scheme
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        logger.log(level=30, msg=f"URL validation failed: invalid scheme '{scheme}'")
        raise InvalidURLError("Invalid webhook URL")

    # Extract hostname
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        logger.log(level=30, msg="URL validation failed: missing hostname")
        raise InvalidURLError("Invalid webhook URL")

    # Check against explicit blocklist
    if hostname in BLOCKED_IPS:
        logger.log(
            level=30, msg=f"URL validation failed: blocked hostname '{hostname}'"
        )
        raise InvalidURLError("Invalid webhook URL")

    # Check if hostname is a direct IP address
    if is_private_ip(hostname):
        logger.log(level=30, msg=f"URL validation failed: private IP '{hostname}'")
        raise InvalidURLError("Invalid webhook URL")

    # Check against explicit allowlist if configured
    allowed_hosts = get_allowed_hosts()
    if allowed_hosts is not None:
        if hostname not in allowed_hosts:
            logger.log(
                level=30,
                msg=f"URL validation failed: host '{hostname}' not in allowlist",
            )
            raise InvalidURLError("Invalid webhook URL")
        # If in allowlist, skip further checks
        return True

    # Perform DNS resolution to catch DNS rebinding attacks
    if not skip_dns_check:
        resolved_ips = resolve_hostname(hostname)

        # Check all resolved IPs against private ranges
        for ip in resolved_ips:
            if is_private_ip(ip):
                logger.log(
                    level=30,
                    msg=f"URL validation failed: hostname '{hostname}' "
                    f"resolves to private IP '{ip}'",
                )
                raise InvalidURLError("Invalid webhook URL")

            # Also check if resolved IP is in blocklist
            if ip in BLOCKED_IPS:
                logger.log(
                    level=30,
                    msg=f"URL validation failed: hostname '{hostname}' "
                    f"resolves to blocked IP '{ip}'",
                )
                raise InvalidURLError("Invalid webhook URL")

    return True


def is_safe_url(url: str) -> bool:
    """Check if a URL is safe without raising exceptions.

    This is a convenience wrapper around validate_url that returns
    a boolean instead of raising exceptions.

    Args:
        url: The URL to check

    Returns:
        True if the URL is safe, False otherwise
    """
    try:
        return validate_url(url)
    except InvalidURLError:
        return False

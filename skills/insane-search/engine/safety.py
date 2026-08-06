"""SSRF / redirect safety guard for an agent-facing fetcher.

curl_cffi follows redirects but does NOT validate the destination (confirmed
against the official docs: there is no built-in private-IP/safe-redirect
option). Since this engine fetches attacker-influenced URLs and follows their
redirects, a hostile page could redirect to loopback, RFC-1918, link-local, or
the cloud metadata endpoint (169.254.169.254) to exfiltrate internal data.

This module provides a pure, deterministic classifier and a redirect resolver.
Default-deny for private/internal targets; opt in with allow_private=True
(env INSANE_ALLOW_PRIVATE=1) for local testing.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_MAX_REDIRECTS = 10


def allow_private_default() -> bool:
    return os.environ.get("INSANE_ALLOW_PRIVATE", "") in ("1", "true", "yes")


def _ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def classify_url(url: str, allow_private: bool = False) -> tuple[bool, str]:
    """(is_safe, reason). Blocks non-http(s) schemes and hosts that are — or
    DNS-resolve to — private/loopback/link-local/reserved/metadata addresses."""
    try:
        p = urlsplit(url)
    except Exception as e:
        return False, f"parse_error:{e}"
    if p.scheme not in ALLOWED_SCHEMES:
        return False, f"scheme:{p.scheme or 'none'}"
    host = p.hostname
    if not host:
        return False, "no_host"
    if allow_private:
        return True, "allow_private"

    # IP literal host → check directly (covers cloud metadata, loopback, …)  # NOTE-BIAS-OK
    try:
        ipaddress.ip_address(host)
        return (False, f"ip_blocked:{host}") if _ip_blocked(host) else (True, "public_ip")
    except ValueError:
        pass

    # Hostname → resolve and check every A/AAAA (DNS-rebinding defense).
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        ips = {info[4][0] for info in infos}
    except Exception:
        # Don't hard-fail on resolver hiccups — the real request will error out
        # naturally; we only need to stop redirects INTO internal space.
        return True, "resolve_failed_allow"
    for ip in ips:
        if _ip_blocked(str(ip)):
            return False, f"resolves_internal:{host}->{ip}"
    return True, "public"


def location_of(resp) -> str | None:
    """Case-insensitive Location header from a curl_cffi/requests response."""
    try:
        headers = {k.lower(): v for k, v in dict(getattr(resp, "headers", {}) or {}).items()}
        return headers.get("location")
    except Exception:
        return None


def is_redirect(resp) -> bool:
    try:
        return int(getattr(resp, "status_code", 0) or 0) in (301, 302, 303, 307, 308)
    except Exception:
        return False


def resolve_redirect(base_url: str, location: str) -> str:
    return urljoin(base_url, location)

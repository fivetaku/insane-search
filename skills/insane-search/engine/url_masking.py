"""Redact secret-bearing parts of URLs before they reach logs or stdout.

The 2026-09-03 credential sweep found zero real leaks in the engine's own
artifacts, but three sinks print request URLs verbatim: the ``--trace`` attempt
log, the observations jsonl, and the ``source_url`` header on wrapped content.
A URL that arrives carrying a token in its query string would land in all
three. Masking values while keeping parameter names leaves those records
diagnosable without recording the secret itself.

Scope is deliberately narrow (owner decision 2026-09-04): mask URLs at the
output boundary only. No general-purpose scrub utility, no changes to what the
fetch chain sends over the wire.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "REDACTED"

# Matched against the parameter name. Anchored alternatives (``^sig$``) exist
# because bare "sig"/"key"/"code" are secrets while "signature_help" or
# "keyword" or "country_code" are not.
_SENSITIVE_PARAM = re.compile(
    r"token|secret|password|passwd|credential|signature|bearer|session"
    r"|api[-_]?key|access[-_]?key|auth"
    r"|^sig$|^key$|^pwd$|^sid$|^code$|^state$|^access$|^refresh$",
    re.IGNORECASE,
)


def _mask_query(query: str) -> str:
    if not query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    masked = [
        (name, REDACTED if value and _SENSITIVE_PARAM.search(name) else value)
        for name, value in pairs
    ]
    if masked == pairs:
        # Nothing to hide. Return the original text rather than the re-encoded
        # round trip, so a query we parsed loosely (or not at all) is never
        # silently reshaped by logging.
        return query
    return urlencode(masked)


def mask_url(url: str) -> str:
    """Return ``url`` with credential-shaped values replaced by ``REDACTED``.

    Masks sensitive query-parameter values and any ``user:pass@`` userinfo.
    Host, path and non-sensitive parameters survive untouched so the result
    still identifies the request. Never raises: an unparseable URL is returned
    as-is, because logging must not change a fetch outcome.
    """
    if not url or "?" not in url and "@" not in url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url

    netloc = parts.netloc
    if "@" in netloc:
        _, _, host = netloc.rpartition("@")
        netloc = f"{REDACTED}@{host}"

    return urlunsplit(
        (parts.scheme, netloc, parts.path, _mask_query(parts.query), parts.fragment)
    )

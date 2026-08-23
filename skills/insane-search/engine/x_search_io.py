"""Credential and HTTP boundaries for X keyword discovery."""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def resolve_xai_credential() -> str | None:
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if api_key:
        return api_key
    omo = shutil.which("omo")
    if not omo:
        return None
    try:
        process = subprocess.run(
            [omo, "auth", "print-bearer-token", "--provider", "xai"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = process.stdout.strip()
    return token if process.returncode == 0 and token else None


def http_get(url: str, timeout: int) -> Any:
    from curl_cffi import requests

    return requests.get(url, impersonate="safari", timeout=timeout, allow_redirects=True)


def http_post_json(url: str, payload: dict[str, object], credential: str, timeout: int) -> Any:
    from curl_cffi import requests

    return requests.post(
        url,
        impersonate="safari",
        timeout=timeout,
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
        json=payload,
    )

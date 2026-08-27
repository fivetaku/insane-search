"""Capability-matched executor for fallback attempts.

The fetch_chain's probe/grid phase uses curl_cffi directly. When curl can't
punch through (JS challenge, real-TLS detection), this module routes to the
right browser executor based on the profile's `capabilities_needed` tags:

    needs_real_tls_stack + needs_js_exec  → playwright_real_chrome.js
    needs_js_exec only                    → Playwright MCP (if available)
    needs_mobile_context (+ real_tls)     → playwright_mobile_chrome.js

The JS templates live in `engine/templates/` and accept only generic
parameters ({{url}}, {{waitSelector}}, {{profileDir}}, {{device}}). No
site-specific logic.

Playwright MCP invocation requires caller's tool access; this module
provides the subprocess path for local JS templates but only stubs the MCP
path (MCP must be driven from the Claude session itself).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Optional

from .validators import Verdict, validate
from .waf_detector import load_profile
from .fetch_chain import Attempt


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _profile_dir_for(url: str, choice: str) -> str:
    """Per-host + per-device Chrome profile directory.

    The host is hashed (never stored as a site name) so the No-Site-Name Rule
    holds while each host keeps an isolated, reusable profile. Desktop and
    mobile get separate subdirs so emulation state never bleeds across.
    """
    import hashlib
    from urllib.parse import urlsplit
    host = (urlsplit(url).hostname or "unknown").lower()
    host_hash = hashlib.sha1(host.encode("utf-8", "ignore")).hexdigest()[:16]
    device = "mobile" if "mobile" in choice else "desktop"
    return os.path.join(tempfile.gettempdir(), ".insane_pw", host_hash, device)


def _node_available() -> bool:
    return shutil.which("node") is not None


# Node deps live OUTSIDE the plugin tree. `templates/node_modules` is gitignored,
# so a marketplace install (or any fresh clone) ships the JS templates with no
# `playwright` module — every browser fallback then died instantly with
# "Cannot find module 'playwright'". A version-independent shared dir is
# installed once and reused across plugin upgrades.
NODE_DEPS_DIR = os.path.expanduser("~/.insane-search/node")
_NODE_DEPS_CACHE: Optional[str] = None


def _has_playwright_module(root: str) -> bool:
    return os.path.isdir(os.path.join(root, "node_modules", "playwright"))


def _npm_install(dest: str) -> bool:
    """Install the template deps into `dest`. Browsers are skipped: the
    templates use channel:'chrome' (the system Chrome), never bundled Chromium."""
    if shutil.which("npm") is None:
        return False
    os.makedirs(dest, exist_ok=True)
    src_pkg = os.path.join(TEMPLATES_DIR, "package.json")
    if os.path.isfile(src_pkg):
        shutil.copyfile(src_pkg, os.path.join(dest, "package.json"))
    env = dict(os.environ)
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    env["PATCHRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    lock = os.path.join(dest, ".installing")
    try:
        # Crude single-flight guard: a concurrent fallback should not run a
        # second npm install into the same dir.
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 900:
            return _has_playwright_module(dest)
        open(lock, "w").close()
        subprocess.run(
            ["npm", "install", "--silent", "--no-audit", "--no-fund"],
            cwd=dest, env=env, capture_output=True, text=True, timeout=900, check=False,
        )
    except Exception:
        return False
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass
    return _has_playwright_module(dest)


def _resolve_node_deps() -> Optional[str]:
    """Return the dir whose node_modules holds playwright, installing it once
    if needed. None = node/npm unusable."""
    global _NODE_DEPS_CACHE
    if _NODE_DEPS_CACHE is not None:
        return _NODE_DEPS_CACHE or None
    if not _node_available():
        _NODE_DEPS_CACHE = ""
        return None
    for root in (TEMPLATES_DIR, NODE_DEPS_DIR):
        if _has_playwright_module(root):
            _NODE_DEPS_CACHE = root
            return root
    if _npm_install(NODE_DEPS_DIR):
        _NODE_DEPS_CACHE = NODE_DEPS_DIR
        return NODE_DEPS_DIR
    _NODE_DEPS_CACHE = ""
    return None


def _pick_executor(capabilities: list[str], device_class: str) -> str:
    caps = set(capabilities or [])
    if device_class == "mobile" or "needs_mobile_context" in caps:
        if "needs_real_tls_stack" in caps:
            return "playwright_mobile_chrome"
        return "playwright_mcp_mobile"
    if "needs_protocol_stealth" in caps:
        return "protocol_stealth_chrome"
    if "needs_real_tls_stack" in caps:
        return "playwright_real_chrome"
    if "needs_js_exec" in caps:
        return "playwright_mcp"
    return "playwright_real_chrome"  # safest general fallback


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _auto_install(pkg: str) -> bool:
    if os.environ.get("INSANE_AUTO_INSTALL", "").strip() not in ("1", "true", "yes"):
        return False
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"],
                       capture_output=True, timeout=180, check=False)
    except Exception:
        return False
    importlib.invalidate_caches()
    return _module_available(pkg)


def _run_python_template(template: str, args: dict, timeout: int = 90) -> tuple[int, str, str]:
    path = os.path.join(TEMPLATES_DIR, template)
    if not os.path.isfile(path):
        return 127, "", f"template not found: {path}"
    try:
        proc = subprocess.run(
            [sys.executable, path], input=json.dumps(args), cwd=TEMPLATES_DIR,
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as e:
        return 1, "", f"{type(e).__name__}:{e}"


def _run_protocol_stealth(
    att: Attempt, url: str, *, success_selectors: Optional[list[str]], timeout: int, t0: float,
) -> tuple[Attempt, str]:
    """nodriver (raw CDP, no Playwright shim) first, patchright channel=chrome next.

    For gates that fingerprint the automation protocol (Runtime.enable), every
    Playwright-shimmed driver fails regardless of patch quality; nodriver is the
    strongest free option, patchright the license-safe next. Missing drivers are
    reported so the caller continues down its fallback list.
    """
    args: dict = {"url": url, "timeout": timeout * 1000}
    if success_selectors:
        args["waitSelector"] = success_selectors[0]
    for pkg, template in (("nodriver", "nodriver_fetch.py"), ("patchright", "patchright_fetch.py")):
        if not _module_available(pkg) and not _auto_install(pkg):
            continue
        rc, stdout, stderr = _run_python_template(template, args, timeout=timeout + 30)
        att.executor = f"protocol_stealth_chrome:{pkg}"
        att.elapsed_s = round(time.time() - t0, 3)
        if rc != 0 or not stdout:
            att.error = f"{pkg}: {(stderr or 'no stdout')[:200]}"
            continue
        resp = _FakeResp(stdout)
        vr = validate(resp, success_selectors=success_selectors)
        att.status = 200
        att.body_size = len(stdout)
        att.verdict = vr.verdict.value
        att.reasons = vr.reasons
        return att, stdout
    att.elapsed_s = round(time.time() - t0, 3)
    if not att.error:
        att.error = "nodriver/patchright not installed (pip install nodriver, or INSANE_AUTO_INSTALL=1)"
    att.verdict = Verdict.UNKNOWN.value
    return att, ""


def _run_node_template(template: str, args: dict, timeout: int = 90,
                       deps_root: Optional[str] = None) -> tuple[int, str, str]:
    """Run a Node.js template with args as JSON on stdin.

    Template convention: reads `process.stdin` → JSON → runs fetch → writes
    HTML to stdout; errors go to stderr with non-zero exit code.

    `deps_root` is the dir holding node_modules; it is exported as NODE_PATH so
    the template resolves playwright/patchright even when the deps live outside
    the (gitignored, version-scoped) plugin tree.
    """
    path = os.path.join(TEMPLATES_DIR, template)
    if not os.path.isfile(path):
        return 127, "", f"template not found: {path}"
    env = dict(os.environ)
    if deps_root:
        node_path = os.path.join(deps_root, "node_modules")
        env["NODE_PATH"] = (node_path + os.pathsep + env["NODE_PATH"]) if env.get("NODE_PATH") else node_path
    try:
        proc = subprocess.run(
            ["node", path],
            input=json.dumps(args),
            cwd=TEMPLATES_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as e:
        return 1, "", f"{type(e).__name__}:{e}"


class _FakeResp:
    """Minimal response shim so validators.validate() works on Playwright HTML."""
    def __init__(self, html: str, status: int = 200, final_url: str = ""):
        self.text = html
        self.status_code = status
        self.url = final_url
        self.cookies = _FakeCookies()
        self.headers = {}


class _FakeCookies:
    class _Jar:
        def __iter__(self):
            return iter([])
    def __init__(self):
        self.jar = self._Jar()
    def __iter__(self):
        return iter([])


def run_playwright_fallback(
    url: str,
    *,
    profile_id: str,
    success_selectors: Optional[list[str]] = None,
    device_class: str = "auto",
    timeout: int = 90,
    profile_dir: Optional[str] = None,
    force_executor: Optional[str] = None,
) -> tuple[Attempt, str]:
    """Invoke the appropriate Playwright executor.

    force_executor: caller-specified executor name (from a profile's
    `fallback_when_challenge` list). When set, it overrides capability-based
    inference. Recognized values: "playwright_real_chrome",
    "playwright_mobile_chrome", "playwright_mcp".

    Returns (Attempt, html_content). Attempt.verdict reflects validation.
    """
    profile = load_profile(profile_id)
    capabilities = profile.get("capabilities_needed") or []
    choice = force_executor or _pick_executor(capabilities, device_class)

    t0 = time.time()
    att = Attempt(
        phase="fallback",
        executor=choice,
        url=url,
        url_transform="original",
        impersonate=None,
        referer="",
    )

    if choice == "protocol_stealth_chrome":
        return _run_protocol_stealth(att, url, success_selectors=success_selectors, timeout=timeout, t0=t0)

    if choice.startswith("playwright_mcp"):
        att.error = (
            "Playwright MCP must be invoked from the Claude session — "
            "call mcp__playwright__* tools directly instead of fetch_chain."
        )
        att.verdict = Verdict.UNKNOWN.value
        att.elapsed_s = round(time.time() - t0, 3)
        return att, ""

    deps_root = _resolve_node_deps()
    if deps_root is None:
        att.error = (
            "node/npm unavailable or `npm install` failed — local Playwright template "
            f"cannot resolve its deps (tried {TEMPLATES_DIR}, {NODE_DEPS_DIR})"
        )
        att.verdict = Verdict.UNKNOWN.value
        att.elapsed_s = round(time.time() - t0, 3)
        return att, ""

    template_map = {
        "playwright_real_chrome": "playwright_real_chrome.js",
        "playwright_mobile_chrome": "playwright_mobile_chrome.js",
    }
    template = template_map.get(choice)
    if template is None:
        att.error = f"no template for executor {choice}"
        att.verdict = Verdict.UNKNOWN.value
        att.elapsed_s = round(time.time() - t0, 3)
        return att, ""

    args: dict = {
        "url": url,
        # Per-host + per-device profile isolation. A single shared profile dir
        # (the old default) leaked cookies/storage across hosts and caused
        # profile-lock collisions when two fallbacks ran concurrently. Hashing
        # the host (not storing it) keeps the No-Site-Name Rule intact while
        # letting a host reuse its own warm storageState across calls.
        "profileDir": profile_dir or _profile_dir_for(url, choice),
        "timeout": timeout * 1000,
    }
    if choice == "playwright_mobile_chrome":
        args["device"] = "iPhone 13 Pro"
    if success_selectors:
        args["waitSelector"] = success_selectors[0]

    rc, stdout, stderr = _run_node_template(template, args, timeout=timeout + 10,
                                            deps_root=deps_root)
    att.elapsed_s = round(time.time() - t0, 3)

    if rc != 0 or not stdout:
        att.error = (stderr or "no stdout")[:300]
        att.verdict = Verdict.UNKNOWN.value
        return att, ""

    # stdout is a JSON envelope {html, finalUrl, status, cookies, userAgent,
    # innerText}. Fall back to treating raw stdout as HTML for forward/backward
    # compat (older templates that did not emit a JSON envelope).
    html, final_url, status, cookies, user_agent, automation, inner_text = _parse_envelope(stdout, url)

    resp = _FakeResp(html, status=status, final_url=final_url)
    vr = validate(resp, success_selectors=success_selectors)
    att.status = status
    att.body_size = len(html)
    att.verdict = vr.verdict.value
    att.reasons = list(vr.reasons) + ([f"automation:{automation}"] if automation else [])
    att.url = final_url or url

    # Cookie bridge: a browser that cleared a JS challenge yields exactly the
    # cookies + UA a plain HTTP client needs. Seed the curl_cffi pool so
    # subsequent same-host pages are collected cheaply (FlareSolverr pattern).
    if vr.verdict in (Verdict.STRONG_OK, Verdict.WEAK_OK) and cookies:
        _bridge_cookies_to_pool(url, cookies, user_agent)

    # Stash the rendered innerText for the render-merge step: many SPAs expose
    # visible text only via innerText; the rescue gate in fetch_chain compares
    # it against the body's visible text and keeps the longer one.
    if inner_text:
        try:
            att._inner_text = inner_text
        except Exception:
            pass

    return att, html


def _parse_envelope(stdout: str, url: str):
    """Return (html, final_url, status, cookies, user_agent, automation,
    inner_text) from a JSON envelope, or treat stdout as raw HTML if it isn't
    JSON. inner_text is "" for envelopes emitted by older templates."""
    import json
    s = stdout.lstrip()
    if s[:1] == "{":
        try:
            env = json.loads(s)
            html = env.get("html", "") or ""
            final_url = env.get("finalUrl", "") or url
            status = int(env.get("status") or 0) or 200
            cookies = env.get("cookies") or []
            user_agent = env.get("userAgent") or None
            automation = env.get("automation") or None
            # Bound the browser-controlled innerText at the parse boundary —
            # the rescue gate in fetch_chain caps again, but the cap belongs
            # here too so a hostile page cannot balloon the envelope in memory.
            inner_text = (env.get("innerText") or "")[:1_000_000]
            return html, final_url, status, cookies, user_agent, automation, inner_text
        except Exception:
            pass
    return stdout, url, 200, [], None, None, ""


def _bridge_cookies_to_pool(url: str, cookies: list, user_agent: Optional[str]) -> None:
    try:
        from .transport import POOL, pool_enabled, _host_of
        if not pool_enabled():
            return
        # Browser is real Chrome → seed the "chrome" curl identity for this host.
        POOL.inject_cookies(_host_of(url), "chrome", cookies, user_agent=user_agent)
    except Exception:
        pass

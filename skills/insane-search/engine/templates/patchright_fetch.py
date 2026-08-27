"""patchright fallback: patched Playwright driving SYSTEM Chrome (channel=chrome).

Second choice behind nodriver for protocol-fingerprinting gates: Patchright
removes the Runtime.enable / Target.setAutoAttach startup leaks, and
channel="chrome" gives a real Chrome TLS + version stamp instead of the
bundled Chromium. Apache-2.0 (nodriver is AGPL-3.0), so this is the
license-safe default when redistribution matters.

stdin:  {"url": str, "timeout": ms, "waitSelector": str?, "headless": bool?}
stdout: page HTML. stderr: diagnostics. exit 0 on content, 1 on failure.
"""
import json
import sys


def main() -> int:
    args = json.load(sys.stdin)
    from patchright.sync_api import sync_playwright

    timeout_ms = int(args.get("timeout", 60000))
    with sync_playwright() as p:
        # Headful by default — headless Chrome is scored as a bot before the
        # protocol fingerprint is even examined.
        browser = p.chromium.launch(channel="chrome", headless=bool(args.get("headless", False)))
        try:
            page = browser.new_page()
            page.goto(args["url"], timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)  # JS challenge solve window
            sel = args.get("waitSelector")
            if sel:
                try:
                    page.wait_for_selector(sel, timeout=10000)
                except Exception as e:
                    print(f"best-effort waitSelector failed: {e}", file=sys.stderr)
            sys.stdout.write(page.content() or "")
        finally:
            try:
                browser.close()
            except Exception as e:
                print(f"best-effort browser close failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

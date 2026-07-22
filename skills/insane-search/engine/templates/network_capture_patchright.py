"""network_capture (patchright): render a page and capture JSON XHR traffic.

Discovers the endpoints a JS app actually calls — the recon half of the
scraper-forge flow (R7). Drives system Chrome (channel=chrome) so protocol
fingerprinting matches a real browser.

stdin:  {"url": str, "timeout": ms, "waitSelector": str?, "scroll": bool?}
stdout: JSON {"html": str, "network": [{url, method, status, bytes, ctype}]}
stderr: diagnostics. exit 0 always when the browser ran, 1 on fatal error.
"""
import json
import sys


def main() -> int:
    args = json.load(sys.stdin)
    from patchright.sync_api import sync_playwright

    timeout_ms = int(args.get("timeout", 60000))
    network: list[dict] = []

    def on_response(resp):
        try:
            ctype = (resp.headers.get("content-type") or "").lower()
            if "json" not in ctype and resp.request.resource_type not in ("xhr", "fetch"):
                return
            body_len = 0
            try:
                body_len = len(resp.body())
            except Exception:
                pass
            network.append({
                "url": resp.url,
                "method": resp.request.method,
                "status": resp.status,
                "bytes": body_len,
                "ctype": ctype.split(";")[0],
            })
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page()
            page.on("response", on_response)
            page.goto(args["url"], timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            if args.get("scroll"):
                for _ in range(3):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1200)
            sel = args.get("waitSelector")
            if sel:
                try:
                    page.wait_for_selector(sel, timeout=10000)
                except Exception as e:
                    print(f"best-effort waitSelector failed: {e}", file=sys.stderr)
            sys.stdout.write(json.dumps({
                "html": page.content() or "",
                "network": network,
            }, ensure_ascii=False))
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

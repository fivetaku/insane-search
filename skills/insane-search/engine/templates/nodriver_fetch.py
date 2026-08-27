"""nodriver fallback: drive system Chrome over raw CDP, no Playwright shim.

Empirical rationale (2026 anti-detect bench): gates that fingerprint the
automation PROTOCOL (Runtime.enable / Target.setAutoAttach) block every
Playwright-based driver regardless of patch quality, while a plain CDP
WebSocket control plane passes. nodriver is that control plane.

stdin:  {"url": str, "timeout": ms, "waitSelector": str?, "headless": bool?}
stdout: page HTML. stderr: diagnostics. exit 0 on content, 1 on failure.
"""
import asyncio
import json
import sys


async def main() -> int:
    args = json.load(sys.stdin)
    import nodriver as uc

    # Headful by default. Cloudflare/DataDome score headless Chrome as a bot on
    # signal alone, so a headless CDP lane loses challenges a headful one clears
    # (matching the headless:false default of the Playwright templates).
    headless = bool(args.get("headless", False))
    browser = await uc.start(headless=headless)
    try:
        tab = await browser.get(args["url"])
        await tab.sleep(6)  # JS challenge solve window
        sel = args.get("waitSelector")
        if sel:
            try:
                await tab.select(sel, timeout=10)
            except Exception as e:
                print(f"best-effort waitSelector failed: {e}", file=sys.stderr)
        sys.stdout.write(await tab.get_content() or "")
    finally:
        try:
            browser.stop()
        except Exception as e:
            print(f"best-effort browser stop failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

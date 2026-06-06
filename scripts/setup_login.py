"""First Amazon login: opens Chromium **non-headless** (requires a display).

Usage:

    source .venv/bin/activate
    python scripts/setup_login.py

On a headless server, run this step over `ssh -X` (X11 forwarding) so the
browser window opens on your local machine.

Navigate to amazon.it, log in (handling any captcha/OTP manually), then return
to the terminal and press ENTER to close and save the session.
"""

from __future__ import annotations

import os
import sys

from src.browser import launch_context
from src.config import PROFILE_DIR, ensure_dirs


def main() -> int:
    ensure_dirs()
    if not os.environ.get("DISPLAY"):
        print("WARNING: DISPLAY variable not set.", file=sys.stderr)
        print("Connect with `ssh -X` and try again.", file=sys.stderr)
        return 1

    print(f"Persistent profile: {PROFILE_DIR}")
    print("Opening Chromium in visible mode. Log in to amazon.it.")
    with launch_context(headless=False) as ctx:
        page = ctx.new_page() if not ctx.pages else ctx.pages[0]
        page.goto("https://www.amazon.it/ap/signin", wait_until="domcontentloaded")
        print("\nWhen you've finished logging in (you see 'Ciao, <name>' top right),")
        print("come back here and press ENTER to close and save the session...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 1

    print("Session saved. You can close the SSH connection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

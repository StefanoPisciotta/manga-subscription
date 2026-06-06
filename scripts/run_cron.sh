#!/usr/bin/env bash
# Wrapper invoked by cron. Sets env, activates venv, runs main.
set -euo pipefail

# Resolve the project root relative to this script (scripts/ -> project root),
# so the wrapper works regardless of where the repo is checked out.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Generic UTF-8 locale (it_IT is not always generated on the system).
# Amazon is served in Italian thanks to Playwright's browser-context locale (it-IT).
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
# Minimal PATH for cron (cron has a reduced PATH by default).
export PATH="/usr/local/bin:/usr/bin:/bin"
# Playwright cache in the user's home (the default, set explicitly for clarity).
export PLAYWRIGHT_BROWSERS_PATH="${HOME}/.cache/ms-playwright"

# Activate venv
# shellcheck source=/dev/null
source "${PROJECT_DIR}/.venv/bin/activate"

# Log to stdout (cron redirects to a file via crontab)
exec python -m src.main

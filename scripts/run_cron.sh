#!/usr/bin/env bash
# Wrapper invocato da cron. Imposta env, attiva venv, lancia main.
set -euo pipefail

PROJECT_DIR="/home/altecspace.it/spisciotta/personal/one-piece"
cd "$PROJECT_DIR"

# Locale UTF-8 generico (it_IT non sempre generato sul sistema).
# Amazon serve in italiano grazie al locale di Playwright (it-IT) nel browser context.
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
# PATH minimale per cron (di default cron ha PATH ridotto).
export PATH="/usr/local/bin:/usr/bin:/bin"
# Cache Playwright nell'home utente (default, esplicito per chiarezza).
export PLAYWRIGHT_BROWSERS_PATH="${HOME}/.cache/ms-playwright"

# Attiva venv
# shellcheck source=/dev/null
source "${PROJECT_DIR}/.venv/bin/activate"

# Log su stdout (cron redirige al file via crontab)
exec python -m src.main

"""Primo login Amazon: apre Chromium **non-headless** (richiede X11 forwarding).

Uso (da macchina locale con X server):

    ssh -X spisciotta-dev.altecspace.it
    cd ~/personal/one-piece
    source .venv/bin/activate
    python scripts/setup_login.py

Naviga su amazon.it, fai login (gestendo eventuali captcha/OTP manualmente),
poi torna sul terminale e premi INVIO per chiudere e salvare la sessione.
"""

from __future__ import annotations

import os
import sys

from src.browser import launch_context
from src.config import PROFILE_DIR, ensure_dirs


def main() -> int:
    ensure_dirs()
    if not os.environ.get("DISPLAY"):
        print("ATTENZIONE: variabile DISPLAY non impostata.", file=sys.stderr)
        print("Connettiti con `ssh -X` e riprova.", file=sys.stderr)
        return 1

    print(f"Profilo persistente: {PROFILE_DIR}")
    print("Apro Chromium in modalita' visibile. Effettua il login su amazon.it.")
    with launch_context(headless=False) as ctx:
        page = ctx.new_page() if not ctx.pages else ctx.pages[0]
        page.goto("https://www.amazon.it/ap/signin", wait_until="domcontentloaded")
        print("\nQuando hai finito il login (vedi 'Ciao, <nome>' in alto a destra),")
        print("torna qui e premi INVIO per chiudere e salvare la sessione...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nInterrotto.")
            return 1

    print("Sessione salvata. Puoi chiudere la connessione SSH.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

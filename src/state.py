from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from src.config import STATE_FILE


class State(TypedDict, total=False):
    current_volume: int
    last_purchase_at: str
    last_purchased_volume: int
    last_order_id: str


def read_state() -> State:
    if not STATE_FILE.exists():
        raise RuntimeError(
            f"state.json non trovato in {STATE_FILE}. "
            "Inizializzalo con: echo '{\"current_volume\": 63}' > state/state.json"
        )
    with STATE_FILE.open() as f:
        return json.load(f)


def write_state(state: State) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=STATE_FILE.parent, prefix=".state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def record_purchase(volume: int, order_id: str | None = None) -> State:
    state = read_state()
    state["current_volume"] = volume
    state["last_purchased_volume"] = volume
    state["last_purchase_at"] = datetime.now().astimezone().isoformat()
    if order_id:
        state["last_order_id"] = order_id
    write_state(state)
    return state

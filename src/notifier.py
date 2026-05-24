"""Notifiche via Telegram Bot API.

Usa urllib stdlib (niente dipendenze extra). Per le conferme usa
inline keyboard + getUpdates polling con offset, niente webhook.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from src.config import Config

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
HTTP_TIMEOUT = 30


def _api_url(token: str, method: str) -> str:
    return f"{API_BASE}/bot{token}/{method}"


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")
    return body["result"]


def _post_multipart(url: str, fields: dict, files: dict[str, Path]) -> dict:
    """POST multipart/form-data per upload file (sendPhoto)."""
    boundary = f"----one-piece-{uuid.uuid4().hex}"
    body = bytearray()
    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.extend(f"{v}\r\n".encode())
    for field_name, path in files.items():
        ctype, _ = mimetypes.guess_type(str(path))
        ctype = ctype or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error (multipart): {result}")
    return result["result"]


def send_message(cfg: Config, text: str, reply_markup: dict | None = None) -> int:
    """Invia un messaggio testuale. Ritorna message_id."""
    payload: dict = {
        "chat_id": cfg.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _post_json(_api_url(cfg.telegram_bot_token, "sendMessage"), payload)
    return result["message_id"]


def send_photo(cfg: Config, photo: Path, caption: str, reply_markup: dict | None = None) -> int:
    fields: dict = {
        "chat_id": str(cfg.telegram_chat_id),
        "caption": caption,
        "parse_mode": "HTML",
    }
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup)
    result = _post_multipart(
        _api_url(cfg.telegram_bot_token, "sendPhoto"),
        fields=fields,
        files={"photo": photo},
    )
    return result["message_id"]


def edit_message_text(cfg: Config, message_id: int, text: str) -> None:
    _post_json(
        _api_url(cfg.telegram_bot_token, "editMessageText"),
        {
            "chat_id": cfg.telegram_chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
        },
    )


def edit_message_caption(cfg: Config, message_id: int, caption: str) -> None:
    _post_json(
        _api_url(cfg.telegram_bot_token, "editMessageCaption"),
        {
            "chat_id": cfg.telegram_chat_id,
            "message_id": message_id,
            "caption": caption,
            "parse_mode": "HTML",
        },
    )


def answer_callback(cfg: Config, callback_id: str, text: str = "") -> None:
    try:
        _post_json(
            _api_url(cfg.telegram_bot_token, "answerCallbackQuery"),
            {"callback_query_id": callback_id, "text": text},
        )
    except Exception as e:
        log.warning("answerCallbackQuery fallito (non bloccante): %s", e)


def send_purchase_request(cfg: Config, screenshot: Path, caption: str, token: str) -> int:
    """Invia foto con pulsanti Conferma/Annulla. `token` distingue questa richiesta dalle precedenti."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Conferma acquisto", "callback_data": f"buy:confirm:{token}"},
            {"text": "❌ Annulla", "callback_data": f"buy:cancel:{token}"},
        ]]
    }
    return send_photo(cfg, screenshot, caption, reply_markup=keyboard)


def wait_for_callback(cfg: Config, token: str) -> str:
    """Polling getUpdates finche' arriva una callback con il token atteso.

    Ritorna 'confirm', 'cancel', o 'timeout'.
    """
    deadline = time.monotonic() + cfg.confirm_timeout_hours * 3600
    poll_seconds = cfg.confirm_poll_seconds
    offset: int | None = None

    log.info("Attendo callback Telegram (token=%s, timeout=%sh)", token, cfg.confirm_timeout_hours)

    while time.monotonic() < deadline:
        try:
            params: dict = {"timeout": min(poll_seconds, 25), "allowed_updates": ["callback_query"]}
            if offset is not None:
                params["offset"] = offset
            updates = _post_json(_api_url(cfg.telegram_bot_token, "getUpdates"), params)
        except urllib.error.URLError as e:
            log.warning("getUpdates fallito (riprovo): %s", e)
            time.sleep(poll_seconds)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            cb = update.get("callback_query")
            if not cb:
                continue
            data = cb.get("data", "")
            if not data.startswith("buy:"):
                continue
            try:
                _, action, recv_token = data.split(":", 2)
            except ValueError:
                continue
            if recv_token != token:
                answer_callback(cfg, cb["id"], "Richiesta non valida o scaduta.")
                continue
            if action == "confirm":
                answer_callback(cfg, cb["id"], "Confermato.")
                return "confirm"
            if action == "cancel":
                answer_callback(cfg, cb["id"], "Annullato.")
                return "cancel"

    return "timeout"


def new_request_token() -> str:
    return uuid.uuid4().hex[:12]


if __name__ == "__main__":
    import argparse

    from src.config import load_config

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Invia messaggio di prova e attende callback 60s")
    parser.add_argument("--get-chat-id", action="store_true", help="Stampa gli updates ricevuti dal bot per scoprire il tuo chat_id")
    args = parser.parse_args()

    cfg = load_config()

    if args.get_chat_id:
        # Per scoprire il chat_id: avvia il bot scrivendogli /start su Telegram,
        # poi lancia questo comando.
        result = _post_json(_api_url(cfg.telegram_bot_token, "getUpdates"), {})
        if not result:
            print("Nessun update. Vai su Telegram, cerca il tuo bot, mandagli /start e riprova.")
        else:
            for upd in result:
                msg = upd.get("message") or upd.get("callback_query", {}).get("message")
                if msg:
                    print(f"chat_id={msg['chat']['id']}  from={msg['chat'].get('username') or msg['chat'].get('first_name')}")
    elif args.test:
        token = new_request_token()
        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ OK", "callback_data": f"buy:confirm:{token}"},
                {"text": "❌ KO", "callback_data": f"buy:cancel:{token}"},
            ]]
        }
        send_message(cfg, "<b>Test notifier</b>\nPremi un pulsante entro 60s.", reply_markup=keyboard)
        # Override timeout per il test
        cfg_short = cfg.__class__(**{**cfg.__dict__, "confirm_timeout_hours": 60 / 3600, "confirm_poll_seconds": 2})
        result = wait_for_callback(cfg_short, token)
        print(f"Risultato: {result}")

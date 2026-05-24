from __future__ import annotations

import html
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from src import amazon, browser, notifier, state
from src.config import LOGS_DIR, ensure_dirs, load_config

log = logging.getLogger("one-piece")


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"one-piece-{datetime.now():%Y-%m}.log"
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=6, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(stream)


def _safe_notify(cfg, text: str) -> None:
    try:
        notifier.send_message(cfg, text)
    except Exception as e:
        log.error("Notifica Telegram fallita: %s", e)


def main() -> int:
    setup_logging()
    ensure_dirs()
    cfg = load_config()
    current_state = state.read_state()
    target = cfg.target_volume_override or current_state["current_volume"] + 1
    log.info("Volume target: %d (dry_run=%s)", target, cfg.dry_run)

    query = cfg.search_query_template.format(volume=target)

    try:
        with browser.launch_context(headless=True) as ctx:
            search_page = amazon.search_volume(ctx, query)
            product_page = amazon.open_first_relevant_result(search_page, target)
            product = amazon.extract_product(product_page)
            log.info(
                "Prodotto: %s | %.2f EUR | editore=%s | binding=%s | stock=%s",
                product.title, product.price_eur, product.publisher, product.binding, product.in_stock,
            )
            amazon.validate(product, target, cfg.max_price_eur)

            review_screenshot = amazon.go_to_buy_now_review(product_page)

            footer = (
                "⚠️ DRY_RUN: nessun acquisto verra' effettuato."
                if cfg.dry_run
                else f"Conferma entro {cfg.confirm_timeout_hours:g}h."
            )
            caption = (
                f"<b>One Piece vol. {target}</b>\n"
                f"{html.escape(product.title)}\n\n"
                f"💶 <b>{product.price_eur:.2f} EUR</b> (soglia {cfg.max_price_eur:.2f})\n"
                f"🏢 {html.escape(product.publisher)}\n"
                f"🔗 <a href=\"{html.escape(product.url)}\">Pagina prodotto</a>\n\n"
                f"{footer}"
            )

            if cfg.dry_run:
                notifier.send_photo(cfg, review_screenshot, caption)
                log.info("DRY_RUN attivo: notifica inviata, niente acquisto.")
                return 0

            token = notifier.new_request_token()
            msg_id = notifier.send_purchase_request(cfg, review_screenshot, caption, token)
            result = notifier.wait_for_callback(cfg, token)

            if result == "timeout":
                notifier.edit_message_caption(
                    cfg, msg_id,
                    caption + f"\n\n⏱️ <b>TIMEOUT</b>: nessun acquisto effettuato.",
                )
                log.warning("Timeout: nessun acquisto per vol. %d", target)
                return 2

            if result == "cancel":
                notifier.edit_message_caption(
                    cfg, msg_id,
                    caption + "\n\n❌ <b>Annullato</b> dall'utente.",
                )
                log.info("Acquisto annullato dall'utente per vol. %d", target)
                return 0

            # result == "confirm"
            order_id = amazon.place_order(product_page)
            new_state = state.record_purchase(target, order_id=order_id)
            log.info("Acquisto registrato: %s", new_state)
            notifier.edit_message_caption(
                cfg, msg_id,
                caption + f"\n\n✅ <b>Ordine confermato</b>" + (f" — #{order_id}" if order_id else ""),
            )
            return 0

    except amazon.ValidationError as e:
        log.error("Validazione fallita: %s", e)
        _safe_notify(
            cfg,
            f"⚠️ <b>Validazione fallita vol. {target}</b>\n\n<pre>{html.escape(str(e))}</pre>\n\nNessun acquisto effettuato.",
        )
        return 3
    except Exception as e:
        log.exception("Errore inatteso: %s", e)
        _safe_notify(
            cfg,
            f"🛑 <b>ERRORE vol. {target}</b>\n<code>{html.escape(repr(e))}</code>",
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())

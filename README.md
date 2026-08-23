# One Piece auto-buy

Automatically buys the next volume of *One Piece New Edition* on Amazon.it each
month, using Playwright + cron, with **manual confirmation via Telegram**
(inline buttons) before the final click.

> ### ⚠️ Read before using
>
> - **This spends real money.** It drives a logged-in Amazon account and places
>   real orders against the payment method and address saved on it. Keep
>   `DRY_RUN=true` until you have watched a full run end to end.
> - **Automating Amazon likely violates its Conditions of Use**, which prohibit
>   accessing the site with robots or automated tools. Running this may put your
>   Amazon account at risk, up to suspension. Personal, non-commercial
>   experiment — use it at your own risk.
> - **No warranty.** See [LICENSE](LICENSE). The author is not liable for
>   unwanted purchases, account actions, or anything else that follows from
>   running this code.
> - Written for **amazon.it** and an Italian-language page layout. It will not
>   work as-is on other Amazon domains.

## How it works

On the 1st of each month the script:

1. Reads the current volume from `state/state.json` and targets the next one (`N + 1`).
2. Searches Amazon.it for that volume.
3. Opens the first relevant result and extracts title, price, publisher, binding and availability.
4. Validates it (see *Purchase safety* below).
5. Opens the 1-click order review page and sends a Telegram message with a screenshot and two buttons.
6. On **✅ Confirm** it places the order and records the purchase; on **❌ Cancel** or timeout it does nothing.

When `DRY_RUN=true` it runs everything except the final order click — it only sends the notification.

## Setup (one-time)

Run from the project directory.

> **Shell note:** the examples below are for `bash`. If you use `fish`, replace
> `source .venv/bin/activate` with `source .venv/bin/activate.fish`, `&&` with
> `; and`, and `FOO=bar python ...` with `env FOO=bar python ...`.

```bash
# 1. Virtualenv and dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# 2. Download Chromium (~150 MB into ~/.cache/ms-playwright)
playwright install chromium

# 3. System libraries for Chromium
#    On most Debian/Ubuntu systems: `playwright install-deps`.
#    On other distros it may already work. If Chromium fails to start, list the
#    missing libraries with:
#      ldd ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome | grep "not found"
#    and install the equivalent packages with your distro's package manager.

# 4. Configuration (see "Telegram bot setup" below)
cp .env.example .env
${EDITOR:-vi} .env   # fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

# 5. Initialize state with the volume you currently own
echo '{"current_volume": 63}' > state/state.json

# 6. First Amazon login — must be done on a machine with a display:
#    source .venv/bin/activate
#    python scripts/setup_login.py
#    -> Chromium opens in a visible window
#    -> log in to amazon.it, handle any captcha/OTP
#    -> return to the terminal and press ENTER
#
#    On a headless server, run this step over `ssh -X` (X11 forwarding) so the
#    browser window opens on your local machine.
```

## Telegram bot setup

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`, choose a name (e.g. `One Piece Autobuy`) and a username ending in `bot` (e.g. `one_piece_autobuy_bot`).
3. BotFather replies with a token like `123456789:ABCdef...`. Put it in `TELEGRAM_BOT_TOKEN` in `.env`.
4. Search for your new bot on Telegram and send it `/start` (this unlocks the chat — otherwise the bot can't message you).
5. Find your `chat_id` with the helper script:

   ```bash
   source .venv/bin/activate
   python -m src.notifier --get-chat-id
   ```

   It prints something like `chat_id=123456789 from=...`. Put it in `TELEGRAM_CHAT_ID` in `.env`.

6. Test sending + buttons:

   ```bash
   python -m src.notifier --test
   ```

   You'll get a message with two buttons; press one within 60s and the script prints `confirm` or `cancel`.

## Test and dry-run

```bash
source .venv/bin/activate

# Dependency smoke test
python -c "from playwright.sync_api import sync_playwright; print('ok')"

# Full dry-run (DRY_RUN=true in .env): searches, validates, sends the Telegram
# notification, but does NOT buy. To test you can force an already-released volume:
TARGET_VOLUME=1 MAX_PRICE_EUR=10 python -m src.main

# Real run (DRY_RUN=false): searches, validates, sends a Telegram message with
# Confirm/Cancel buttons, waits for N hours, then buys (or cancels / times out).
python -m src.main
```

To authorize a purchase, press the **✅ Confirm purchase** button in the Telegram message.

## Cron

Add to your crontab (`crontab -e`), using an absolute path to the script:

```
0 9 1 * * /absolute/path/to/one-piece/scripts/run_cron.sh >> /absolute/path/to/one-piece/logs/cron.log 2>&1
```

Check the system timezone:

```bash
timedatectl | grep "Time zone"   # should be Europe/Rome
```

## Project structure

```
src/
  config.py     env loader + paths
  state.py      atomic read/write of state.json
  browser.py    Playwright factory + stealth + persistent profile
  notifier.py   Telegram Bot API (sendPhoto + inline buttons + getUpdates)
  amazon.py     search, validation, 1-click checkout
  main.py       orchestration (cron entrypoint)
scripts/
  setup_login.py  first interactive login
  run_cron.sh     wrapper invoked by cron
state/
  state.json      { "current_volume": N }
  profile/        Chromium user-data-dir (cookies, session)
  screenshots/    pre-purchase and order screenshots
logs/
  one-piece-YYYY-MM.log
  cron.log
```

## Purchase safety

The script **never buys without manual confirmation** via the Telegram button,
except when `DRY_RUN=true` (which disables buying entirely and only notifies).
A hard-fail validation blocks the purchase before even asking for confirmation if:

- the title does not contain `One Piece`, `New Edition`, `vol. N`
- the publisher is not Star Comics (Panini is accepted as a fallback)
- the binding is not a paper format
- the price is above `MAX_PRICE_EUR`
- the product is not available

On any failure: a Telegram alert is sent, the process exits non-zero, and state is left unchanged.

## Troubleshooting

- **`playwright install chromium` fails with SSL/network errors**: check any corporate proxy, possibly set `HTTPS_PROXY=...`.
- **Telegram: `chat not found` or `Forbidden: bot was blocked`**: you must send `/start` to the bot on Telegram before the first message.
- **`python -m src.notifier --get-chat-id` returns empty**: no messages in the bot's inbox. Send it a `/start` on Telegram and try again.
- **Inline buttons don't respond**: the script polls `getUpdates`. If a webhook is configured on the same bot, `getUpdates` receives nothing. Disable the webhook: `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"`.
- **Validation always fails on publisher/binding**: Amazon changed its markup → update the selectors in `src/amazon.py` (see the verification-date comment at the top).
- **Cron doesn't run**: check `grep CRON /var/log/cron` and verify PATH/HOME in the wrapper.
- **Amazon session expired** (login required during a headless cron run): re-run `scripts/setup_login.py` with a display (e.g. over `ssh -X`).

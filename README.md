# One Piece auto-buy

Acquisto automatico mensile del volume successivo di *One Piece New Edition*
su Amazon.it via Playwright + cron, con **conferma manuale via Telegram**
(pulsanti inline) prima del click finale.

## Setup (una tantum)

Eseguire dalla directory del progetto.

> **Nota shell:** gli esempi sotto sono per `bash`. Se usi **fish** (come la shell di default su questa VM), sostituisci ovunque:
> - `source .venv/bin/activate` → `source .venv/bin/activate.fish`
> - `&&` → `; and`
> - `FOO=bar python ...` → `env FOO=bar python ...` (oppure `set -lx FOO bar; python ...`)
> Lo step `sudo .venv/bin/playwright ...` funziona identico in entrambe le shell perche' invoca direttamente il binario senza attivare il venv.

```bash
cd ~/personal/one-piece

# 1. Virtualenv e dipendenze
python3 -m venv .venv
source .venv/bin/activate          # fish: source .venv/bin/activate.fish
pip install --upgrade pip
pip install -e .

# 2. Download Chromium (~150 MB in ~/.cache/ms-playwright)
playwright install chromium

# 3. Librerie di sistema per Chromium
#    SU QUESTA VM (Oracle Linux 8.10) NON SERVE: le system-lib (nss, atk, cairo,
#    pango, libdrm, libxkbcommon) sono gia' presenti, Chromium parte direttamente.
#    `playwright install-deps` fallirebbe comunque (assume apt-get / Ubuntu).
#    Se domani migri su una macchina dove Chromium non parte, usa ldd:
#      ldd ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome | grep "not found"
#    e installa le librerie equivalenti via dnf.

# 4. Configurazione (vedi sezione "Setup Telegram bot" sotto)
cp .env.example .env
${EDITOR:-vi} .env   # compila TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID

# 5. Inizializza state
echo '{"current_volume": 63}' > state/state.json

# 6. Primo login Amazon — DA MACCHINA LOCALE con X server:
#    ssh -X spisciotta-dev.altecspace.it
#    cd ~/personal/one-piece && source .venv/bin/activate     # fish: source .venv/bin/activate.fish
#    python scripts/setup_login.py
#    -> Chromium si apre sulla tua macchina via X11
#    -> login su amazon.it, gestisci eventuali captcha/OTP
#    -> torna sul terminale e premi INVIO
```

## Setup Telegram bot

1. Apri Telegram, cerca **@BotFather**.
2. Manda `/newbot`, scegli un nome (es. `One Piece Autobuy`) e un username che termini in `bot` (es. `one_piece_autobuy_bot`).
3. BotFather risponde con un token tipo `123456789:ABCdef...`. Copialo in `TELEGRAM_BOT_TOKEN` nel `.env`.
4. Su Telegram cerca il tuo bot appena creato e mandagli `/start` (serve a "sbloccare" la chat, altrimenti il bot non può scriverti).
5. Scopri il tuo `chat_id` con lo script helper:

   ```bash
   source .venv/bin/activate          # fish: source .venv/bin/activate.fish
   python -m src.notifier --get-chat-id
   ```

   Stampa qualcosa come `chat_id=123456789 from=stefano`. Copialo in `TELEGRAM_CHAT_ID` nel `.env`.

6. Test invio + pulsanti:

   ```bash
   python -m src.notifier --test
   ```

   Riceverai un messaggio con due bottoni; premine uno entro 60s, lo script stampa `confirm` o `cancel`.

## Test e dry-run

```bash
source .venv/bin/activate          # fish: source .venv/bin/activate.fish

# Smoke test dipendenze
python -c "from playwright.sync_api import sync_playwright; print('ok')"

# Dry-run completo (DRY_RUN=true nel .env): cerca, valida, manda notifica Telegram,
# NON acquista. Per testare puoi forzare un volume gia' uscito:
TARGET_VOLUME=1 MAX_PRICE_EUR=10 python -m src.main
# fish equivalent:
# env TARGET_VOLUME=1 MAX_PRICE_EUR=10 python -m src.main

# Esecuzione reale (DRY_RUN=false): cerca, valida, manda Telegram con bottoni
# Conferma/Annulla, attende per N ore, poi acquista (o annulla / timeout).
python -m src.main
```

Per autorizzare l'acquisto: premi il bottone **✅ Conferma acquisto** nel messaggio Telegram.

## Cron

Aggiungere alla crontab (`crontab -e`):

```
0 9 1 * * /home/altecspace.it/spisciotta/personal/one-piece/scripts/run_cron.sh >> /home/altecspace.it/spisciotta/personal/one-piece/logs/cron.log 2>&1
```

Verifica timezone del sistema:

```bash
timedatectl | grep "Time zone"   # deve essere Europe/Rome
```

## Struttura

```
src/
  config.py     env loader + percorsi
  state.py      lettura/scrittura atomica state.json
  browser.py    factory Playwright + stealth + profilo persistente
  notifier.py   Telegram Bot API (sendPhoto + inline buttons + getUpdates)
  amazon.py     ricerca, validazione, checkout 1-click
  main.py       orchestrazione (entrypoint cron)
scripts/
  setup_login.py  primo login interattivo via X11
  run_cron.sh     wrapper invocato da cron
state/
  state.json      { "current_volume": N }
  profile/        user-data-dir Chromium (cookie, sessione)
  screenshots/    screenshot pre-acquisto e ordine
logs/
  one-piece-YYYY-MM.log
  cron.log
```

## Sicurezza acquisti

Lo script **non acquista mai senza conferma manuale** via pulsante Telegram, salvo quando `DRY_RUN=true` (che disabilita completamente l'acquisto e si limita a notificare). La validazione hard-fail blocca l'acquisto prima ancora di chiedere conferma se:

- titolo non contiene `One Piece`, `New Edition`, `vol. N`
- editore diverso da Panini
- formato non cartaceo
- prezzo > `MAX_PRICE_EUR`
- prodotto non disponibile

In caso di fail → notifica Telegram di alert, exit non-zero, nessuna modifica di state.

## Troubleshooting

- **`playwright install chromium` fallisce con SSL/network**: controlla proxy aziendale, eventualmente `HTTPS_PROXY=...`.
- **Telegram: `chat not found` o `Forbidden: bot was blocked`**: devi mandare `/start` al bot da Telegram prima del primo invio.
- **`python -m src.notifier --get-chat-id` ritorna vuoto**: nessun messaggio nella inbox del bot. Mandagli un `/start` da Telegram e riprova.
- **Bottoni inline non rispondono**: lo script fa polling di `getUpdates`. Se hai un webhook configurato sullo stesso bot, `getUpdates` non riceve nulla. Disattiva il webhook: `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"`.
- **Validazione fallisce sempre per editore/formato**: Amazon ha cambiato il markup → aggiornare i selettori in `src/amazon.py` (vedi commento data verifica in cima).
- **Cron non parte**: `grep CRON /var/log/cron` e verificare PATH/HOME nel wrapper.
- **Sessione Amazon scaduta** (login richiesto durante cron headless): rilanciare `scripts/setup_login.py` via SSH X11.

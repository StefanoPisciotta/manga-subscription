# Amazon One Piece Auto-Buy Bot

## Obiettivo
Script Python che ogni mese acquista automaticamente il volume successivo di One Piece (New Edition) su Amazon.it tramite Playwright, schedulato con cron.

## Ambiente di esecuzione
- **OS:** Oracle Linux (VM aziendale, sempre attiva)
- **Python:** da verificare (`python3 --version`)
- **Sudo/root:** da verificare
- **Display:** headless (nessun display fisico)

## Stack tecnico
- **Playwright** (Python) — automazione browser headless
- **playwright-stealth** — evasione anti-bot Amazon
- **cron** — scheduling mensile (1° del mese)
- Profilo Chrome persistente con sessione Amazon già autenticata

## Stato attuale
- Volume attualmente posseduto: **63**
- Prossimo acquisto: **volume 64**, giugno 2026
- Serie: One Piece **New Edition**
- Amazon: account con 1-click abilitato, carta e indirizzo già salvati

## Flusso previsto
1. Avvio script il 1° del mese
2. Cerca su Amazon.it "One Piece New Edition vol. N" (N = volume corrente + 1)
3. Seleziona il risultato corretto (formato cartaceo, editore Star Comics)
4. Acquisto con 1-click
5. Log del risultato (successo/fallimento) su file

## Da fare
- [ ] Verificare versione Python sulla VM
- [ ] Verificare accesso sudo
- [ ] Installare Playwright + playwright-stealth
- [ ] Creare profilo Chrome persistente con sessione Amazon attiva
- [ ] Scrivere lo script principale
- [ ] Configurare il cronjob
- [ ] Testare in dry-run (senza acquisto reale)

## Note
- Amazon rileva browser headless → necessario `playwright-stealth` + profilo persistente
- Il volume corrente va tracciato in un file di stato (es. `state.json`) e incrementato dopo ogni acquisto riuscito
- Gestire il caso in cui il volume non sia ancora disponibile (retry o notifica)
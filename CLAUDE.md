# Amazon One Piece Auto-Buy Bot

## Goal
A Python script that every month automatically buys the next volume of One Piece (New Edition) on Amazon.it via Playwright, scheduled with cron.

## Runtime environment
- **OS:** Linux server, always on
- **Python:** 3.10+ (`python3 --version`)
- **Display:** headless (no physical display)

## Tech stack
- **Playwright** (Python) — headless browser automation
- **playwright-stealth** — reduces automation fingerprints that break page rendering
- **cron** — monthly scheduling (1st of the month)
- Persistent Chrome profile with an already-authenticated Amazon session

## Scope
- Series: One Piece **New Edition** (publisher Star Comics)
- The current volume is tracked in `state/state.json` and incremented after each successful purchase
- Requires an Amazon account with 1-click enabled (card and address saved)

## Flow
1. Script starts on the 1st of the month
2. Searches Amazon.it for "One Piece New Edition vol. N" (N = current volume + 1)
3. Selects the correct result (paper format, publisher Star Comics)
4. Buys with 1-click
5. Logs the result (success/failure) to file

## Setup checklist
- [ ] Verify the Python version on the VM
- [ ] Verify sudo access
- [ ] Install Playwright + playwright-stealth
- [ ] Create a persistent Chrome profile with an active Amazon session
- [ ] Write the main script
- [ ] Configure the cronjob
- [ ] Test in dry-run (no real purchase)

## Notes
- A plain headless browser does not render the pages reliably → `playwright-stealth` + a persistent profile are required
- The current volume must be tracked in a state file (e.g. `state.json`) and incremented after each successful purchase
- Handle the case where the volume is not yet available (retry or notify)

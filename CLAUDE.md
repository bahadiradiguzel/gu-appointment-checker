# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Bot Does

Monitors a Qmatic-based booking system for earlier appointment slots and sends a notification when one appears. Runs periodically via GitHub Actions.

## Running the Bot

```bash
pip install -r requirements.txt
python checker.py
```

## Architecture

Single-file bot (`checker.py`) with no framework. Flow: fetch dates API → fetch times per date → diff against `state.json` → send notification if earlier slot found → save new state.

**Key design decision:** Uses Qmatic's REST API directly (no Selenium):
- Dates: `GET /rest/schedule/branches/{BRANCH_ID}/dates;servicePublicId={SERVICE_ID};customSlotLength=25`
- Times: `GET /rest/schedule/branches/{BRANCH_ID}/dates/{date}/times;servicePublicId={SERVICE_ID};customSlotLength=25`

**Notification logic:** Only alerts when a date *earlier* than the current earliest known date appears. New far-future dates are silently ignored.

**State persistence:** `state.json` stores `[{"date": "YYYY-MM-DD", "times": ["HH:MM", ...]}, ...]`. On GitHub Actions, this file is committed back to the repo after each run (`[skip ci]` prevents workflow loops).

## Configuration Constants (top of checker.py)

| Constant | Purpose |
|----------|---------|
| `BRANCH_ID` | Qmatic branch identifier (from API URL) |
| `SERVICE_ID` | Qmatic service identifier (from API URL) |
| `MIN_DATE` | Ignore slots before this date |
| `TELEGRAM_BOT_TOKEN` | Read from `TELEGRAM_BOT_TOKEN` env var |
| `TELEGRAM_CHAT_ID` | Read from `TELEGRAM_CHAT_ID` env var |

## GitHub Actions Setup

Workflow at `.github/workflows/check.yml` runs on a cron schedule. Requires two repository secrets: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. The `contents: write` permission is needed to commit `state.json`.

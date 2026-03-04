# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
pip install -r requirements.txt
python checker.py
```

## Architecture

Single-file bot (`checker.py`) with no framework. Flow: fetch dates API → fetch times per date → diff against `state.json` → send notification if earlier slot found → save new state.

**API endpoints used:**
- Dates: `GET {BASE_URL}/branches/{BRANCH_ID}/dates;servicePublicId={SERVICE_ID};customSlotLength=25`
- Times: `GET {BASE_URL}/branches/{BRANCH_ID}/dates/{date}/times;servicePublicId={SERVICE_ID};customSlotLength=25`

**Notification logic:** Only alerts when a date *earlier* than the current earliest known date appears, and only if that date is on or before `MAX_NOTIFY_DATE`. New far-future dates are silently ignored.

**State persistence:** `state.json` stores `[{"date": "YYYY-MM-DD", "times": ["HH:MM", ...]}, ...]`. On GitHub Actions, this file is committed back to the repo after each run (`[skip ci]` prevents workflow loops).

## Configuration Constants (top of checker.py)

| Constant | Purpose |
|----------|---------|
| `BASE_URL` | Scheduling API base URL |
| `BRANCH_ID` | Branch identifier (from API URL) |
| `SERVICE_ID` | Service identifier (from API URL) |
| `MIN_DATE` | Ignore slots before this date |
| `MAX_NOTIFY_DATE` | Skip notifications for slots after this date |
| `TELEGRAM_BOT_TOKEN` | Read from `TELEGRAM_BOT_TOKEN` env var |
| `TELEGRAM_CHAT_ID` | Read from `TELEGRAM_CHAT_ID` env var |
| `SERVICE_NAME` | Read from `SERVICE_NAME` env var (shown in notifications) |

## GitHub Actions Setup

Workflow at `.github/workflows/check.yml` runs every 10 minutes via cron. Requires three repository secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SERVICE_NAME`. The `contents: write` permission is needed to commit `state.json`.

Settings → Actions → General → Workflow permissions must be set to **Read and write permissions**.

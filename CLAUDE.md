# CLAUDE.md — Infinity Pay Telegram Support Bot

## Project Overview
Infinity Pay Telegram Support Bot v2 — customer support bot for Infinity Pay Inc.
Merchants write to the bot on Telegram, AI (Claude) analyzes and classifies the issue,
creates a ClickUp ticket, and routes it to the support team.

## Tech Stack
- **Language:** Python 3.11
- **Telegram:** python-telegram-bot 20.7 (with job-queue)
- **AI:** Anthropic Claude (Haiku for simple, Sonnet for complex), OpenAI Whisper (voice)
- **Task management:** ClickUp API v2
- **Deployment:** Railway (auto-deploy from GitHub main branch)
- **Container:** Docker (python:3.11-slim)

## File Structure
```
bot.py              — main bot file (all logic in one file)
clickup_ids.json    — ClickUp custom field IDs mapping
requirements.txt    — Python dependencies
Dockerfile          — Docker container config
README.md           — project README
.gitignore          — git ignore rules
CLAUDE.md           — this file
```

## Key Features (v2)
1. **Hybrid AI:** Haiku for simple questions → Sonnet for complex ones
2. **Smart categories:** Terminal, Payment, Chargeback, Statement, Billing, Account, Software, Hardware, Fraud, Compliance, General (no "Other")
3. **Priorities:** Urgent 🔴 / High 🟠 / Normal 🟡 / Low 🟢
4. **Sessions:** groups messages into one ticket (10 min timeout)
5. **Voice messages:** transcribed via Whisper API
6. **Support group:** tickets duplicated to TG support group
7. **Agent/ISO login:** /login + secret code (IAMAGENT, ISO-MASTER)
8. **ClickUp sync:** ticket status updates → user notifications
9. **FAQ cache:** caches common answers (24h TTL, max 200)
10. **Anti-spam:** max 10 messages per 60 seconds

## Environment Variables (Railway)
```
TELEGRAM_BOT_TOKEN      — Telegram bot token
CLAUDE_API_KEY          — Anthropic API key
CLICKUP_API_TOKEN       — ClickUp API token
CLICKUP_LIST_TICKETS_ID — ClickUp list ID for tickets
CLICKUP_LIST_MERCHANTS_ID — ClickUp list ID for merchants
SUPPORT_GROUP_CHAT_ID   — Telegram group chat ID for support team
OPENAI_API_KEY          — OpenAI API key (for Whisper voice transcription)
```

## Bot Commands
- `/start` — welcome message, merchant identification
- `/login` — agent/ISO login prompt
- `/stats` — bot statistics (agents only)
- `/recent` — recent tickets (agents only)

## How It Works
1. Merchant sends message → bot identifies merchant by TG ID via ClickUp
2. AI (Haiku) classifies: category + priority + summary
3. If complex → escalates to Sonnet for deeper analysis
4. Creates ClickUp ticket with custom fields (source, merchant, MID, category, priority, channel, phone)
5. Posts ticket summary to TG support group
6. Periodic job checks ClickUp for status changes → notifies merchant

## Development Notes
- All code is in a single `bot.py` file (~1280 lines)
- State is stored in-memory (dicts), no database
- Bot uses polling mode (not webhooks)
- Cyrillic comments in bot.py — UI text is in Russian
- ClickUp custom field IDs are hardcoded in bot.py AND in clickup_ids.json
- Railway auto-deploys on every push to main — be careful with commits

## Known Issues
- bot.py on GitHub has double-encoded UTF-8 (Cyrillic text appears as mojibake) — cosmetic only, bot works fine
- No persistent storage — restart clears sessions, FAQ cache, stats

## Important: Editing bot.py
- The file is ~1280 lines — when editing on GitHub web editor, CodeMirror virtualizes content
- Always verify syntax before committing (missing colons, brackets, etc.)
- Railway will crash-loop on SyntaxError — check deploy logs after every commit

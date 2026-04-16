# STACK.md — Infinity Pay Telegram Support Bot

## Language & Runtime
- **Language:** Python 3.11
- **Container:** Docker (python:3.11-slim)
- **Deployment:** Railway (auto-deploy from GitHub `main` branch)
- **Entry point:** `bot.py` — single file, launched via `python bot.py`

## Frameworks & Libraries

### Telegram
- `python-telegram-bot[job-queue]==20.7` — async bot framework with built-in job scheduling
  - Uses `Application`, `CommandHandler`, `MessageHandler`, `filters`, `ContextTypes`
  - Polling mode (not webhooks)
  - Job queue: `run_repeating` for periodic ClickUp sync every 120s

### AI
- `anthropic==0.25.0` — Anthropic Claude SDK
  - `claude-haiku-4-5-20251001` — fast, cheap, used for simple queries (confidence ≥ 70%)
  - `claude-sonnet-4-6` — high quality, used when Haiku confidence < 70% or for complex escalations
  - Pattern: `Anthropic(api_key=CLAUDE_API_KEY)` — global client instance
- `openai==1.82.0` — OpenAI SDK (only used for Whisper voice transcription via REST)
  - Calls `https://api.openai.com/v1/audio/transcriptions` with `whisper-1` model

### HTTP
- `requests==2.31.0` — synchronous HTTP (used for ClickUp API and Telegram group notifications)
  - **Note:** Called from within async handlers — potential blocking issue in high-load scenarios

### Data
- `pandas==2.1.4` — imported in requirements but NOT used in bot.py (dead dependency)
- `openpyxl==3.1.2` — imported in requirements but NOT used in bot.py (dead dependency)

### Config
- `python-dotenv==1.0.0` — loads `.env` file via `load_dotenv()`

## Configuration

### Environment Variables (all required unless noted)
| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `CLAUDE_API_KEY` | Yes | Anthropic API key |
| `CLICKUP_API_TOKEN` | Yes | ClickUp API token |
| `CLICKUP_LIST_TICKETS_ID` | Yes | ClickUp list ID for support tickets |
| `CLICKUP_LIST_MERCHANTS_ID` | Yes | ClickUp list ID for merchant records |
| `SUPPORT_GROUP_CHAT_ID` | No | Telegram group chat ID for support team notifications |
| `OPENAI_API_KEY` | No | OpenAI key for Whisper transcription (voice disabled if absent) |

### Hardcoded Constants
- `SESSION_TIMEOUT = 600` (10 min) — message grouping window
- `SPAM_LIMIT = 10`, `SPAM_WINDOW = 60` — anti-spam: max 10 msgs/60s
- `FAQ_CACHE_MAX = 200`, `FAQ_CACHE_TTL = 86400` (24h) — FAQ cache
- `NOTIFICATION_CACHE_TTL = 86400` (24h) — dedup cache for ClickUp notifications

## File Structure
```
bot.py                 — entire bot logic (~1280 lines)
clickup_ids.json       — ClickUp custom field ID mapping (reference only, not loaded at runtime)
requirements.txt       — Python dependencies
Dockerfile             — docker build config
README.md              — project readme
CLAUDE.md              — developer notes
```

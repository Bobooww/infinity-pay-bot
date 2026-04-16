# STRUCTURE.md — Infinity Pay Telegram Support Bot

## Directory Layout
```
infinity-pay-bot/
├── bot.py                  — ALL logic (~1280 lines, single file)
├── clickup_ids.json        — ClickUp custom field IDs (reference only, not loaded at runtime)
├── requirements.txt        — Python dependencies
├── Dockerfile              — Docker build config (python:3.11-slim)
├── README.md               — Project readme
├── CLAUDE.md               — Developer notes for Claude Code
└── .planning/              — GSD planning directory (created by this workflow)
    └── codebase/           — This codebase map
```

## bot.py Internal Structure

The file is organized with ASCII banner separators (`# ───...`):

| Lines | Section | Description |
|-------|---------|-------------|
| 1–15 | Module docstring | Features list (in Russian, UTF-8 encoded) |
| 17–30 | Imports | All Python imports |
| 32–136 | Config & State | Env vars, constants, API clients, all in-memory dicts |
| 139–224 | Utility functions | spam check, session management, JSON parsing |
| 227–457 | ClickUp helpers | All ClickUp API functions (synchronous) |
| 460–531 | AI — Haiku/Sonnet | Claude integration, hybrid escalation |
| 534–568 | Voice messages | Whisper transcription |
| 571–892 | Telegram handlers — merchants | `/start`, `/login`, `/logout`, `/stats`, message/voice handlers |
| 895–1091 | Telegram handlers — agents/ISO | Agent message handling, ClickUp task creation |
| 1116–1245 | ClickUp webhook/job | Periodic ticket status polling and merchant notifications |
| 1248–1281 | main() | Handler registration, job queue setup, polling start |

## Key File Locations

| Item | Location |
|------|----------|
| Bot token config | `bot.py:43` — `TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]` |
| ClickUp field IDs | `bot.py:62–70` — `TICKET_FIELDS` dict |
| Support agents list | `bot.py:73–76` — `SUPPORT_AGENTS` list |
| Agent login codes | `bot.py:79–82` — `AGENT_CODES` dict |
| AI system prompt | `bot.py:464–481` — `SYSTEM_PROMPT_TEMPLATE` |
| Agent AI prompt | `bot.py:902–921` — `AGENT_AI_PROMPT` |
| Main state machine | `bot.py:710–892` — `handle_message()` |
| ClickUp sync job | `bot.py:1120–1245` — `check_ticket_updates()` |
| Handler registration | `bot.py:1257–1274` — `main()` |

## Naming Conventions

### Functions
- Async handlers: `async def handle_*(update, context)` — Telegram message handlers
- Sync ClickUp: `def search_*/create_*/add_*` — ClickUp API operations
- Utility: `def is_*/get_*/cleanup_*/parse_*` — helpers

### Variables
- User identity: `tg_id` (Telegram user ID, int)
- Merchant data: `merchant` dict with keys: `task_id, name, mid, phone, email, address, business_type, unique_code, telegram_id`
- AI result: `analysis` dict with keys: `confidence, should_escalate, category, priority, response_to_merchant, escalation_summary`

### Constants
- UPPER_SNAKE_CASE: `TELEGRAM_TOKEN`, `CLICKUP_BASE`, `SESSION_TIMEOUT`, etc.
- Dicts with string keys: `TICKET_FIELDS`, `PRIORITY_MAP`, `PRIORITY_EMOJI`, `AGENT_CODES`

## Language Notes
- **Code:** English (variable names, function names, log messages)
- **UI strings:** Russian (Cyrillic) — messages sent to users
- **Comments:** Russian (Cyrillic) — inline code comments
- **Known issue:** bot.py on GitHub shows double-encoded UTF-8 (mojibake) — cosmetic only, bot works correctly

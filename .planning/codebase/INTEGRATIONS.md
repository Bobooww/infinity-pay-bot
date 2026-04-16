# INTEGRATIONS.md — Infinity Pay Telegram Support Bot

## Telegram Bot API
- **Auth:** Bot token via `TELEGRAM_BOT_TOKEN` env var
- **Mode:** Long polling (`app.run_polling(allowed_updates=Update.ALL_TYPES)`)
- **Group notifications:** Direct REST calls to `https://api.telegram.org/bot{TOKEN}/sendMessage` with `parse_mode: "Markdown"`
- **Handlers registered:**
  - `/start`, `/help`, `/login`, `/logout`, `/stats`, `/close_session` — command handlers
  - `VOICE | AUDIO` — voice message handler
  - `TEXT & ~COMMAND` — text message handler

## Anthropic Claude API
- **Auth:** `CLAUDE_API_KEY` env var → `Anthropic(api_key=...)` global client
- **Models used:**
  - `claude-haiku-4-5-20251001` — primary (merchant queries + agent task parsing)
  - `claude-sonnet-4-6` — fallback (when Haiku confidence < 70%)
- **Call pattern:** `anthropic_client.messages.create(model, max_tokens=512, system, messages)`
- **Response format:** JSON string (with optional ```json ... ``` wrapper) — parsed via `parse_ai_json()`
- **Two prompts:**
  1. `SYSTEM_PROMPT_TEMPLATE` — for merchant support (classification, priority, response)
  2. `AGENT_AI_PROMPT` — for agent/ISO task creation (intent detection, task extraction)

## OpenAI API (Whisper)
- **Auth:** `OPENAI_API_KEY` env var
- **Endpoint:** `POST https://api.openai.com/v1/audio/transcriptions`
- **Model:** `whisper-1`
- **Flow:** Downloads voice file from Telegram → saves to temp `.ogg` file → sends to Whisper → deletes temp file
- **Graceful degradation:** If `OPENAI_API_KEY` is empty, voice messages return a text-only fallback message

## ClickUp API v2
- **Auth:** `CLICKUP_API_TOKEN` env var, sent as `Authorization` header
- **Base URL:** `https://api.clickup.com/api/v2`
- **Lists:**
  - `CLICKUP_LIST_TICKETS_ID` — support ticket list
  - `CLICKUP_LIST_MERCHANTS_ID` — merchant database list

### Endpoints Used
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/list/{id}/task` | Fetch merchants (search by code or TG ID) |
| GET | `/list/{id}/task` | Fetch tickets (check updates, find least-loaded agent) |
| GET | `/task/{id}` | Get merchant task to find Telegram ID field |
| POST | `/task/{id}/field/{field_id}` | Save Telegram ID to merchant record |
| POST | `/list/{id}/task` | Create support ticket |
| POST | `/task/{id}/comment` | Add merchant follow-up message as comment |
| GET | `/task/{id}/comment` | Fetch comments for forwarding support replies to merchant |

### Custom Fields on Tickets
| Field Name | Field ID |
|-----------|---------|
| source | `cce340eb-1ad3-4393-99db-8a4479a4adf8` |
| merchant | `a1748265-3769-4961-8a97-68f4c790b5ee` |
| mid | `6b12ba3e-96a6-4068-9eaa-1cba547558ce` |
| category | `98e62955-2751-45ed-a00a-4d8889e0c09e` |
| priority_level | `aaae7c35-5cbf-4325-be9c-d358b5654ab8` |
| channel | `688d4913-337f-4f97-bada-3653dcee743c` |
| phone | `67b7f5f3-2ebb-4b64-9d3f-f87c0a09b4bb` |

### Merchant Fields Searched
- `Unique Code` — for first-time merchant identification
- `Telegram ID` — for returning merchant lookup
- `MID`, `Phone`, `Email`, `Address`, `Business Type`, `Unique Code`

## No Database / No Persistent Storage
- All state is in-memory Python dicts
- Bot restart clears all sessions, caches, and statistics
- ClickUp serves as the only persistent datastore (merchant records + tickets)

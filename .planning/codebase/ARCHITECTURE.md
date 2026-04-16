# ARCHITECTURE.md — Infinity Pay Telegram Support Bot

## Pattern
**Single-file async monolith** with polling-based event loop. All logic lives in `bot.py`.

```
Telegram (polling) → python-telegram-bot handlers → business logic → ClickUp API + Anthropic API
                                                    ↓
                                               Job queue (every 2 min) → poll ClickUp → notify merchants
```

## Layers

### 1. Configuration Layer (lines 42–136)
Constants, env vars, API clients, global in-memory state dicts. Initialized at module load.

### 2. Utility Layer (lines 142–224)
- `is_spam(tg_id)` — rate limiting check
- `get_session(tg_id)` — session creation/retrieval with 10-min TTL
- `close_session(tg_id)` — resets session state
- `cleanup_notification_cache()` / `cleanup_faq_cache()` — TTL-based eviction
- `parse_ai_json(text)` — strips ```json``` wrapper and parses JSON

### 3. ClickUp Helpers (lines 229–457)
Synchronous `requests`-based functions for all ClickUp API operations:
- `get_least_loaded_agent()` — load balancing across support agents
- `search_merchant_by_code(code)` — paginated search by unique code
- `search_merchant_by_telegram_id(telegram_id)` — paginated search by TG ID
- `extract_merchant_data(task)` — parses ClickUp task into merchant dict
- `save_telegram_id_to_merchant(task_id, telegram_id)` — writes TG ID to ClickUp
- `create_support_ticket(merchant, message, ai_analysis, phone)` — creates ticket + notifies group
- `add_comment_to_ticket(ticket_id, comment)` — appends message to ticket

### 4. AI Layer (lines 464–531)
- `analyze_with_claude(merchant, message, use_sonnet)` — hybrid Haiku → Sonnet classification
  - Returns JSON: `{confidence, should_escalate, category, priority, response_to_merchant, escalation_summary}`
  - Auto-escalates to Sonnet if Haiku confidence < 70%

### 5. Voice Handler (lines 538–568)
- `transcribe_voice(update, context)` — downloads OGG from Telegram, sends to Whisper, returns text

### 6. Merchant Telegram Handlers (lines 574–892)
Async handlers for merchant-facing flows:
- `start(update, context)` — welcome + merchant identification
- `login_command` / `logout_command` — agent/ISO auth
- `stats_command` — bot statistics (agents only)
- `close_session_command` — manual session reset
- `handle_voice(update, context)` — voice → text → handle_message
- `handle_message(update, context)` — main dispatch state machine

### 7. Agent/ISO Telegram Handlers (lines 895–1091)
- `handle_agent_message(update, context, text)` — AI parses agent text → creates ClickUp task
- `_create_clickup_task(agent, task_data, phone)` — agent-facing ticket creation

### 8. Job Queue (lines 1120–1245)
- `check_ticket_updates(context)` — runs every 120s, polls ClickUp for status changes, forwards comments

### 9. Entry Point (lines 1252–1281)
- `main()` — wires all handlers, starts job queue, runs polling

## State Machine (Merchant Flow)

```
[new user] → awaiting_code
    ↓ (valid code)
identified → [message received]
    ↓
awaiting_choice (1=self_help, 2=support)
    ↓ choice=1                  ↓ choice=2
mode="self_help"           awaiting_phone
    ↓                           ↓ (phone or "skip")
AI answers directly         mode="support"
    ↓ user types "2"            ↓
awaiting_phone         ticket created in ClickUp
                            ↓
                        ticket_id set → follow-up messages as comments
                            ↓ (ticket closed)
                        session reset
```

## In-Memory State Dicts

| Dict | Key | Value | Purpose |
|------|-----|-------|---------|
| `user_states` | tg_id | str ("awaiting_code"\|"identified"\|"agent"\|"iso") | User auth state |
| `merchant_cache` | tg_id | merchant dict | Avoid repeat ClickUp lookups |
| `agent_sessions` | tg_id | {role, name, clickup_id, tg_id} | Agent/ISO session |
| `message_sessions` | tg_id | {messages, last_time, ticket_id, awaiting_*, mode} | Merchant conversation session |
| `faq_cache` | question_hash | {answer, hits, last_used} | AI answer cache |
| `notification_cache` | "notified_{task_id}_{status}" | timestamp | Dedup ClickUp notifications |
| `spam_tracker` | tg_id | {count, first_msg} | Rate limiting |
| `pending_agent_tasks` | tg_id | {task_data, created_at} | Agent 2-step task creation |
| `stats` | metric_name | int | Bot statistics |

## Data Flow

### Merchant Support Flow
1. Merchant sends text → `handle_message()`
2. Spam check → state check → session lookup
3. If new: ask choice (self_help / support)
4. Self-help: `analyze_with_claude()` → return AI answer
5. Support: ask phone → `create_support_ticket()` → post to TG group
6. Follow-up messages: `add_comment_to_ticket()`

### ClickUp Sync Flow (every 2 min)
1. `check_ticket_updates()` fetches 20 most-recently-updated tickets
2. Parses Telegram ID from ticket description
3. Checks `notification_cache` for dedup
4. Sends status update to merchant via Telegram
5. Fetches last 3 comments → forwards non-merchant comments to user

## Entry Points
- **`bot.py`** — `main()` → `Application.run_polling()`
- **Docker CMD:** `["python", "bot.py"]`

# CONVENTIONS.md — Infinity Pay Telegram Support Bot

## Code Style

### General
- Python 3.11 with modern type hints in function signatures (`str | None`, `dict | None`)
- `async def` for all Telegram handlers, sync `def` for ClickUp helpers and utilities
- `f-strings` used throughout for string formatting
- Logging via `logger = logging.getLogger(__name__)` — standard Python logging

### Telegram Handlers Pattern
```python
async def handler_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    # ... logic ...
    await update.message.reply_text("message text", parse_mode="Markdown")
```

### ClickUp API Call Pattern
```python
r = requests.get(f"{CLICKUP_BASE}/endpoint", headers=CLICKUP_HEADERS, params={...})
if r.status_code != 200:
    return None
data = r.json()
```

### AI Call Pattern
```python
response = anthropic_client.messages.create(
    model=model,
    max_tokens=512,
    system=system_prompt,
    messages=[{"role": "user", "content": message}]
)
text = response.content[0].text.strip()
result = parse_ai_json(text)
```

## Error Handling
- ClickUp calls: `try/except Exception as e: logger.error(f"...")` with fallback values
- AI calls: JSON parse failures fall back to Sonnet, Sonnet failures return hardcoded safe dict
- Telegram send failures in job queue: silently caught with `except: pass`
- Voice transcription: returns `None` on failure, bot sends user-friendly message

## State Management Patterns

### Session guard pattern
```python
session = get_session(tg_id)
if session.get("ticket_id"):
    # already has ticket — add comment
    return
if session.get("awaiting_phone"):
    # waiting for phone — process it
    return
```

### Cache dedup pattern
```python
cache_key = f"notified_{task_id}_{status_name}"
if cache_key in notification_cache:
    continue
# ... send notification ...
notification_cache[cache_key] = time.time()
```

## Formatting Conventions

### Telegram Messages
- Uses Markdown (`parse_mode="Markdown"`) for most formatted messages
- Emoji used extensively for visual structure: `✅`, `❌`, `⚠️`, `📋`, `🔴`, `🟠`, `🟡`, `🟢`
- Bold with `*text*`, code with `` `text` ``, italic with `_text_`

### Ticket Naming
```python
task_name = f"{emoji} [{category}] {merchant['name']} → {summary[:80]}"
```
- Emoji prefix: 🔴 Urgent, 🟠 High, 🟡 Normal, 🟢 Low
- Format: `{priority_emoji} [{category}] {merchant} → {summary}`

### Log Messages
- Russian Cyrillic in all log messages (same encoding issue as comments)
- Pattern: `logger.info(f"Context: {value}")`, `logger.error(f"Error description: {e}")`

## Configuration Pattern
All configuration at module top level as globals:
```python
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]     # raises KeyError if missing
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # optional, defaults to ""
```

## Anti-patterns Present in Codebase
1. **Synchronous HTTP in async handlers** — `requests.get/post` blocks the event loop
2. **Bare `except: pass`** — silently swallows errors in comment forwarding (lines 1241–1242)
3. **Dead dependencies** — `pandas` and `openpyxl` in requirements.txt but unused
4. **ClickUp search is O(n)** — full list scan on every merchant lookup, no index
5. **No input validation** — phone numbers accepted as-is without format validation

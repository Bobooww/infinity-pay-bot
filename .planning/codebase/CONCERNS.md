# CONCERNS.md — Infinity Pay Telegram Support Bot

## 🔴 Critical Bugs

### 1. Typo: `messagsage` — Runtime NameError
**Location:** `bot.py:500`
```python
messages=[{"role": "user", "content": messagsage}]  # NameError!
```
Variable `messagsage` does not exist — the correct name is `message`. This will crash `analyze_with_claude()` on every call, causing all AI analysis to fail and fall through to the Sonnet fallback... which has the same bug. The bot will always return the hardcoded fallback response.

**Fix:** Rename `messagsage` → `message` on line 500.

### 2. Synchronous HTTP in Async Handlers
**Location:** All ClickUp helper functions called from async handlers
`requests.get/post` is synchronous and blocks the entire async event loop. Under any concurrent load, one slow ClickUp API call stalls all Telegram message processing.

**Fix:** Replace `requests` with `httpx` async client or `aiohttp` for ClickUp calls.

## 🟠 High Severity

### 3. No Persistent Storage
All state (`user_states`, `merchant_cache`, `agent_sessions`, `message_sessions`, `faq_cache`, `notification_cache`, `spam_tracker`, `stats`) lives in memory. A bot restart or Railway redeploy:
- Clears all active merchant sessions mid-conversation
- Loses all FAQ cache (cold start)
- Loses all statistics
- Loses notification dedup cache (duplicate notifications risk)

**Impact:** Railway restarts happen on every push to `main`. Merchants mid-conversation lose context.

### 4. Agent Secret Codes Hardcoded in Source
**Location:** `bot.py:79–82`
```python
AGENT_CODES = {
    "IAMAGENT": {"role": "agent", ...},
    "ISO-MASTER": {"role": "iso", "name": "Shams (ISO Owner)", ...},
}
```
Secret login codes are in source code, committed to git. Anyone with repo access can log in as an agent or ISO owner.

**Fix:** Move to environment variables: `AGENT_CODE_1`, `ISO_CODE`, etc.

### 5. ClickUp Merchant Search is O(n) — Full Table Scan
**Location:** `bot.py:260–309`
Every message from an unrecognized user triggers a full paginated scan of the merchants list (100 records/page). On a large merchant list, this adds significant latency and ClickUp API rate limit risk.

**Fix:** Maintain a TG ID → merchant mapping in Redis or a simple JSON file with periodic sync.

### 6. Fragile Telegram ID Extraction from Ticket
**Location:** `bot.py:1160–1165`
```python
tg_part = desc.split("Telegram ID:** ")[1].split("\n")[0].strip()
```
This string-parsing approach breaks if ticket descriptions are formatted differently or if `**` Markdown isn't present. Silently fails (no notification to merchant).

**Fix:** Store Telegram ID in a ClickUp custom field on tickets, not embedded in description text.

## 🟡 Medium Severity

### 7. Dead Dependencies
`pandas==2.1.4` and `openpyxl==3.1.2` are in `requirements.txt` but never imported in `bot.py`. These add ~50MB to the Docker image and unnecessary install time.

### 8. Bare `except: pass` in Comment Forwarding
**Location:** `bot.py:1241–1242`
```python
except:
    pass
```
Silently swallows all errors in the comment forwarding loop. Merchant never receives support team replies if any error occurs here.

### 9. Double-Encoded UTF-8 on GitHub
Cyrillic text in `bot.py` appears as mojibake in GitHub's web editor. Not a runtime issue but makes code hard to review/edit on GitHub, increasing risk of introducing syntax errors during quick edits.

### 10. ClickUp Polling Fetches Only 20 Tickets
**Location:** `bot.py:1152`
```python
for task in tasks[:20]:
```
If more than 20 tickets are updated between polling cycles (2-min interval), older updates are missed and merchants never get notified.

## 🟢 Low Severity

### 11. No Input Sanitization on Phone Numbers
Phone numbers are accepted as-is from users and stored in ClickUp without format validation or sanitization.

### 12. `pending_agent_tasks` Cleanup Only in Job Queue
Agent 2-step task flows that are abandoned (user never responds with phone) sit in `pending_agent_tasks` for 30 min. A dedicated timeout per-step would be cleaner.

### 13. Support Agent Load Balancing Has a Race Condition
Two near-simultaneous tickets could both query agent loads before either ticket is created, resulting in both being assigned to the same (apparently least-loaded) agent.

### 14. No Rate Limiting on ClickUp API Calls
The bot makes multiple synchronous ClickUp API calls per message with no retry logic, backoff, or rate limit handling. ClickUp API returns 429 on rate limit — currently unhandled.

## Known Non-Issues (from CLAUDE.md)
- Double-encoded UTF-8 Cyrillic in bot.py on GitHub — cosmetic only, runtime fine
- In-memory state loss on restart — acknowledged limitation

# ROADMAP.md — Infinity Pay Support Bot

**3 phases** | **15 requirements** | All v1 requirements covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|-----------------|
| 1 | Fix & Secure | Bot works correctly and is safe | BUG-01, BUG-02, BUG-03, SEC-01, SEC-02, CLEAN-01 | 4 |
| 2 | Persist & Speed | No data lost on restart, fast responses | STORE-01, STORE-02, STORE-03, PERF-01 | 3 |
| 3 | Clover Integration | Merchants get live Clover data via bot | CLOVER-01, CLOVER-02, CLOVER-03, CLOVER-04, CLOVER-05 | 4 |

---

## Phase 1: Fix & Secure

**Goal:** Bot correctly runs AI on every message and agent codes are not in source code.

**Requirements:** BUG-01, BUG-02, BUG-03, SEC-01, SEC-02, CLEAN-01

**Plans:**
1. Fix `messagsage` typo (`bot.py:500`) — one-line fix, critical
2. Replace `requests` with `httpx` async for all ClickUp + Telegram group calls
3. Move agent secret codes to env vars (`AGENT_CODE_AGENT`, `AGENT_CODE_ISO`)
4. Store merchant TG ID in ClickUp custom field on tickets (already done on merchants, need on tickets)
5. Remove `pandas` and `openpyxl` from `requirements.txt`

**Success Criteria:**
1. Merchant sends a message → AI (Haiku) actually responds with classified JSON, not hardcoded fallback
2. `/login IAMAGENT` still works after secret is moved to env var
3. `requirements.txt` has 5 deps (not 7) — pandas and openpyxl gone
4. ClickUp API calls are async (no `import requests` in async functions)

---

## Phase 2: Persist & Speed

**Goal:** Bot survives Railway restarts without losing merchant sessions or sending duplicate notifications.

**Requirements:** STORE-01, STORE-02, STORE-03, PERF-01

**Plans:**
1. Add JSON-file persistence layer (`data/state.json`) — merchant cache, sessions, notification cache
2. Load state on startup, save after every write
3. Implement merchant lookup: memory → JSON file → ClickUp (only on cache miss)
4. Auto-save on graceful shutdown (SIGTERM handler)

**Success Criteria:**
1. Bot restarts → previously identified merchants are still identified (no re-enter code)
2. Notifications don't duplicate after Railway redeploy
3. Merchant mid-conversation → bot restarts → merchant can continue (session restored)

---

## Phase 3: Clover Integration

**Goal:** Merchants can ask "какие продажи сегодня?" and get live Clover data.

**Requirements:** CLOVER-01, CLOVER-02, CLOVER-03, CLOVER-04, CLOVER-05

**Plans:**
1. Add Clover API helper module (get sales, get last order, toggle menu item)
2. Add `clover_merchant_id` and `clover_access_token` fields to merchant data (from ClickUp)
3. Extend AI prompt to classify Clover intents: `sales_query`, `order_query`, `menu_change`
4. Route Clover intents to API calls before falling back to ClickUp ticket
5. Format and send Clover responses in clean Russian/English

**Success Criteria:**
1. Merchant asks "какие продажи сегодня" → bot replies with today's net sales figure from Clover
2. Merchant asks "последний заказ" → bot shows last order details
3. Agent sends "выключи [item] у [merchant]" → item disabled on Clover + confirmation sent
4. Merchants without Clover credentials → graceful fallback to regular support flow

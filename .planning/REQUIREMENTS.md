# REQUIREMENTS.md — Infinity Pay Support Bot

## v1 Requirements

### Bug Fixes (Critical)
- [ ] **BUG-01**: Fix `messagsage` typo in `bot.py:500` so AI actually runs on every message
- [ ] **BUG-02**: Replace synchronous `requests` calls in async handlers with `httpx` async client to prevent event loop blocking
- [ ] **BUG-03**: Replace fragile string-based Telegram ID extraction from ticket description with ClickUp custom field lookup

### Security
- [ ] **SEC-01**: Move hardcoded agent secret codes (`IAMAGENT`, `ISO-MASTER`) from source code to environment variables
- [ ] **SEC-02**: Add Telegram ID as a proper custom field on tickets (not embedded in description text)

### Persistence
- [ ] **STORE-01**: Cache merchant data (name, MID, TG ID) in a JSON file so ClickUp isn't scanned on every message
- [ ] **STORE-02**: Persist notification dedup cache to file so duplicate notifications don't fire after restart
- [ ] **STORE-03**: Persist active merchant sessions to file so mерчант doesn't lose context when Railway redeploys

### Performance
- [ ] **PERF-01**: Reduce ClickUp API calls — merchant lookup should hit cache first, ClickUp only on cache miss
- [ ] **CLEAN-01**: Remove unused `pandas` and `openpyxl` from `requirements.txt`

### Clover API Integration
- [ ] **CLOVER-01**: Bot can fetch and display today's net sales for a merchant from Clover API
- [ ] **CLOVER-02**: Bot can fetch and display last order details from Clover API
- [ ] **CLOVER-03**: Agent/ISO can enable or disable a menu item on merchant's Clover via bot command
- [ ] **CLOVER-04**: AI routing — when merchant asks about sales/orders/menu, bot detects intent and calls Clover API instead of (or before) creating a ClickUp ticket
- [ ] **CLOVER-05**: Each merchant's Clover `merchant_id` and `access_token` stored in ClickUp merchant record custom field

## v2 Requirements (Deferred)
- ClickUp webhooks instead of polling (complex infra, polling works fine for now)
- WhatsApp integration (needs Meta business verification)
- MPA form automation (separate project)
- Full PostgreSQL database (overkill for 152 merchants)
- Automated testing suite
- Admin dashboard

## Out of Scope
- Node.js rewrite — Python bot works, no value in rewriting
- Multiple bot instances / load balancing — single instance on Railway is sufficient
- Custom ClickUp webhook server — adds infra complexity without proportional benefit

## Traceability

| Requirement | Phase |
|-------------|-------|
| BUG-01, BUG-02, BUG-03 | Phase 1 |
| SEC-01, SEC-02 | Phase 1 |
| CLEAN-01 | Phase 1 |
| STORE-01, STORE-02, STORE-03, PERF-01 | Phase 2 |
| CLOVER-01, CLOVER-02, CLOVER-03, CLOVER-04, CLOVER-05 | Phase 3 |

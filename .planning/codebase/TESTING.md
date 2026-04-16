# TESTING.md — Infinity Pay Telegram Support Bot

## Current State
**No tests exist.** The project has zero test files, no test framework configured, and no CI pipeline beyond Railway's auto-deploy on push to `main`.

## Testing Infrastructure
- No `pytest`, `unittest`, or any test framework in `requirements.txt`
- No `tests/` directory
- No `.github/workflows/` CI config
- No `Makefile` or test scripts

## Deployment as "Testing"
The current workflow is effectively **deploy-and-observe**:
1. Push to `main` → Railway auto-deploys
2. Check Railway deploy logs for syntax errors / startup crashes
3. Manual testing via the actual Telegram bot

## Risk Areas Without Tests

### Critical paths with no coverage
- `analyze_with_claude()` — hybrid Haiku→Sonnet logic, JSON parsing, category validation
- `handle_message()` — 150-line state machine with multiple branches
- `create_support_ticket()` — ClickUp ticket creation with custom fields
- `check_ticket_updates()` — ClickUp polling + notification dedup logic
- `parse_ai_json()` — strips markdown code fences before JSON parse

### Known fragile behaviors
- AI response JSON parsing (`parse_ai_json`) — if Claude returns unexpected format, falls back to Sonnet
- Merchant search — paginated ClickUp scan, stops when `len(tasks) < 100`
- Telegram ID extraction from ticket description — fragile string parsing: `desc.split("Telegram ID:** ")[1].split("\n")[0]`

## Testing Approach (Recommended for Future)
- `pytest` + `pytest-asyncio` for async handler tests
- `unittest.mock` to mock `anthropic_client`, `requests`, and `context.bot`
- Integration tests would require ClickUp sandbox list IDs
- Minimum viable test: unit test `parse_ai_json()`, `is_spam()`, `get_session()`, `analyze_with_claude()` with mocked Anthropic client

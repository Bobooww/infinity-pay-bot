# PROJECT.md — Infinity Pay Support Bot

## What This Is

Telegram-бот для поддержки 152 мерчантов Infinity Pay Inc. Мерчанты пишут вопросы/проблемы → Claude AI отвечает сам или создаёт задачу в ClickUp → команда обрабатывает → ответ идёт обратно мерчанту. Агенты/ISO также используют бота для создания внутренних задач голосом/текстом.

**Core Value:** Мерчант получает ответ или тикет за секунды, без звонков. Команда видит все запросы в ClickUp.

## Context

- **Owner:** Shams Rozikov (ISO Owner, Infinity Pay Inc.)
- **Users:** 152 мерчанта (русскоязычные рестораны в США) + агенты поддержки
- **Deploy:** Railway (auto-deploy с GitHub main)
- **Language stack:** Python 3.11, python-telegram-bot 20.7, Anthropic Claude, ClickUp API v2
- **Bot handle:** @InfinityPaySupportBot

## Current State (Brownfield)

### ✅ Что работает
- Идентификация мерчантов по коду или Telegram ID
- Сессии с 10-мин таймаутом (группировка сообщений в один тикет)
- Создание тикетов в ClickUp с custom fields
- Дублирование тикетов в Telegram группу поддержки
- Агент/ISO логин через секретный код
- AI-создание задач агентами (intent detection → ClickUp task)
- Голосовые сообщения (Whisper API)
- Поллинг ClickUp каждые 2 мин → уведомления мерчантам

### 🔴 Критически сломано
- **`messagsage` typo** (`bot.py:500`) — бот НИКОГДА не запускает AI, всегда возвращает заглушку

### 🟠 Проблемы
- Synchronous HTTP в async handlers (блокирует event loop)
- Всё состояние в памяти — перезапуск стирает сессии (Railway деплоит на каждый пуш)
- Секретные коды агентов захардкожены в исходнике
- ClickUp merchant search O(n) — полный скан на каждое сообщение
- TG ID хранится в тексте описания тикета (хрупкий парсинг)

## Goals (Finish Line)

1. **Бот работает правильно** — AI реально анализирует запросы, приоритеты и категории корректны
2. **Стабильность** — перезапуск не ломает активные разговоры с мерчантами
3. **Clover API** — мерчант может спросить "какие продажи сегодня?" и получить ответ
4. **Безопасность** — секретные коды в env vars, не в коде
5. **Производительность** — async HTTP, кэш мерчантов

## Requirements

### Validated (already exists)
- ✓ Merchant identification by unique code or Telegram ID — existing
- ✓ Session grouping (10 min timeout) — existing
- ✓ Claude AI classification (Haiku→Sonnet hybrid) — existing (broken by bug)
- ✓ ClickUp ticket creation with custom fields — existing
- ✓ TG support group notification on new ticket — existing
- ✓ Agent/ISO login — existing
- ✓ Voice message transcription (Whisper) — existing
- ✓ ClickUp status polling → merchant notifications — existing
- ✓ Comment forwarding (ClickUp → merchant Telegram) — existing

### Active
- [ ] **BUG-01**: Fix `messagsage` typo in `analyze_with_claude()` — AI completely broken
- [ ] **BUG-02**: Fix sync HTTP in async handlers — use `httpx` async client
- [ ] **STORE-01**: Persist merchant cache to avoid O(n) scans on every message
- [ ] **STORE-02**: Persist notification dedup cache — survive restarts
- [ ] **STORE-03**: Persist active sessions — mерчант не теряет контекст после Railway deploy
- [ ] **SEC-01**: Move agent secret codes to environment variables
- [ ] **SEC-02**: Store merchant Telegram ID in ClickUp custom field (not in description text)
- [ ] **CLOVER-01**: Clover API — fetch today's sales for a merchant
- [ ] **CLOVER-02**: Clover API — fetch last order
- [ ] **CLOVER-03**: Clover API — enable/disable menu item
- [ ] **CLOVER-04**: AI routing — detect Clover-related queries and respond with live data
- [ ] **PERF-01**: Merchant lookup cache (in-memory with TTL) to reduce ClickUp API calls
- [ ] **CLEAN-01**: Remove unused `pandas` and `openpyxl` from requirements.txt

### Out of Scope
- PostgreSQL / full database — overkill for current scale, Redis/JSON file sufficient
- Node.js rewrite — Python implementation is fine, no need to rewrite
- ClickUp webhooks — polling every 2 min is acceptable, webhooks add infra complexity
- WhatsApp integration — pending Meta verification, future milestone
- MPA form automation — separate project

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep Python (not rewrite to Node.js) | Bot works, rewrite wastes time | — Confirmed |
| Persistent storage = JSON file + Redis optional | Railway free tier, simple ops | — Pending |
| Async HTTP = httpx | Drop-in replacement for requests in async context | — Pending |
| Clover API = direct REST calls | No extra libs needed | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

---
*Last updated: 2026-04-16 after initialization*

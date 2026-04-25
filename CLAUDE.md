# CLAUDE.md — Infinity Pay Telegram Support Bot

## ⚠️ ВАЖНО: ЭТОТ БОТ DEPRECATED (2026-04-24)

`bot.py` — **legacy** Python implementation. Сейчас активный бот — это **`infinity-pay-dashboard`** (Node.js, webhook mode).

**Активный бот:**
- Repo: `~/Documents/brain/infinity-pay-dashboard/`
- Endpoint: `https://infinity-pay-dashboard-production.up.railway.app/bot/webhook`
- Архитектура: Claude tool-use (12 tools), conversation history в Postgres, multimodal (фото)
- Файлы: `src/bot/agent.js` (merchant), `src/bot/webhook.js` (роутинг), `src/bot/tools.js` (Clover tools)

**Этот сервис (`infinity-pay-bot`) на Railway остановлен** чтобы не было webhook conflicts.

Если когда-нибудь нужно будет вернуть `bot.py` в работу:
1. Удалить webhook у бота: `curl https://api.telegram.org/bot<TOKEN>/deleteWebhook`
2. Запустить `bot.py` (polling вернётся в работу)
3. **НО:** дашборд тогда не будет получать сообщения. Можно использовать только один из двух одновременно.

---

## Project Overview (legacy)

Infinity Pay Telegram Support Bot v2 — оригинальный Python implementation бота.
Использовался до перехода на Node.js дашборд с Claude tool-use архитектурой.

## Tech Stack
- **Language:** Python 3.11
- **Telegram:** python-telegram-bot 20.7 (polling mode)
- **AI:** Anthropic Claude (Haiku + Sonnet hybrid)
- **Task management:** ClickUp API v2
- **Voice:** OpenAI Whisper

## Структура файлов
```
bot.py              — main bot file (~3500 lines)
clickup_ids.json    — ClickUp custom field IDs
requirements.txt    — Python dependencies
Dockerfile          — Docker container config
README.md           — project README
CLAUDE.md           — this file
launch/             — launch documentation pack (актуально)
mockups/            — visual prototype mockups (актуально)
```

## Что осталось актуальным

**В этом repo:**
- `launch/` — все launch-материалы (broadcasts, training, scripts, business cards)
- `mockups/` — кликабельный визуальный прототип дашборда

Эти артефакты независимы от bot.py и используются как-есть.

## История изменений

- **2026-04-24** — bot.py deprecated, дашборд стал live. Сервис остановлен на Railway.
- **2026-04-24** — Apr 17 (мой апгрейд): добавил intelligent intent routing, 30-day memory persistence. **Никогда не дошло до прода** — webhook был на дашборде.
- **2026-04-19** — Dashboard security hardening + UI completion
- **2026-04-18** — Long-term merchant memory architecture
- **2026-04-15** — Initial Python bot build

## Если нужно что-то улучшить в боте

**Не редактируй bot.py** — он не запущен. Иди в `infinity-pay-dashboard/src/bot/`:
- `agent.js` — главная логика merchant agent
- `webhook.js` — entry point, role routing
- `tools.js` — Clover tools (sales, menu, terminals)
- `agentTools.js` — tools для саппорт-агентов
- `systemPrompts.js` — промпты для разных ролей
- `guardian.js` — anti-spam, daily limits, fragmentation detection

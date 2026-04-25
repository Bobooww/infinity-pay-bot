# 📊 Production state snapshot — 2026-04-25 03:00 UTC

> Snapshot из боевой БД дашборда. Что РЕАЛЬНО есть прямо сейчас.

---

## 🏪 Мерчанты

| Метрика | Значение |
|---|---|
| **Всего записей** | **153** |
| Активных (`is_active=true`) | 151 |
| С INF-XXXX кодом | 153 ✅ (все) |
| **Подключено через Telegram** | **1** ⚠️ (только тестовый, нужна рассылка) |
| Подключено к Clover (имеют OAuth token) | 1 (тестовый) |
| `preferred_language='en'` для всех | 153 ⚠️ (поле не заполнено по реальным языкам) |

**Что это значит:**
- Мерчанты в БД, готовы получать сообщения
- Но **никто из них пока не нажал /start INF-XXXX** в боте
- Нужна массовая рассылка приветствия (см. `MERCHANT_BROADCAST.md`)

---

## 👥 Команда

| Email | Роль | 2FA | Последний вход |
|---|---|---|---|
| `rozikov.shams@gmail.com` | owner | ❌ | 2026-04-19 |
| `daler@infinitypay.us` | owner | ❌ | 2026-04-19 |
| `laziza@infinitypay.us` | admin | ❌ | **never** |
| `support1@infinitypay.us` | agent | ❌ | 2026-04-19 |
| `support2@infinitypay.us` | agent | ❌ | **never** |

**Что это значит:**
- 3 из 5 уже логинились (Shams, Daler, support1)
- 2 из 5 не заходили вообще (Laziza, support2) — **критично, нужно сегодня**
- Никто не включил 2FA — **security gap**

**Action:** разошли всем `TempPass123!` + ссылку на `TEAM_QUICKSTART.md`. Без 2FA нельзя запускать.

---

## 🎫 Тикеты

| Статус | Кол-во |
|---|---|
| open | 1 |
| resolved | 1 |

Тестовые. Перед боевым запуском удалить.

---

## 🤖 Бот / Дашборд / API

| Сервис | Статус | Где |
|---|---|---|
| Dashboard `/health` | ✅ 200 OK | https://infinity-pay-dashboard-production.up.railway.app |
| Telegram webhook | ✅ 0 pending, 0 errors | `/bot/webhook` |
| Bot identity | ✅ @Infinitypaysupport_bot | id 8602300782 |
| Old `bot.py` сервис | 🛑 stopped | `infinity-pay-bot` Railway project |
| Health monitor (cron) | ✅ запущен | каждые 15 мин на твоём Mac (launchd) |

---

## 🔌 Clover API

| Что | Значение | Статус |
|---|---|---|
| `CLOVER_ENV` | `production` | настроено |
| `CLOVER_APP_ID` | `WJXR55ASP5PKJ` | настроено |
| `CLOVER_APP_SECRET` | (encrypted) | настроено |
| OAuth callback | `${APP_URL}/api/clover/oauth/callback` | работает |
| Production verification | **⏳ ждём от Clover** | 2-4 недели обычно |

**Что это значит:**
- Код готов, ждёт только верификацию от Clover
- См. `launch/CLOVER_API_GUIDE.md` — как ускорить, что подготовить, типичные ошибки

---

## 📧 Email (Resend)

```
RESEND_API_KEY = re_xxxxxxxxxxxxxxxxxxxx   ⚠️ placeholder
```

**Без реального ключа** — пароль-ресет email не работает. Если Laziza или support2 забудут пароль — нет способа им сбросить, кроме как Shams вручную через БД.

**Action:** https://resend.com → register → create API key → положить в Railway.

---

## 🌐 Custom Domain

```
APP_URL = https://infinity-pay-dashboard-production.up.railway.app
```

`support.infinitypay.us` пока не настроен. Не блокер, но хочется красивый URL для визиток / рассылок.

**Action:** DNS CNAME `support` → `5356kgjh.up.railway.app` у регистратора.

---

## 🚦 Готовность к запуску

```
Инфраструктура (бот/дашборд/БД/АИ):  ████████████████████░  98%
Мерчанты в БД:                       ████████████████████░  98%
Мерчанты в боте (нажали /start):     ░░░░░░░░░░░░░░░░░░░░   1%
Команда обучена + 2FA:               ████░░░░░░░░░░░░░░░░  20%
Resend / DNS / Clover prod:          ░░░░░░░░░░░░░░░░░░░░   0%
```

**Total launch readiness: ~50%**

Технически всё работает. Не работает — операционка (раздача паролей, рассылка мерчантам, DNS, Resend).

---

## 🎯 5 действий для запуска (по приоритету)

1. **Разослать пароли команде сегодня** (15 минут твоего времени)
   ```
   Daler / Laziza / support1 / support2 → email + TempPass123! + ссылка на TEAM_QUICKSTART.md
   ```

2. **Resend API key** (10 минут)
   ```
   https://resend.com → Create API Key
   railway variables --set RESEND_API_KEY=re_xxx --service infinity-pay-dashboard
   ```

3. **DNS CNAME** (5 минут + 24ч пропагация)
   ```
   support.infinitypay.us  →  5356kgjh.up.railway.app
   ```

4. **Прогнать E2E тесты** (1 час) — `launch/E2E_TEST_PLAN.md`

5. **Рассылка мерчантам** через owner-bot:
   - Открой `@Infinitypaysupport_bot` в личке
   - Напиши: "Отправь приветствие на русском первым 30 мерчантам, по 1 каждые 6 секунд"
   - Бот покажет список, попросит подтвердить
   - Через час 30 мерчантов получили приветствие — мониторь openness rate

После этих 5 действий — **продукт запущен**.

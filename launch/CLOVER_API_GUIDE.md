# 🔌 Clover API — что нужно знать

> Для тебя, Shams — пока разбираешься с API доступом и верификацией.
> Что уже настроено в дашборде и что от Clover зависит.

---

## 📊 Текущее состояние

```
CLOVER_ENV       = production
CLOVER_APP_ID    = WJXR55ASP5PKJ
CLOVER_APP_SECRET = a3833a2b-f0ec-b376-24dc-...  (в Railway, зашифрован)
APP_URL          = https://infinity-pay-dashboard-production.up.railway.app
```

OAuth callback: `${APP_URL}/api/clover/oauth/callback` — уже работает в коде, ждёт реальных мерчантов.

---

## 🌐 Что нужно от Clover чтобы заработал live merchant

Clover различает **два уровня доступа**:

### Уровень 1: Sandbox (есть у всех с момента регистрации)
- `https://sandbox.dev.clover.com`
- Можно создавать тестовых мерчантов в Clover dashboard
- OAuth работает, но только с sandbox-мерчантами
- API возвращает фейковые транзакции
- **Зачем:** прокликать end-to-end перед prod

### Уровень 2: Production (нужна верификация)
- `https://api.clover.com`
- Можно подключать **реальных** Clover-мерчантов
- Их реальные транзакции / меню / устройства
- Требует:
  1. **App Approval** (review приложения от Clover)
  2. **Business verification** (юридическая инфа Infinity Pay)
  3. **Compliance review** (PCI / data handling)

---

## 🚦 Как проверить статус твоего приложения

Заходишь в **https://www.clover.com/developer-home**:

1. Login → твой dev account (тот же Gmail)
2. Apps → выбираешь Infinity Pay
3. **Settings → Status:**
   - 🟡 *In Review* — ждёшь, обычно 2-4 недели
   - 🟢 *Approved* — можно деплоить prod
   - 🔴 *Rejected* — есть feedback, надо исправить

4. **Permissions → проверь scopes которые ты запросил:**
   - `READ_MERCHANT` ✅ нужен — базовая инфа
   - `READ_PAYMENTS` ✅ нужен — транзакции
   - `WRITE_INVENTORY` ✅ нужен — менять меню (sold out / prices)
   - `READ_INVENTORY` ✅ нужен — список меню
   - `READ_EMPLOYEES` ✅ нужен — сотрудники
   - `READ_ORDERS` ✅ нужен — заказы

   Если каких-то нет — заявка не пройдёт verification потому что нашему боту они нужны.

---

## 🛠 Как ускорить verification

### Что точно нужно подготовить перед review

- **Privacy Policy URL** — `https://infinitypay.us/privacy` (если нет — создай)
- **Terms of Service URL** — `https://infinitypay.us/terms`
- **Support email** — `support@infinitypay.us`
- **Demo video** — 2 минуты — как мерчант подключается, бот отвечает на вопросы, ты как ISO видишь дашборд
- **Description приложения** — что делает, почему нужно мерчанту

### Что Clover проверяет

1. **Что приложение делает то что заявлено** (smoke test их инженером)
2. **Что данные мерчанта не утекают в третьи стороны** (мы храним токены зашифрованные, ✅)
3. **Что есть UI для disconnect** (мы показываем "Disconnect Clover" в дашборде, ✅)
4. **Что privacy policy объясняет какие данные собираются** (нужна страница на твоём сайте)

### Если застрянешь

Email: **app-review@clover.com** или **developer-relations@clover.com**

Шаблон письма:
```
Subject: App Review Status — Infinity Pay (App ID: WJXR55ASP5PKJ)

Hi Clover team,

Submitted our app for review on [date]. We're an ISO with 152 active
merchants ready to onboard. Could you provide an ETA or any feedback
we need to address?

Happy to provide additional documentation or jump on a call.

Thanks,
Shams Rozikov
Co-founder, Infinity Pay Inc.
```

---

## 🔄 Когда Clover одобрит — что делать

Ничего не нужно менять в коде! Уже готово:

```bash
# В Railway dashboard project уже:
CLOVER_ENV=production
CLOVER_APP_ID=WJXR55ASP5PKJ
CLOVER_APP_SECRET=...
```

После одобрения:
1. Открываешь дашборд → Merchants → выбираешь любого реального мерчанта
2. Нажимаешь `Connect Clover`
3. Открывается OAuth страница Clover
4. Owner мерчанта логинится своим Clover аккаунтом → жмёт Approve
5. Token приходит в callback → шифруется → сохраняется в `merchants.clover_access_token`
6. Бот теперь может ходить в Clover за реальными данными этого мерчанта

---

## 🧪 Как протестировать пока ждёшь prod

### Вариант 1: Sandbox

Создай новый sandbox app:
1. https://www.clover.com/developer-home
2. Apps → Create New App
3. **Назови `Infinity Pay Sandbox`**
4. Скопируй sandbox `App ID` и `Secret`
5. В Railway создай **отдельный environment** (preview):
   - `CLOVER_ENV=sandbox`
   - `CLOVER_APP_ID=<sandbox app id>`
   - `CLOVER_APP_SECRET=<sandbox secret>`
6. Создай тестового мерчанта на https://sandbox.dev.clover.com
7. Подключай его через OAuth — это работает без верификации
8. Проверь что бот может читать его меню / sales

### Вариант 2: Подождать

Все остальные фичи бота работают **без Clover** прямо сейчас:
- Создание тикетов
- Эскалация саппорту
- Conversation history
- Multi-language
- Голосовые
- Multimodal (фото)

Можно запустить рассылку 152 мерчантам прямо сейчас — Clover-фичи активируются позже когда придёт верификация.

---

## 📋 Tools которые бот использует через Clover API

(`infinity-pay-dashboard/src/bot/tools.js`):

| Tool | Что делает | Нужен scope |
|---|---|---|
| `get_sales` | Продажи за сегодня / период | `READ_PAYMENTS` |
| `get_top_items` | Топ блюд по выручке | `READ_PAYMENTS`, `READ_ORDERS` |
| `get_last_order` | Последний заказ | `READ_ORDERS` |
| `disable_item` | "Sold out" — выключить блюдо | `WRITE_INVENTORY` |
| `enable_item` | Вернуть в меню | `WRITE_INVENTORY` |
| `change_price` | Изменить цену блюда | `WRITE_INVENTORY` |
| `add_item` | Добавить блюдо в меню | `WRITE_INVENTORY` |
| `list_items` | Список блюд | `READ_INVENTORY` |
| `get_devices_status` | Какие терминалы онлайн | `READ_MERCHANT` |
| `list_employees` | Кассиры | `READ_EMPLOYEES` |
| `lookup_clover_help` | KB поиск | (без scope) |
| `escalate_to_support` | Эскалация на агента | (без scope) |

Если какой-то scope в твоём app не запрошен — соответствующий tool у бота не работает.

---

## 🔍 Quick health check Clover API

Когда подключишь хотя бы одного реального мерчанта, проверь:

```bash
# В Railway shell или локально с DATABASE_URL
psql $DATABASE_URL -c "SELECT business_name, mid, clover_merchant_id IS NOT NULL as connected FROM merchants WHERE clover_access_token IS NOT NULL;"

# Дашборд показывает live данные?
curl https://infinity-pay-dashboard-production.up.railway.app/api/merchants/<id>/clover-status
```

Если `connected = true` но `clover-status` возвращает `error` — токен невалидный, мерчанту надо переподключиться.

---

## 🆘 Типичные ошибки от Clover API

| Ошибка | Что значит | Что делать |
|---|---|---|
| `401 Unauthorized` | Token expired or revoked | Мерчант должен переподключить через дашборд |
| `403 Forbidden` | Нет нужного scope в твоём app | Запросить scope в developer-home → переотдать app на review |
| `404 Not Found` | MID не существует или у тебя нет доступа | Проверь что mid правильный + scope `READ_MERCHANT` есть |
| `429 Too Many Requests` | Rate limit (Clover: 1000 req/min на app) | У нас далеко до этого, но если упрёшься — добавить кеш |
| `500 Internal Server Error` | Clover упал | Попробовать через 5 минут |

---

## 📞 Контакты Clover

| Что | Куда |
|---|---|
| App review status | app-review@clover.com |
| Developer support | developer-relations@clover.com |
| Sales (для merchant onboarding) | sales@clover.com |
| Sandbox login | https://sandbox.dev.clover.com |
| Production login | https://www.clover.com |
| Developer home | https://www.clover.com/developer-home |
| API docs | https://docs.clover.com/reference |

---

## 💡 Если хочешь понять глубже

**Чтение:**
- [Clover OAuth Flow](https://docs.clover.com/docs/oauth)
- [Clover REST API Reference](https://docs.clover.com/reference)
- [Webhooks](https://docs.clover.com/docs/webhooks) — мы пока не используем, но мог бы для real-time updates

**Локально потестить:**
```bash
cd ~/Documents/brain/infinity-pay-dashboard
npm install
# В .env положи sandbox creds
npm run dev
# Открыть http://localhost:3000 → Connect Clover → OAuth flow
```

---

Если застрянешь на конкретном шаге — пиши, помогу дебажить.

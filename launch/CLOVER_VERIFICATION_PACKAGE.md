# 📦 Clover Production Verification — submission package

> Готовый материал чтобы заявка Clover прошла **с первого раза**, а не вернули на доработку.
> Открой https://www.clover.com/developer-home → выбери своё приложение → заполни форму используя текст ниже.

---

## 🎯 Что Clover проверяет (5 критериев)

1. **Description** — что приложение делает, для кого
2. **Privacy Policy URL** — публичная страница на сайте
3. **Terms of Service URL** — публичная страница на сайте
4. **Demo / video walkthrough** — 2-минутное видео как работает
5. **Permissions justification** — зачем тебе каждый scope

Если все 5 заполнены **профессионально и по делу** — review проходит за 1-2 недели.
Если что-то халтурно — отсылают на доработку, цикл +2 недели.

---

## 1. Description (для App Store + review)

```
Infinity Pay AI Support is the official support assistant for Infinity Pay
ISO merchants. Our bot helps restaurant and retail owners manage their
Clover POS through natural language conversations on Telegram.

Core capabilities:
• Sales analytics: daily totals, hourly breakdowns, top items, payment
  method splits — answered conversationally so non-technical merchants
  understand instantly.
• Menu management: enable/disable items as sold out, update prices,
  add new items. Common after-hours requests when merchants don't have
  time to navigate the dashboard.
• Device monitoring: check terminal health, last activity, offline
  alerts.
• Knowledge support: walks merchants through Clover-specific procedures
  (refunds, chargebacks, printer issues) using a curated knowledge base.
• Escalation: when issues require human intervention, automatically
  routes to the Infinity Pay support team with full context.

Used by 152 active merchants — primarily Russian-speaking restaurant
operators across the Northeast US who benefit from multi-language support
(English, Russian, Tajik, Uzbek, Spanish).

Built on Claude AI with native tool use, deployed on Railway, hosted at
infinity-pay-dashboard-production.up.railway.app.
```

---

## 2. Privacy Policy URL

**Нужно:** опубликовать на сайте `infinitypay.us/privacy`

### Готовый текст (создай страницу `/privacy` на твоём сайте):

```markdown
# Privacy Policy — Infinity Pay AI Support

Last updated: 2026-04-25

## What we collect when you connect your Clover account

When you authorize our app via Clover OAuth, we receive an access token
that lets us read your merchant data on your behalf. We use this access
solely to power features the merchant explicitly requests via our chat
bot:

• Sales data (totals, breakdowns, top items)
• Menu items and inventory state
• Order history (most recent transactions)
• Connected device list and status
• Employee names and roles (for ticket context — never PINs or pay rates)

We DO NOT receive or store:
• Cardholder data (full PAN, CVV, magnetic stripe)
• Customer personal information
• Bank account or routing numbers
• Tax IDs

## How we store your data

Your Clover access token is encrypted at rest using AES-256 with a key
held by Infinity Pay only — Clover, Railway, and our database provider
cannot decrypt it. The encrypted token lives in our PostgreSQL database
inside Railway's private network. We retain it only as long as your
Infinity Pay merchant account is active. Disconnecting your Clover
account from our dashboard immediately revokes and deletes the token.

Conversation history with the bot is stored for 30 days for context
across sessions, then purged. You can request earlier deletion by
emailing support@infinitypay.us.

## Who we share with

• Anthropic (Claude AI) — receives the text of your messages and any
  Clover data needed to answer your question, used only for that single
  response. No training, no retention beyond the API call. See:
  https://www.anthropic.com/legal/privacy
• Telegram — handles message delivery between you and the bot.
• Our internal support team — sees ticket content when you escalate.
• No one else. We do not sell, rent, or share data with advertisers
  or analytics providers.

## Your rights

You may at any time:
• Disconnect your Clover account (revokes our access immediately)
• Delete all your conversation history (email support@infinitypay.us)
• Stop using the bot (block it on Telegram)
• Request a copy of all data we hold on you

## Contact

Questions or requests:
• Email: support@infinitypay.us
• Phone: +1 (347) 883-3577
• Address: [Your business address — fill this in]

Infinity Pay Inc., a US-registered ISO/MSP affiliated with Tekcard.
```

---

## 3. Terms of Service URL

**Нужно:** опубликовать на сайте `infinitypay.us/terms`

### Готовый текст:

```markdown
# Terms of Service — Infinity Pay AI Support

Last updated: 2026-04-25

## Eligibility

This service is available only to active Infinity Pay merchants who
have completed onboarding through an authorized Infinity Pay sales
agent. By using @InfinityPaySupportBot you confirm you are an authorized
representative of the merchant business.

## What we provide

A Telegram-based support assistant that can:
• Answer questions about your Clover POS, transactions, and Infinity Pay
  account.
• Make read-only queries to your Clover account (sales, devices, menu)
  when you authorize via OAuth.
• Make limited write actions to your Clover account (toggle item
  availability, update prices, add menu items) when you explicitly
  request them in conversation.
• Escalate to a human support agent when the issue requires it.

## Limitations

• The bot is not a substitute for Tekcard's hotline for time-critical
  fraud, transaction reversal, or settlement issues.
• Bot responses about regulations, legal matters, or financial advice
  are informational only — consult appropriate professionals.
• We cannot disclose rates, fees, or contract terms via the bot —
  please contact your Infinity Pay sales agent or owner directly.

## Acceptable use

You agree not to:
• Use the bot to harass, flood, or stress-test our systems (limit
  enforced: 100 messages/day per merchant).
• Share access to your Clover account with anyone outside your business.
• Reverse-engineer, scrape, or attempt to extract proprietary data
  from the bot.

## Liability

The service is provided "as is". Infinity Pay Inc. is not liable for
business losses arising from bot downtime, AI mistakes, or merchant
errors made via bot tools. Always verify financial data on the official
Clover dashboard at clover.com.

## Contact

Email: support@infinitypay.us · Phone: +1 (347) 883-3577

Infinity Pay Inc.
```

---

## 4. Demo Video (2 minutes)

### Сценарий — что записать в Loom / Zoom recording

**Видео-структура (~120 секунд):**

1. **Intro (10s)** — экран с логотипом + текст
   ```
   "Infinity Pay AI Support — Telegram bot helping 152 ISO merchants
    manage their Clover POS through conversational AI."
   ```

2. **Merchant signup (15s)** — показать `/start INF-XXXX`
   - Открой Telegram → @InfinityPaySupportBot → /start INF-3456
   - Бот: "✅ Pizza Palace connected!"

3. **Sales query (15s)** — голос или текст
   - Мерчант: "What are today's sales?"
   - Бот: вызывает `get_sales_today` tool → "$420 today, 23 orders, average $18"

4. **Menu management (20s)** — реальное use case
   - Мерчант: "Mark chicken plov sold out for today"
   - Бот: вызывает `toggle_menu_item` tool → "Done, chicken plov is now hidden"
   - Подтверждение: открыть Clover dashboard → видно что блюдо скрыто

5. **Multilingual (15s)** — показать что работает на русском
   - Мерчант (RU): "Какие продажи на этой неделе?"
   - Бот отвечает на русском с цифрами

6. **Escalation (15s)** — что бот делает с серьёзными проблемами
   - Мерчант: "I got a chargeback yesterday"
   - Бот: вызывает `escalate_to_support` → "Тикет #142 создан, наш специалист свяжется"
   - Открыть наш дашборд → виден тикет

7. **Privacy / disconnect (10s)** — показать что мерчант контролирует
   - Открыть наш дашборд → Merchants → одна кнопка "Disconnect Clover"
   - "Tokens encrypted at rest, can be revoked anytime"

8. **Outro (10s)** — экран
   ```
   "Built with Claude AI. Encrypted token storage. PCI-compliant
    data handling. infinitypay.us"
   ```

### Как записать

```bash
# На Mac
1. Open QuickTime → New Screen Recording
2. Запиши все шаги выше
3. Loom (https://loom.com) — даёт публичный URL для отправки
   ИЛИ
4. YouTube unlisted — тоже подойдёт
```

---

## 5. Permissions Justification

В форме Clover для каждого scope нужно объяснение **зачем именно тебе**.

### Готовые формулировки:

**`READ_MERCHANT`** ← проверь что включён
```
Required to identify the merchant after OAuth and look up basic info
(business name, location) for personalized bot responses.
```

**`READ_PAYMENTS`**
```
Required for sales analytics — daily/weekly totals, transaction count,
average ticket size, payment method breakdown. The most common merchant
question is "what did I make today" — this scope answers it.
```

**`READ_ORDERS`**
```
Required to show recent orders, top-selling items, and hourly sales
patterns. Lets the bot answer "what's my busiest hour" or "what sold
yesterday".
```

**`READ_INVENTORY`**
```
Required to list current menu items and their prices/availability when
the merchant asks "is X still on the menu" or wants to find an item to
modify.
```

**`WRITE_INVENTORY`**
```
Required for the most-requested feature: marking items as sold out
during service ("we ran out of chicken plov"). Without this scope,
merchants would have to navigate Clover dashboard manually during the
dinner rush. Also enables price updates and adding new items by voice
(merchants often ask via voice message while away from the POS).
```

**`READ_EMPLOYEES`**
```
Required when escalating tickets — knowing which employees are on shift
helps support agents understand the context (e.g., "new hire processed
this transaction").
```

---

## 📋 Submission checklist

Перед нажатием "Submit for Review":

- [ ] Description (выше) скопирован в App Description
- [ ] Privacy URL: `infinitypay.us/privacy` (страница опубликована)
- [ ] Terms URL: `infinitypay.us/terms` (страница опубликована)
- [ ] Demo video URL загружен (Loom / YouTube unlisted)
- [ ] Все 6 scopes (READ_MERCHANT, READ_PAYMENTS, READ_ORDERS, READ_INVENTORY, WRITE_INVENTORY, READ_EMPLOYEES) с объяснениями
- [ ] App icon загружен (минимум 512×512px) — можно сделать из логотипа Infinity Pay
- [ ] Support email: `support@infinitypay.us`
- [ ] Support phone: `+1 (347) 883-3577`
- [ ] Test merchant credentials указаны (sandbox merchant для review)

---

## 🚀 После submit

1. Email подтверждение приходит сразу
2. Reviewer назначается за 24-48 часов
3. Если проходит чисто — approval за 1-2 недели
4. Если questions — приходит email, отвечаешь, цикл +1 неделя

**Если за 14 дней нет ответа** — пиши:
```
To: app-review@clover.com
Subject: App Review Status — Infinity Pay (App ID: WJXR55ASP5PKJ)

Hi Clover team,

Submitted Infinity Pay app for production review on [DATE].
Could you provide an ETA or any blockers I need to address?

We have 152 ISO merchants ready to onboard via OAuth as soon as we
get approval. Happy to provide additional documentation, jump on a
call, or expedite if possible.

Thanks,
Shams Rozikov
Co-founder, Infinity Pay Inc.
shams@infinitypay.us · +1 (347) 883-3577
```

---

## 🟡 Пока ждёшь — что бот УЖЕ умеет БЕЗ Clover API

Дашборд имеет 2761 строк документации в `knowledge/clover/` — бот через `lookup_clover_help` отвечает на:

✅ "Терминал не включается" → walks through hard reset
✅ "Не могу принять оплату" → diagnostic flow
✅ "WiFi не подключается" → troubleshooting steps
✅ "Хочу вернуть деньги клиенту" → refund process через device + dashboard
✅ "Пришёл чарджбек" → собрать evidence + escalate
✅ "Где мой депозит" → объяснить timing (3-5 business days)
✅ "Как добавить сотрудника" → Dashboard → Employees → Add
✅ "Принтер не печатает" → cable + paper + reset checks
✅ "Как поменять цену в меню" → пошагово через Clover dashboard
✅ "Что такое MID/EMV/NFC" → glossary

Плюс эскалация серьёзных вопросов на твою команду.

**~70-80% типичных вопросов мерчантов решаются через KB прямо сейчас, без Clover prod.**

Только эти 4 фичи требуют Clover live API:
- "Какие у меня продажи сегодня?" (нужен API)
- "Покажи топ блюд" (нужен API)
- "Выключи блюдо из меню" (нужен API)
- "Поменяй цену" (нужен API)

---

**Bottom line:** оформи submission package по этому документу, потом 1-2 недели ждёшь. А пока — бот уже полезен мерчантам.

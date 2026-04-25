# 🛡️ Super-Admin Mode — управление ВСЕМИ мерчантами через Telegram

> Для: Shams (owner), Daler (owner), Laziza (admin)
> Где: личка с `@Infinitypaysupport_bot` или группа `Infinity Support` (с тэгом `@bot`)
> Зачем: задавать вопросы и менять данные для **любого** из 152 мерчантов через
> естественную речь, не открывая дашборд.

---

## 🚀 Что появилось (2026-04-25)

Раньше внутренний бот умел только тикеты:
> "Беру 142", "Закрой 138", "Передай Лазизе 140"

**Теперь** — полный super-admin доступ к любому мерчанту:
> "Что с Taku сегодня?", "Выключи плов у Faiza", "Поменяй цену самсы у Silk Road на 8"

---

## 📋 Все доступные команды (естественная речь, без `/`)

### 🎫 Тикеты (как было)

```
"Что у меня открыто?"               → твои тикеты
"Срочные"                           → urgent тикеты команды
"Что в очереди?"                    → unassigned
"Беру 142"                          → assign себе
"Передай Лазизе 140"                → reassign
"Закрой 138, починили"              → resolve
"Кто онлайн?"                       → агенты со статусом
"Как мы идём?"                      → KPIs (открытые/урджент/SLA)
```

### 🔍 Поиск мерчанта

```
"Найди Taku"                        → fuzzy search по имени
"INF-0329"                          → по коду
"5VHNT2Q0H8AJ1"                     → по MID
"Покажи Plov Point"                 → если уникально — overview сразу
```

Если несколько совпадений — бот покажет 5 кандидатов с их INF-кодами.

### 💰 Продажи и аналитика (read-only — для всех)

```
"Что с Taku Food?"                  → overview: контакты, продажи сегодня, тикеты, девайсы
"Сколько Faiza продал сегодня?"     → today's sales
"Сколько Silk Road за неделю?"      → 7d total + breakdown
"30 дней Ochag"                     → 30-day trend
"Топ блюд у Shawarma #1"            → top selling items
"Что в меню у Taku?"                → full menu w/ prices + availability
"Терминалы у Faiza"                 → devices online/offline
"Последние заказы Plov Point"       → recent transactions
"Тикеты Bison Burger"               → их тикеты open + closed
"Открытые тикеты Silk Road"         → только open
```

### ⚡ Действия (admin/owner only — Shams/Daler/Laziza)

```
"Выключи плов у Taku"               → mark sold-out (toggle_item false)
"Верни самсу в меню Faiza"          → mark available (toggle_item true)
"Поменяй цену самсы у Taku на 8"    → update_price → $8
"Напиши Plov Point: завтра встретимся в 5"
                                     → бот шлёт TG-сообщение мерчанту от своего имени
```

### 📡 Broadcast / массовая рассылка

```
"Отправь всем мерчантам приветствие"
  → бот покажет ТЕКСТ + audience count, спросит подтверждение
  → ты пишешь "отправляй" → шлёт партиями
  → если ничего не пишешь / пишешь "стоп" → не шлёт

"Напиши только активным мерчантам с TG: ..."
  → audience filter по telegram_chat_id IS NOT NULL
```

---

## 🎬 Примеры реальных сценариев

### Сценарий 1. "Кто-то из Taku пишет что плов закончился"

Раньше: ты звонишь в Taku → они открывают Clover dashboard → выключают плов.
Теперь:
```
Ты: Выключи плов у Taku
Бот: Готово — у TAKU FOOD убрал "Plov" из меню, теперь sold-out.
```

### Сценарий 2. "Мне надо понять как идут дела у проблемного мерчанта"

```
Ты: Что с Faiza за неделю?
Бот:
  💰 $8,432 за 7 дней (1,205 заказов, средний $7)
  🎫 Открытых тикетов: 2
     · IP-0042 [Urgent] Терминал Flex 4 не печатает (3ч назад)
     · IP-0038 [Normal] Хочу добавить новое блюдо
  📱 Терминалы: 4 (3 онлайн, 1 offline 6 часов)
```

### Сценарий 3. "Поменять цены сразу нескольким"

```
Ты: Поменяй самсу у Taku на 8 и у Farhod тоже на 8
Бот: Хорошо. Подтверди — обе позиции "Самса" на $8?
Ты: да
Бот:
  ✅ TAKU FOOD: "Tandyr Samsa" $7 → $8
  ✅ FARHOD FOOD: "Самса" $6.50 → $8
```

### Сценарий 4. "Напомнить мерчанту что-то"

```
Ты: Напиши Plov Point: завтра встречаемся в 5 в их ресторане
Бот: Покажу что отправлю:
     "завтра встречаемся в 5 в их ресторане"
     → PLOV POINT (telegram chat 123456789)
     Отправлять?
Ты: да
Бот: ✉️ Отправлено в Plov Point
```

(сообщение появится у owner Plov Point в его Telegram-чате с ботом)

### Сценарий 5. "Кто-то жалуется на терминал"

```
Ты: Терминалы у Silk Road
Бот:
  📱 5 устройств у Silk Road Uzbek Restaurant:
  · Flex 4 (C046UG52250737)        🟢 онлайн, последняя оплата 12 мин назад
  · Flex 4 (C046UG52250742)        🟢 онлайн, 8 мин назад
  · Flex 4 (C046UG52250800)        🔴 offline, последний раз 4 часа назад
  · Station Duo 2nd Gen            🟢 онлайн, 3 мин назад
  · Kitchen Display 24"            🟢 онлайн (KDS — без транзакций)

Ты: Открой тикет на Flex 4 offline у Silk Road, urgent
Бот:
  ✅ Тикет IP-0149 создан: "Flex 4 offline 4h+ at Silk Road"
     Priority: Urgent · Category: Hardware · Назначен: support1
```

---

## 🔐 Permissions

| Роль | Может |
|---|---|
| **owner** (Shams, Daler) | Всё. Read + write + broadcast + send_message |
| **admin** (Laziza) | Read + write + send_message |
| **agent** (support1, support2) | Read only — `merchant_overview`, `merchant_sales`, `merchant_menu`, etc.<br>Toggling items, цены, send_message — заблокировано |

Если агент попросит write op — бот ответит:
> "Нужен admin или owner. Спроси Shams или Daler."

---

## 🤖 Какая модель работает

`BOT_MODEL = claude-sonnet-4-6` (только что апгрейднул с Haiku).

Sonnet 4.6:
- Понимает кашу из мыслей, опечатки, смешанные языки (RU/EN/UZ/TJ/ES)
- Корректно вызывает несколько tools подряд если нужно (например merchant_overview → если есть offline терминал → escalate_to_support)
- Цена ~$3/M input vs $1 у Haiku — для 1500 сообщений/день примерно $0.40/день разница, ничтожно

Если хочешь экономить — поставь обратно `BOT_MODEL=claude-haiku-4-5`. Если хочешь самый умный — `claude-opus-4-7` (но дорого, ~10× Sonnet).

---

## 🧩 Что под капотом

Файлы:
- `infinity-pay-dashboard/src/bot/agentTools.js` — 20 tools в total (было 9)
- `infinity-pay-dashboard/src/bot/systemPrompts.js` — обновлены agentPrompt / ownerPrompt
- `infinity-pay-dashboard/src/bot/webhook.js` — без изменений, route handler уже умеет вызывать новые tools

Архитектура:
```
Shams DM → @Infinitypaysupport_bot
  → webhook handles "owner" role
  → ownerPrompt + 20 tools
  → Sonnet 4.6 решает что вызвать
  → tool executor (resolveMerchant → Clover API / DB)
  → ответ Shams
```

Memory: каждый разговор сохраняется в `bot_conversations` таблицу — Sonnet видит последние 20 сообщений между тобой и ботом.

---

## 🎯 Прямо сейчас

После следующего деплоя (Railway собирает ~60-90 сек) — открывай `@Infinitypaysupport_bot` в личке и пиши:

```
Что с Taku Food?
```

Бот должен ответить: контакты, sales today, открытые тикеты, девайсы.

Если что-то не работает / не понимает — скажи мне точную фразу что писал и что ответил, доработаю промпт или tool.

# 📨 Сообщения мерчантам — рассылка

> Готовые тексты для отправки 152 мерчантам через Telegram / WhatsApp / SMS.
> Каждому мерчанту вставь его персональный `INF-XXXX` код (последние 4 цифры MID).
> Где взять коды: дашборд → Merchants → CSV Export, или БД таблица `merchants.merchant_code`.

---

## 🇷🇺 RU — Русскоязычные мерчанты (большинство)

```
Salom! 👋

Мы запустили новый канал поддержки Infinity Pay — теперь все вопросы решаются быстрее через Telegram-бота.

🤖 Бот: @InfinityPaySupportBot
🔑 Ваш персональный код: INF-XXXX

Как пользоваться:
1. Откройте @InfinityPaySupportBot в Telegram
2. Нажмите Start (или напишите /start)
3. Введите ваш код: INF-XXXX
4. Готово! Пишите вопрос — текстом или голосовым 🎙

Бот сам разберётся, поможет с типичными вопросами (Clover POS, меню, принтер, отчёты), а если нужен живой человек — сразу передаст специалисту.

Работает 24/7, понимает русский, узбекский, таджикский, английский, испанский.

Если что-то не работает — напишите нам в этот же чат.

— Команда Infinity Pay 💙
```

---

## 🇺🇸 EN — English merchants

```
Hello! 👋

We've launched a new support channel for Infinity Pay — get help faster through our Telegram bot.

🤖 Bot: @InfinityPaySupportBot
🔑 Your personal code: INF-XXXX

How to use:
1. Open @InfinityPaySupportBot in Telegram
2. Tap Start (or send /start)
3. Enter your code: INF-XXXX
4. Done! Send your question — text or voice 🎙

The bot can answer common questions about Clover POS, menus, printers, and reports. For anything complex, it routes you to a real specialist.

Available 24/7 in English, Russian, Tajik, Uzbek, Spanish.

If you have any issues — just reply here.

— Infinity Pay Team 💙
```

---

## 🇹🇯 TJ — Тоҷикӣ

```
Салом! 👋

Мо канали нави дастгирии Infinity Pay-ро роҳ андохтем — акнун ҳамаи саволҳо тавассути боти Telegram тезтар ҳал мешаванд.

🤖 Бот: @InfinityPaySupportBot
🔑 Рамзи шахсии шумо: INF-XXXX

Чӣ тавр истифода кардан:
1. @InfinityPaySupportBot-ро дар Telegram кушоед
2. Start-ро пахш кунед (ё /start нависед)
3. Рамзи худро ворид кунед: INF-XXXX
4. Тайёр! Саволи худро нависед — матн ё садо 🎙

Бот ба саволҳои оддӣ (Clover POS, меню, принтер, ҳисобот) худаш ҷавоб медиҳад, ва агар одами зинда лозим бошад — ба мутахассис мепайвандад.

24/7 кор мекунад, забонҳои тоҷикӣ, ӯзбекӣ, русӣ, англисӣ, испаниро мефаҳмад.

Агар чизе кор накунад — ба ин ҷо нависед.

— Командаи Infinity Pay 💙
```

---

## 🇪🇸 ES — Español (для латиноамериканских мерчантов)

```
¡Hola! 👋

Lanzamos un nuevo canal de soporte para Infinity Pay — resuelve tus dudas más rápido a través de nuestro bot de Telegram.

🤖 Bot: @InfinityPaySupportBot
🔑 Tu código personal: INF-XXXX

Cómo usarlo:
1. Abre @InfinityPaySupportBot en Telegram
2. Toca Start (o envía /start)
3. Ingresa tu código: INF-XXXX
4. ¡Listo! Envía tu pregunta — texto o audio 🎙

El bot responde preguntas comunes sobre Clover POS, menús, impresoras, reportes. Si necesitas hablar con una persona real, te conecta con un especialista.

Disponible 24/7 en español, inglés, ruso, tayiko, uzbeko.

Si algo no funciona — escríbenos por aquí.

— Equipo Infinity Pay 💙
```

---

## 🇺🇿 UZ — O'zbek tilida

```
Assalomu alaykum! 👋

Infinity Pay'ning yangi qo'llab-quvvatlash kanalini ishga tushirdik — endi barcha savollar Telegram boti orqali tezroq hal qilinadi.

🤖 Bot: @InfinityPaySupportBot
🔑 Sizning shaxsiy kodingiz: INF-XXXX

Qanday foydalanish:
1. Telegramda @InfinityPaySupportBot'ni oching
2. Start tugmasini bosing (yoki /start yuboring)
3. Kodingizni kiriting: INF-XXXX
4. Tayyor! Savolingizni yozing — matn yoki ovoz 🎙

Bot oddiy savollarga (Clover POS, menyu, printer, hisobotlar) o'zi javob beradi. Murakkab masala bo'lsa — mutaxassisga yo'naltiradi.

24/7 ishlaydi, o'zbek, rus, tojik, ingliz, ispan tillarini tushunadi.

Biror narsa ishlamasa — shu yerga yozing.

— Infinity Pay jamoasi 💙
```

---

## 📋 Как массово разослать

### Вариант 1 — Из дашборда (когда добавим)
В roadmap есть фича `Broadcast` — массовая рассылка по `merchant.preferred_language`.

### Вариант 2 — Сейчас, вручную
Используй `Telegram desktop`. Открой каждого мерчанта в группе `INFINITY PAY / MERCHANTS`, скопируй RU-вариант, замени `INF-XXXX` на его код.

### Вариант 3 — Telegram MCP
Скрипт уже есть: `~/Library/Application Support/Claude/mcp-servers/telegram_mcp.py`.
Я могу прогнать всех 152 мерчантов автоматом — попроси меня "разошли мерчантам приветственное сообщение", и я сделаю с подтверждением каждого перед отправкой (анти-спам Telegram → не больше 30 сообщений в секунду).

### Что вставлять вместо INF-XXXX

```sql
SELECT name, mid, merchant_code, preferred_language, telegram_id
FROM merchants
WHERE active = true
ORDER BY name;
```

Или в дашборде: Merchants → Export CSV.

---

## ⚠️ Важно

- **Не отправляй всем сразу в одну минуту** — Telegram заблокирует. Распредели на 2-3 часа.
- **Спроси Daler первым** — он знает каких мерчантов прямо сейчас не надо беспокоить.
- **После рассылки** мониторь @InfinityPaySupportBot — могут пойти первые тикеты в течение часа.

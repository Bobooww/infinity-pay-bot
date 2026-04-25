# 📤 Инструкция для мерчанта — взять API token из своего Clover

> Шаблон сообщения для отправки мерчанту (через WhatsApp / Telegram / SMS)
> когда нужно подключить его Clover к нашему боту, а ты не можешь сделать это сам.

---

## 🇷🇺 RU — для русскоязычных мерчантов

```
Здравствуйте! 👋

Чтобы наш бот мог автоматически отвечать на ваши вопросы по Clover
(продажи, меню, заказы) — нужен один шаг: создать API-токен в Clover
и прислать мне.

Это займёт 3 минуты. Безопасно — токен только для нашего бота, в любой
момент отзовёте.

ШАГ 1. Заходите на https://www.clover.com со своим логином

ШАГ 2. Сверху-справа: иконка профиля → "Account & Setup"

ШАГ 3. Слева в меню: "Setup" → "API Tokens"

ШАГ 4. Нажмите "Create New Token"
   • Name: Infinity Pay Bot
   • Поставьте ВСЕ галочки в Permissions
   • Нажмите "Create"

ШАГ 5. Скопируйте появившуюся строку (длинная, с дефисами, типа:
   abc12345-def6-7890-ghij-klmnop123456)
   ВАЖНО: после закрытия окна Clover её больше не покажет.

ШАГ 6. Также найдите ваш Merchant ID:
   "Account & Setup" → "Merchant Info"
   Это короткая строка типа: 5VHNT2Q0H8AJ1

ШАГ 7. Пришлите мне обе строки сюда:
   • Token: <вставьте>
   • Merchant ID: <вставьте>

После этого бот начнёт работать с вашим Clover автоматически.

Спасибо!
```

---

## 🇺🇸 EN — for English-speaking merchants

```
Hi! 👋

To enable our bot to automatically answer your Clover questions
(sales, menu, orders) — we need one step: create an API token in your
Clover account and send it to me.

3 minutes, safe — token is only for our bot, you can revoke anytime.

STEP 1. Go to https://www.clover.com — log in with your owner account

STEP 2. Top right: profile icon → "Account & Setup"

STEP 3. Left menu: "Setup" → "API Tokens"

STEP 4. Click "Create New Token"
   • Name: Infinity Pay Bot
   • Check ALL Permissions boxes
   • Click "Create"

STEP 5. Copy the long string that appears (looks like:
   abc12345-def6-7890-ghij-klmnop123456)
   IMPORTANT: After closing the popup, Clover won't show it again.

STEP 6. Also find your Merchant ID:
   "Account & Setup" → "Merchant Info"
   Short string like: 5VHNT2Q0H8AJ1

STEP 7. Send me both:
   • Token: <paste here>
   • Merchant ID: <paste here>

After that, the bot will work with your Clover automatically.

Thanks!
```

---

## 🇪🇸 ES — para comerciantes hispanohablantes

```
¡Hola! 👋

Para que nuestro bot pueda responder automáticamente tus preguntas
sobre Clover (ventas, menú, órdenes) — necesitamos un paso: crear un
token API en tu cuenta Clover y enviármelo.

3 minutos, seguro — el token es solo para nuestro bot, puedes
revocarlo en cualquier momento.

PASO 1. Entra a https://www.clover.com con tu cuenta de owner

PASO 2. Arriba a la derecha: icono de perfil → "Account & Setup"

PASO 3. Menú izquierdo: "Setup" → "API Tokens"

PASO 4. Click en "Create New Token"
   • Name: Infinity Pay Bot
   • Marca TODAS las casillas de Permissions
   • Click "Create"

PASO 5. Copia la cadena larga que aparece (tipo:
   abc12345-def6-7890-ghij-klmnop123456)
   IMPORTANTE: después de cerrar el popup, Clover no la mostrará de nuevo.

PASO 6. También encuentra tu Merchant ID:
   "Account & Setup" → "Merchant Info"
   Cadena corta tipo: 5VHNT2Q0H8AJ1

PASO 7. Envíame ambas:
   • Token: <pega aquí>
   • Merchant ID: <pega aquí>

Después de eso, el bot trabajará con tu Clover automáticamente.

¡Gracias!
```

---

## 🛡️ Если мерчант беспокоится про безопасность

Готовый ответ:

```
RU: "Безопасно — токен зашифрован у нас в БД, никто кроме нашего бота
его не видит. В любой момент можете удалить через Clover dashboard
(API Tokens → Delete). Бот пользуется токеном только когда ВЫ ему
напишете в Telegram — никаких background-запросов."

EN: "Safe — token is encrypted in our database, only our bot has access.
You can revoke anytime from Clover dashboard (API Tokens → Delete). Bot
uses the token ONLY when YOU message it on Telegram — no background
queries."
```

---

## 📋 После того как мерчант прислал

1. Открываешь дашборд → Merchants → этот мерчант → Clover tab
2. **"Or paste token manually"** → вводишь оба значения → **"Save & verify"**
3. Если зелёная плашка "Token saved and verified" — готово
4. Если ошибка — см. troubleshooting в `MANUAL_CLOVER_TOKEN_GUIDE.md`

---

**Один мерчант = ~5 минут от твоего сообщения до полностью подключённого бота.**

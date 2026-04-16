"""
Infinity Pay — Telegram Support Bot
Запускается командой: python bot.py

Логика:
1. Мерчант пишет боту первый раз → просим уникальный код (INF-001 etc.)
2. Код найден → привязываем Telegram ID к мерчанту в ClickUp
3. Следующие сообщения → Claude анализирует → отвечает сам ИЛИ создаёт тикет в ClickUp
4. Команда пишет комментарий в ClickUp → бот пересылает мерчанту в Telegram
"""

import os
import json
import logging
import asyncio
from dotenv import load_dotenv
from anthropic import Anthropic

# Загружаем .env файл
load_dotenv()
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config из переменных окружения ─────────────────────────────────────────
TELEGRAM_TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
CLAUDE_API_KEY         = os.environ["CLAUDE_API_KEY"]
CLICKUP_TOKEN          = os.environ["CLICKUP_API_TOKEN"]
CLICKUP_LIST_TICKETS   = os.environ["CLICKUP_LIST_TICKETS_ID"]
CLICKUP_LIST_MERCHANTS = os.environ["CLICKUP_LIST_MERCHANTS_ID"]

CLICKUP_HEADERS = {
    "Authorization": CLICKUP_TOKEN,
    "Content-Type": "application/json"
}
CLICKUP_BASE = "https://api.clickup.com/api/v2"

# ─── Саппорт-команда (ClickUp User IDs) ───────────────────────────────────
SUPPORT_AGENTS = [
    {"id": 94469635, "name": "Support 1"},
    {"id": 94469636, "name": "Support 2"},
]

anthropic_client = Anthropic(api_key=CLAUDE_API_KEY)


# ─── Авто-назначение тикетов по нагрузке ──────────────────────────────────

def get_least_loaded_agent() -> dict:
    """Возвращает агента с наименьшим количеством открытых тикетов."""
    agent_loads = []

    for agent in SUPPORT_AGENTS:
        try:
            r = requests.get(
                f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
                headers=CLICKUP_HEADERS,
                params={
                    "assignees[]": [agent["id"]],
                    "include_closed": False,
                    "subtasks": False,
                    "page": 0,
                }
            )
            if r.status_code == 200:
                tasks = r.json().get("tasks", [])
                agent_loads.append({"agent": agent, "open_tickets": len(tasks)})
                logger.info(f"Агент {agent['name']}: {len(tasks)} открытых тикетов")
            else:
                logger.warning(f"Ошибка загрузки тикетов для {agent['name']}: {r.status_code}")
                agent_loads.append({"agent": agent, "open_tickets": 999})
        except Exception as e:
            logger.error(f"Ошибка при проверке нагрузки {agent['name']}: {e}")
            agent_loads.append({"agent": agent, "open_tickets": 999})

    # Сортируем по количеству открытых тикетов — первый = наименее загружен
    agent_loads.sort(key=lambda x: x["open_tickets"])
    chosen = agent_loads[0]["agent"]
    logger.info(f"Назначаем тикет на: {chosen['name']} (ID: {chosen['id']})")
    return chosen


# ─── Временное хранилище состояния ──────────────────────────────────────────
# В production лучше использовать Redis или PostgreSQL
# Для MVP — в памяти (сбрасывается при рестарте бота)
user_states = {}   # {telegram_id: "awaiting_code" | "identified"}
merchant_cache = {}  # {telegram_id: merchant_data}


# ─── ClickUp helpers ───────────────────────────────────────────

def search_merchant_by_code(code: str) -> dict | None:
    """Ищет мерчанта в ClickUp по уникальному коду (INF-001).

    Загружает ВСЕ задачи из списка мерчантов и проверяет custom field
    'Unique Code', т.к. ClickUp search ищет только по названию задачи.
    """
    page = 0
    while True:
        r = requests.get(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_MERCHANTS}/task",
            headers=CLICKUP_HEADERS,
            params={"include_closed": False, "page": page, "subtasks": False}
        )
        if r.status_code != 200:
            logger.error(f"ClickUp search error: {r.status_code} {r.text}")
            return None

        tasks = r.json().get("tasks", [])
        if not tasks:
            break

        for task in tasks:
            for field in task.get("custom_fields", []):
                if field.get("name") == "Unique Code":
                    val = field.get("value", "")
                    if val and val.strip().upper() == code.strip().upper():
                        logger.info(f"Мерчант найден: {task['name']} (код: {code})")
                        return extract_merchant_data(task)

        # ClickUp отдаёт до 100 задач на страницу
        if len(tasks) < 100:
            break
        page += 1

    logger.warning(f"Мерчант с кодом {code} не найден")
    return None


def search_merchant_by_telegram_id(telegram_id: int) -> dict | None:
    """Ищет мерчанта по Telegram User ID (с пагинацией)."""
    page = 0
    while True:
        r = requests.get(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_MERCHANTS}/task",
            headers=CLICKUP_HEADERS,
            params={"include_closed": False, "page": page, "subtasks": False}
        )
        if r.status_code != 200:
            return None

        tasks = r.json().get("tasks", [])
        if not tasks:
            break

        for task in tasks:
            for field in task.get("custom_fields", []):
                if field.get("name") == "Telegram ID":
                    val = field.get("value", "")
                    if val and str(val).strip() == str(telegram_id):
                        return extract_merchant_data(task)

        if len(tasks) < 100:
            break
        page += 1

    return None


def extract_merchant_data(task: dict) -> dict:
    """Извлекает данные мерчанта из задачи ClickUp."""
    data = {
        "task_id": task["id"],
        "name": task["name"].split(" | MID:")[0].strip(),
        "mid": "",
        "phone": "",
        "email": "",
        "address": "",
        "business_type": "",
        "unique_code": "",
        "telegram_id": "",
    }
    field_map = {
        "MID": "mid",
        "Phone": "phone",
        "Email": "email",
        "Address": "address",
        "Business Type": "business_type",
        "Unique Code": "unique_code",
        "Telegram ID": "telegram_id",
    }
    for field in task.get("custom_fields", []):
        key = field_map.get(field.get("name", ""))
        if key:
            data[key] = field.get("value", "") or ""
    return data


def save_telegram_id_to_merchant(task_id: str, telegram_id: int, field_ids: dict = None):
    """Сохраняет Telegram ID в карточку мерчанта в ClickUp."""
    # Получаем задачу чтобы найти field ID
    r = requests.get(f"{CLICKUP_BASE}/task/{task_id}", headers=CLICKUP_HEADERS)
    if r.status_code != 200:
        return False

    task = r.json()
    tg_field_id = None
    for field in task.get("custom_fields", []):
        if field.get("name") == "Telegram ID":
            tg_field_id = field["id"]
            break

    if not tg_field_id:
        logger.warning(f"Telegram ID field не найден в task {task_id}")
        return False

    r = requests.post(
        f"{CLICKUP_BASE}/task/{task_id}/field/{tg_field_id}",
        headers=CLICKUP_HEADERS,
        json={"value": str(telegram_id)}
    )
    return r.status_code in (200, 201)


def create_support_ticket(merchant: dict, message: str, ai_analysis: dict) -> str | None:
    """Создаёт тикет поддержки в ClickUp с авто-назначением на наименее загруженного агента."""
    priority_map = {"Urgent": 1, "High": 2, "Normal": 3, "Low": 4}
    priority = priority_map.get(ai_analysis.get("priority", "Normal"), 3)

    # Определяем наименее загруженного агента
    assigned_agent = get_least_loaded_agent()

    task_name = f"[{ai_analysis.get('category', 'Other')}] {merchant['name']} — {message[:60]}"

    description = f"""**🏣 Мерчант:** {merchant['name']}
**🆔 MID:** {merchant['mid']}
**📱 Telegram ID:** {merchant.get('telegram_id', 'N/A')}

**📩 Сообщение:**
{message}

---
**🤖 AI Анализ:**
- Категория: {ai_analysis.get('category')}
- Приоритет: {ai_analysis.get('priority')}
- Уверенность: {ai_analysis.get('confidence')}%
- Назначено: {assigned_agent['name']}

**📋 Резюме:**
{ai_analysis.get('escalation_summary', '')}
"""

    payload = {
        "name": task_name,
        "description": description,
        "priority": priority,
        "assignees": [assigned_agent["id"]],
        "custom_fields": []
    }

    r = requests.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )

    if r.status_code in (200, 201):
        task = r.json()
        logger.info(f"Тикет создан: {task['id']} для {merchant['name']}")
        return task["id"]
    else:
        logger.error(f"Ошибка создания тикета: {r.status_code} {r.text}")
        return None


# ─── Claude AI ────────────────────────────────────────────────────────────────

def analyze_with_claude(merchant: dict, message: str) -> dict:
    """Отправляет сообщение в Claude и получает структурированный ответ."""

    system_prompt = f"""Ты AI-ассистент службы поддержки Infinity Pay Inc. — ISO (Independent Sales Organization) в сфере платёжных услуг.
Процессор: Tekcard. Основной POS: Clover.

Мерчант: {merchant['name']}
MID: {merchant['mid']}
Тип бизнеса: {merchant.get('business_type', 'Ресторан')}

ПРАВИЛА:
- Отвечай на языке мерчанта (русский или английский)
- ОТВЕЧАЙ СРАЗУ если простой вопрос о Clover/Tekcard с уверенностью >85%
- ЭСКАЛИРУЙ если: чарджбеки, закрытие аккаунта, изменение ставок, возвраты >$500, фрод/PCI вопросы, что-то неясное
- НИКОГДА не делись данными других мерчантов
- НИКОГДА не называй ставки без одобрения владельца
- НИКОГДА не проси номера карт/SSN/банковские данные

Ответь ТОЛЬКО в JSON формате:
{{
  "confidence": 0-100,
  "should_escalate": true/false,
  "category": "Hardware|Software|Statement|Payment|Account|Other",
  "priority": "Urgent|High|Normal|Low",
  "response_to_merchant": "текст ответа мерчанту",
  "escalation_summary": "краткое резюме для команды поддержки (если эскалация)"
}}"""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        )
        text = response.content[0].text.strip()
        # Убираем markdown если Claude обернул в ```json
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Claude вернул невалидный JSON: {e}")
        return {
            "confidence": 0,
            "should_escalate": True,
            "category": "Other",
            "priority": "Normal",
            "response_to_merchant": "Спасибо за обращение! Наш специалист свяжется с вами в ближайшее время.",
            "escalation_summary": f"Ошибка AI. Оригинальное сообщение: {message}"
        }
    except Exception as e:
        logger.error(f"Ошибка Claude API: {e}")
        return {
            "confidence": 0,
            "should_escalate": True,
            "category": "Other",
            "priority": "High",
            "response_to_merchant": "Произошла техническая ошибка. Ваш запрос передан специалисту.",
            "escalation_summary": f"Ошибка системы: {str(e)}. Сообщение: {message}"
        }


# ─── Telegram handlers ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — приветствие."""
    telegram_id = update.effective_user.id

    # Проверяем — уже идентифицирован?
    merchant = merchant_cache.get(telegram_id) or search_merchant_by_telegram_id(telegram_id)

    if merchant:
        merchant_cache[telegram_id] = merchant
        user_states[telegram_id] = "identified"
        await update.message.reply_text(
            f"👋 С возвращением, {merchant['name']}!\n\n"
            f"Чем могу помочь? Опишите вашу проблему или вопрос."
        )
    else:
        user_states[telegram_id] = "awaiting_code"
        await update.message.reply_text(
            "👋 Здравствуйте! Я AI-ассистент Infinity Pay.\n\n"
            "Для идентификации введите ваш персональный код.\n"
            "Код выглядит так: *INF-001*\n\n"
            "_(Код был отправлен вам при подключении к Infinity Pay)_",
            parse_mode="Markdown"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все входящие сообщения."""
    telegram_id = update.effective_user.id
    message_text = update.message.text.strip()
    state = user_states.get(telegram_id, "unknown")

    # ── Состояние: ожидаем код ─────────────────────────────────────────────────────
    if state == "awaiting_code":
        code = message_text.upper().strip()

        await update.message.reply_text("🔍 Проверяю код...")

        merchant = search_merchant_by_code(code)

        if merchant:
            # Сохраняем Telegram ID в ClickUp
            saved = save_telegram_id_to_merchant(merchant["task_id"], telegram_id)

            merchant["telegram_id"] = str(telegram_id)
            merchant_cache[telegram_id] = merchant
            user_states[telegram_id] = "identified"

            await update.message.reply_text(
                f"✅ *Идентификация успешна!*\n\n"
                f"Добро пожаловать, *{merchant['name']}*!\n"
                f"MID: `{merchant['mid']}`\n\n"
                f"Теперь просто опишите вашу проблему или вопрос — "
                f"я постараюсь помочь сразу или передам вашей команде поддержки.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Код *{code}* не найден.\n\n"
                f"Проверьте код и попробуйте ещё раз, или свяжитесь с нами напрямую.",
                parse_mode="Markdown"
            )
        return

    # ── Состояние: не идентифицирован ───────────────────────────────────────────
    if state not in ("identified",):
        # Проверяем в ClickUp (на случай перезапуска бота)
        merchant = search_merchant_by_telegram_id(telegram_id)
        if merchant:
            merchant_cache[telegram_id] = merchant
            user_states[telegram_id] = "identified"
        else:
            user_states[telegram_id] = "awaiting_code"
            await update.message.reply_text(
                "Для начала введите ваш код Infinity Pay (например: *INF-001*)",
                parse_mode="Markdown"
            )
            return

    # ── Состояние: идентифицирован — обрабатываем запрос ──────────────────────────────────
    merchant = merchant_cache.get(telegram_id)
    if not merchant:
        merchant = search_merchant_by_telegram_id(telegram_id)
        if not merchant:
            user_states[telegram_id] = "awaiting_code"
            await update.message.reply_text("Введите ваш код Infinity Pay:")
            return
        merchant_cache[telegram_id] = merchant

    # Показываем что обрабатываем
    await update.message.reply_text("⏳ Обрабатываю запрос...")

    # Анализируем через Claude
    analysis = analyze_with_claude(merchant, message_text)
    logger.info(
        f"[{merchant['name']}] confidence={analysis['confidence']} "
        f"escalate={analysis['should_escalate']} category={analysis['category']}"
    )

    # Решение: отвечать или эскалировать
    if not analysis["should_escalate"] and analysis["confidence"] >= 85:
        # Отвечаем напрямую
        await update.message.reply_text(analysis["response_to_merchant"])
    else:
        # Создаём тикет в ClickUp
        ticket_id = create_support_ticket(merchant, message_text, analysis)

        if ticket_id:
            await update.message.reply_text(
                "✅ *Ваш запрос принят!*\n\n"
                "Наш специалист изучит ситуацию и свяжется с вами "
                "в течение рабочего дня.\n\n"
                f"Номер обращения: `{ticket_id[:8]}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "✅ Ваш запрос получен. Специалист свяжется с вами в ближайшее время."
            )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    await update.message.reply_text(
        "📞 *Infinity Pay Support*\n\n"
        "Я могу помочь с:\n"
        "• Вопросами по работе Clover POS\n"
        "• Информацией о транзакциях\n"
        "• Техническими проблемами\n"
        "• Вопросами по выпискам\n\n"
        "Просто опишите вашу проблему!",
        parse_mode="Markdown"
    )


# ─── Main ────────────────────────────────────────────────────────────────────────────

def main():
    print("\n═══════════════════════════════════════════")
    print("  Infinity Pay Telegram Bot — Starting...")
    print("═══════════════════════════════════════════\n")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот запущен. Нажми Ctrl+C для остановки.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

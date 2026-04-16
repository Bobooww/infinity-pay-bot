"""
Infinity Pay — Telegram Support Bot v2
Запускается командой: python bot.py

Фичи v2:
- Гибрид AI: Haiku для простых → Sonnet для сложных
- Умные категории без "Other"
- Приоритеты Urgent/High/Normal/Low с эмодзи
- Сессии: группировка сообщений в один тикет (таймаут 10 мин)
- Голосовые сообщения (Whisper API)
- Дублирование тикетов в TG-группу поддержки
- Логин агентов/ISO через /login + секретный код
- Уведомления при смене статуса тикета (ClickUp webhook)
- FAQ кеш, антиспам, статистика
"""

import os
import json
import logging
import asyncio
import time
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ─── Загружаем .env ────────────────────────────────────────────────────────
load_dotenv()

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
CLAUDE_API_KEY         = os.environ["CLAUDE_API_KEY"]
CLICKUP_TOKEN          = os.environ["CLICKUP_API_TOKEN"]
CLICKUP_LIST_TICKETS   = os.environ["CLICKUP_LIST_TICKETS_ID"]
CLICKUP_LIST_MERCHANTS = os.environ["CLICKUP_LIST_MERCHANTS_ID"]

# Telegram группа поддержки (chat_id, задаётся в .env)
SUPPORT_GROUP_CHAT_ID  = os.environ.get("SUPPORT_GROUP_CHAT_ID", "")

# OpenAI API для Whisper (голосовые)
OPENAI_API_KEY         = os.environ.get("OPENAI_API_KEY", "")

CLICKUP_HEADERS = {
    "Authorization": CLICKUP_TOKEN,
    "Content-Type": "application/json"
}
CLICKUP_BASE = "https://api.clickup.com/api/v2"

# ─── Саппорт-команда ───────────────────────────────────────────────────────
SUPPORT_AGENTS = [
    {"id": 94469635, "name": "Support 1"},
    {"id": 94469636, "name": "Support 2"},
]

# ─── Секретные коды для логина агентов/ISO ──────────────────────────────────
AGENT_CODES = {
    "IAMAGENT": {"role": "agent", "name": "Infinity Pay Staff", "clickup_id": None},
    "ISO-MASTER": {"role": "iso", "name": "Shams (ISO Owner)", "clickup_id": None},
}

# ─── AI клиенты ────────────────────────────────────────────────────────────
anthropic_client = Anthropic(api_key=CLAUDE_API_KEY)

# ─── Приоритеты с эмодзи ──────────────────────────────────────────────────
PRIORITY_EMOJI = {
    "Urgent": "🔴",
    "High":   "🟠",
    "Normal": "🟡",
    "Low":    "🟢",
}
PRIORITY_MAP = {"Urgent": 1, "High": 2, "Normal": 3, "Low": 4}

# ─── Категории (без "Other") ──────────────────────────────────────────────
VALID_CATEGORIES = [
    "Terminal", "Payment", "Chargeback", "Statement",
    "Billing", "Account", "Software", "Hardware",
    "Fraud", "Compliance", "General"
]

# ─── Хранилище состояний (в памяти) ────────────────────────────────────────
user_states = {}       # {tg_id: "awaiting_code"|"identified"|"agent"|"iso"}
merchant_cache = {}    # {tg_id: merchant_data}
agent_sessions = {}    # {tg_id: {"role": "agent"|"iso", "name": ..., ...}}

# ─── Сессии сообщений (антидубль) ──────────────────────────────────────────
# {tg_id: {"messages": [...], "last_time": timestamp, "ticket_id": str|None}}
message_sessions = {}
SESSION_TIMEOUT = 600  # 10 минут

# ─── FAQ кеш ───────────────────────────────────────────────────────────────
faq_cache = {}  # {"вопрос_хеш": {"answer": str, "hits": int, "last_used": ts}}
FAQ_CACHE_MAX = 200

# ─── Антиспам ──────────────────────────────────────────────────────────────
spam_tracker = {}  # {tg_id: {"count": int, "first_msg": timestamp}}
SPAM_LIMIT = 10     # макс 10 сообщений за 60 сек
SPAM_WINDOW = 60

# ─── Статистика ────────────────────────────────────────────────────────────
stats = {
    "total_messages": 0,
    "tickets_created": 0,
    "ai_direct_answers": 0,
    "escalations": 0,
    "voice_messages": 0,
    "haiku_calls": 0,
    "sonnet_calls": 0,
}


# ═══════════════════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════════════════

def is_spam(tg_id: int) -> bool:
    """Антиспам: >10 сообщений за 60 сек."""
    now = time.time()
    if tg_id not in spam_tracker:
        spam_tracker[tg_id] = {"count": 1, "first_msg": now}
        return False
    tracker = spam_tracker[tg_id]
    if now - tracker["first_msg"] > SPAM_WINDOW:
        spam_tracker[tg_id] = {"count": 1, "first_msg": now}
        return False
    tracker["count"] += 1
    return tracker["count"] > SPAM_LIMIT


def get_session(tg_id: int) -> dict:
    """Возвращает текущую сессию или создаёт новую."""
    now = time.time()
    if tg_id in message_sessions:
        session = message_sessions[tg_id]
        if now - session["last_time"] < SESSION_TIMEOUT:
            session["last_time"] = now
            return session
    message_sessions[tg_id] = {
        "messages": [],
        "last_time": now,
        "ticket_id": None,
    }
    return message_sessions[tg_id]


def close_session(tg_id: int):
    """Мягко закрывает сессию — сбрасывает тикет, но сохраняет историю сообщений для контекста."""
    if tg_id in message_sessions:
        message_sessions[tg_id]["ticket_id"] = None


# ═══════════════════════════════════════════════════════════════════════════
# CLICKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════

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
            else:
                agent_loads.append({"agent": agent, "open_tickets": 999})
        except Exception as e:
            logger.error(f"Ошибка нагрузки {agent['name']}: {e}")
            agent_loads.append({"agent": agent, "open_tickets": 999})

    agent_loads.sort(key=lambda x: x["open_tickets"])
    chosen = agent_loads[0]["agent"]
    logger.info(f"Назначаем на: {chosen['name']}")
    return chosen


def search_merchant_by_code(code: str) -> dict | None:
    """Ищет мерчанта по уникальному коду."""
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
                if field.get("name") == "Unique Code":
                    val = field.get("value", "")
                    if val and val.strip().upper() == code.strip().upper():
                        return extract_merchant_data(task)
        if len(tasks) < 100:
            break
        page += 1
    return None


def search_merchant_by_telegram_id(telegram_id: int) -> dict | None:
    """Ищет мерчанта по Telegram ID."""
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
    """Извлекает данные мерчанта."""
    data = {
        "task_id": task["id"],
        "name": task["name"].split(" | MID:")[0].strip(),
        "mid": "", "phone": "", "email": "", "address": "",
        "business_type": "", "unique_code": "", "telegram_id": "",
    }
    field_map = {
        "MID": "mid", "Phone": "phone", "Email": "email",
        "Address": "address", "Business Type": "business_type",
        "Unique Code": "unique_code", "Telegram ID": "telegram_id",
    }
    for field in task.get("custom_fields", []):
        key = field_map.get(field.get("name", ""))
        if key:
            data[key] = field.get("value", "") or ""
    return data


def save_telegram_id_to_merchant(task_id: str, telegram_id: int):
    """Сохраняет Telegram ID в карточку мерчанта."""
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
        return False
    r = requests.post(
        f"{CLICKUP_BASE}/task/{task_id}/field/{tg_field_id}",
        headers=CLICKUP_HEADERS,
        json={"value": str(telegram_id)}
    )
    return r.status_code in (200, 201)


def create_support_ticket(merchant: dict, message: str, ai_analysis: dict) -> str | None:
    """Создаёт тикет в ClickUp."""
    priority = PRIORITY_MAP.get(ai_analysis.get("priority", "Normal"), 3)
    assigned_agent = get_least_loaded_agent()
    category = ai_analysis.get("category", "General")
    priority_label = ai_analysis.get("priority", "Normal")
    emoji = PRIORITY_EMOJI.get(priority_label, "🟡")

    # Используем AI-резюме для названия тикета
    summary = ai_analysis.get("escalation_summary", "")
    task_title = summary[:80] if summary else message[:80]
    task_name = f"{emoji} [{category}] {merchant['name']} — {task_title}"

    description = f"""**🏪 Мерчант:** {merchant['name']}
**🆔 MID:** {merchant['mid']}
**📱 Telegram ID:** {merchant.get('telegram_id', 'N/A')}

**📩 Сообщение:**
{message}

---
**🤖 AI Анализ:**
- Категория: {category}
- Приоритет: {emoji} {priority_label}
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
        ticket_id = task["id"]
        logger.info(f"Тикет создан: {ticket_id}")
        stats["tickets_created"] += 1

        # Дублируем в TG-группу поддержки
        if SUPPORT_GROUP_CHAT_ID:
            try:
                notify_text = (
                    f"🆕 *Новый тикет*\n\n"
                    f"{emoji} *Приоритет:* {priority_label}\n"
                    f"📁 *Категория:* {category}\n"
                    f"🏪 *Мерчант:* {merchant['name']}\n"
                    f"🆔 *MID:* {merchant['mid']}\n"
                    f"👤 *Назначен:* {assigned_agent['name']}\n\n"
                    f"💬 *Сообщение:*\n{message[:300]}\n\n"
                    f"📋 *AI Резюме:*\n{ai_analysis.get('escalation_summary', 'N/A')}\n\n"
                    f"🔗 Тикет ID: `{ticket_id}`"
                )
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": SUPPORT_GROUP_CHAT_ID,
                        "text": notify_text,
                        "parse_mode": "Markdown",
                    }
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления в группу: {e}")

        return ticket_id
    else:
        logger.error(f"Ошибка создания тикета: {r.status_code} {r.text}")
        return None


def add_comment_to_ticket(ticket_id: str, comment: str):
    """Добавляет комментарий к тикету в ClickUp."""
    r = requests.post(
        f"{CLICKUP_BASE}/task/{ticket_id}/comment",
        headers=CLICKUP_HEADERS,
        json={"comment_text": comment}
    )
    return r.status_code in (200, 201)


# ═══════════════════════════════════════════════════════════════════════════
# AI — ГИБРИД HAIKU/SONNET
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """Ты AI-ассистент Infinity Pay Inc. — ISO в сфере платёжных услуг.
Процессор: Tekcard. POS: Clover.

Мерчант: {name} | MID: {mid} | Бизнес: {business_type}

ПРАВИЛА:
- Определи язык мерчанта и отвечай ТОЛЬКО на нём (RU/EN/TJ/UZ/AR/ES).
- Понимай уличный/разговорный стиль, сленг, смешанный язык.
- ОТВЕЧАЙ СРАЗУ если уверенность >85%.
- ЭСКАЛИРУЙ если: чарджбеки, закрытие аккаунта, ставки, возвраты >$500, фрод/PCI.
- НИКОГДА не делись данными других мерчантов.
- НИКОГДА не называй ставки.
- НИКОГДА не проси карты/SSN/банковские данные.

Категории (ТОЛЬКО из списка): Terminal, Payment, Chargeback, Statement, Billing, Account, Software, Hardware, Fraud, Compliance, General

JSON ответ:
{{"confidence":0-100,"should_escalate":true/false,"category":"<из списка>","priority":"Urgent|High|Normal|Low","response_to_merchant":"текст","escalation_summary":"резюме"}}"""


def analyze_with_claude(merchant: dict, message: str, use_sonnet: bool = False) -> dict:
    """Гибрид: сначала Haiku, если сложно — Sonnet."""
    model = "claude-sonnet-4-6" if use_sonnet else "claude-haiku-4-5-20251001"
    model_label = "sonnet" if use_sonnet else "haiku"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        name=merchant.get("name", ""),
        mid=merchant.get("mid", ""),
        business_type=merchant.get("business_type", "Ресторан"),
    )

    try:
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)

        # Валидация категории
        if result.get("category") not in VALID_CATEGORIES:
            result["category"] = "General"

        stats[f"{model_label}_calls"] += 1

        # Гибрид: если Haiku не уверен (<70%) и ещё не Sonnet — пересылаем Sonnet
        if not use_sonnet and result.get("confidence", 0) < 70:
            logger.info("Haiku не уверен, переключаюсь на Sonnet")
            return analyze_with_claude(merchant, message, use_sonnet=True)

        return result

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Ошибка {model}: {e}")
        if not use_sonnet:
            return analyze_with_claude(merchant, message, use_sonnet=True)
        return {
            "confidence": 0, "should_escalate": True,
            "category": "General", "priority": "Normal",
            "response_to_merchant": "Спасибо за обращение! Специалист свяжется с вами.",
            "escalation_summary": f"Ошибка AI. Сообщение: {message}"
        }


# ═══════════════════════════════════════════════════════════════════════════
# ГОЛОСОВЫЕ СООБЩЕНИЯ
# ═══════════════════════════════════════════════════════════════════════════

async def transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Скачивает голосовое и транскрибирует через Whisper."""
    if not OPENAI_API_KEY:
        return None
    try:
        voice = update.message.voice or update.message.audio
        if not voice:
            return None

        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Whisper API
        with open(tmp_path, "rb") as audio_file:
            r = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": audio_file},
                data={"model": "whisper-1"}
            )
        os.unlink(tmp_path)

        if r.status_code == 200:
            text = r.json().get("text", "")
            stats["voice_messages"] += 1
            logger.info(f"Голосовое транскрибировано: {text[:50]}...")
            return text
    except Exception as e:
        logger.error(f"Ошибка транскрибации: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS — МЕРЧАНТЫ
# ═══════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    tg_id = update.effective_user.id

    # Если уже агент — не сбрасываем
    if tg_id in agent_sessions:
        role = agent_sessions[tg_id]["role"]
        name = agent_sessions[tg_id]["name"]
        await update.message.reply_text(f"👋 {name}, вы вошли как {role.upper()}.")
        return

    merchant = merchant_cache.get(tg_id) or search_merchant_by_telegram_id(tg_id)
    if merchant:
        merchant_cache[tg_id] = merchant
        user_states[tg_id] = "identified"
        await update.message.reply_text(
            f"👋 С возвращением, {merchant['name']}!\n\n"
            f"Чем могу помочь? Опишите проблему или отправьте голосовое."
        )
    else:
        user_states[tg_id] = "awaiting_code"
        await update.message.reply_text(
            "👋 Здравствуйте! Я AI-ассистент Infinity Pay.\n\n"
            "Введите ваш персональный код.\n"
            "Код выглядит так: *INF-001*\n\n"
            "_(Код был отправлен вам при подключении к Infinity Pay)_",
            parse_mode="Markdown"
        )


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /login CODE — вход для агентов и ISO."""
    tg_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "🔐 Для входа используйте:\n`/login AGENT-001`\n\nКод выдаётся администратором.",
            parse_mode="Markdown"
        )
        return

    code = args[0].upper().strip()
    if code in AGENT_CODES:
        info = AGENT_CODES[code]
        agent_sessions[tg_id] = {
            "role": info["role"],
            "name": info["name"],
            "clickup_id": info.get("clickup_id"),
            "tg_id": tg_id,
        }
        user_states[tg_id] = info["role"]
        role_label = "🛡️ Агент" if info["role"] == "agent" else "👑 ISO Owner"
        await update.message.reply_text(
            f"✅ Вход выполнен!\n\n"
            f"{role_label}: *{info['name']}*\n\n"
            f"Доступные команды:\n"
            f"/stats — статистика бота\n"
            f"/assign TICKET_ID @агент — назначить тикет\n"
            f"/close_session — закрыть свою сессию\n"
            f"/logout — выйти",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Неверный код. Обратитесь к администратору.")


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /logout — выход агента."""
    tg_id = update.effective_user.id
    if tg_id in agent_sessions:
        name = agent_sessions[tg_id]["name"]
        del agent_sessions[tg_id]
        user_states.pop(tg_id, None)
        await update.message.reply_text(f"👋 {name}, вы вышли из системы.")
    else:
        await update.message.reply_text("Вы не авторизованы. Используйте /login CODE")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика (только для агентов/ISO)."""
    tg_id = update.effective_user.id
    if tg_id not in agent_sessions:
        await update.message.reply_text("🔒 Только для авторизованных агентов.")
        return

    s = stats
    text = (
        f"📊 *Статистика бота*\n\n"
        f"💬 Всего сообщений: {s['total_messages']}\n"
        f"🎫 Тикетов создано: {s['tickets_created']}\n"
        f"🤖 AI ответил сам: {s['ai_direct_answers']}\n"
        f"⬆️ Эскалаций: {s['escalations']}\n"
        f"🎙 Голосовых: {s['voice_messages']}\n\n"
        f"*AI вызовы:*\n"
        f"⚡ Haiku: {s['haiku_calls']}\n"
        f"🧠 Sonnet: {s['sonnet_calls']}\n"
        f"💰 Экономия: ~{s['haiku_calls'] * 90}% дешевле без гибрида"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голосовых сообщений."""
    tg_id = update.effective_user.id

    # Антиспам
    if is_spam(tg_id):
        return

    if not OPENAI_API_KEY:
        await update.message.reply_text(
            "🎙 Голосовые сообщения пока не поддерживаются. Напишите текстом."
        )
        return

    await update.message.reply_text("🎙 Распознаю голосовое...")
    text = await transcribe_voice(update, context)

    if text:
        await update.message.reply_text(f"📝 Распознано: _{text}_", parse_mode="Markdown")
        # Обрабатываем как текстовое сообщение
        update.message.text = text
        await handle_message(update, context)
    else:
        await update.message.reply_text("❌ Не удалось распознать голосовое. Попробуйте текстом.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений."""
    tg_id = update.effective_user.id
    message_text = update.message.text.strip()
    state = user_states.get(tg_id, "unknown")
    stats["total_messages"] += 1

    # Антиспам
    if is_spam(tg_id):
        await update.message.reply_text("⚠️ Слишком много сообщений. Подождите минуту.")
        return

    # ── Агент/ISO обработка ────────────────────────────────────────────────
    if tg_id in agent_sessions:
        await handle_agent_message(update, context, message_text)
        return

    # ── Ожидаем код ────────────────────────────────────────────────────────
    if state == "awaiting_code":
        code = message_text.upper().strip()
        await update.message.reply_text("🔍 Проверяю код...")
        merchant = search_merchant_by_code(code)
        if merchant:
            save_telegram_id_to_merchant(merchant["task_id"], tg_id)
            merchant["telegram_id"] = str(tg_id)
            merchant_cache[tg_id] = merchant
            user_states[tg_id] = "identified"
            await update.message.reply_text(
                f"✅ *Идентификация успешна!*\n\n"
                f"Добро пожаловать, *{merchant['name']}*!\n"
                f"MID: `{merchant['mid']}`\n\n"
                f"Опишите проблему или отправьте голосовое 🎙",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Код *{code}* не найден.\nПроверьте и попробуйте ещё раз.",
                parse_mode="Markdown"
            )
        return

    # ── Не идентифицирован ─────────────────────────────────────────────────
    if state not in ("identified",):
        merchant = search_merchant_by_telegram_id(tg_id)
        if merchant:
            merchant_cache[tg_id] = merchant
            user_states[tg_id] = "identified"
        else:
            user_states[tg_id] = "awaiting_code"
            await update.message.reply_text(
                "Введите ваш код Infinity Pay (например: *INF-001*)",
                parse_mode="Markdown"
            )
            return

    # ── Идентифицирован — обработка ────────────────────────────────────────
    merchant = merchant_cache.get(tg_id)
    if not merchant:
        merchant = search_merchant_by_telegram_id(tg_id)
        if not merchant:
            user_states[tg_id] = "awaiting_code"
            await update.message.reply_text("Введите ваш код Infinity Pay:")
            return
        merchant_cache[tg_id] = merchant

    # ── Сессия: проверяем есть ли активная ─────────────────────────────────
    session = get_session(tg_id)
    session["messages"].append(message_text)

    # Если есть активный тикет — добавляем комментарий вместо нового тикета
    if session.get("ticket_id"):
        add_comment_to_ticket(session["ticket_id"], f"[Мерчант] {message_text}")
        await update.message.reply_text(
            "📝 Сообщение добавлено к вашему обращению. Ожидайте ответа."
        )
        return

    await update.message.reply_text("⏳ Обрабатываю запрос...")

    # Анализ через гибридный AI
    full_message = "\n".join(session["messages"])
    analysis = analyze_with_claude(merchant, full_message)

    logger.info(
        f"[{merchant['name']}] confidence={analysis['confidence']} "
        f"escalate={analysis['should_escalate']} category={analysis['category']}"
    )

    if not analysis["should_escalate"] and analysis["confidence"] >= 85:
        stats["ai_direct_answers"] += 1
        await update.message.reply_text(analysis["response_to_merchant"])
        close_session(tg_id)
    else:
        stats["escalations"] += 1
        ticket_id = create_support_ticket(merchant, full_message, analysis)
        if ticket_id:
            session["ticket_id"] = ticket_id
            emoji = PRIORITY_EMOJI.get(analysis.get("priority", "Normal"), "🟡")
            await update.message.reply_text(
                f"✅ *Ваш запрос принят!*\n\n"
                f"{emoji} Приоритет: *{analysis.get('priority')}*\n"
                f"📁 Категория: *{analysis.get('category')}*\n\n"
                f"Специалист свяжется с вами в течение рабочего дня.\n"
                f"Номер: `{ticket_id[:8]}`\n\n"
                f"_Можете дополнить обращение — просто напишите ещё._",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "✅ Запрос получен. Специалист свяжется с вами."
            )


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS — АГЕНТЫ/ISO
# ═══════════════════════════════════════════════════════════════════════════

async def _create_staff_task(update: Update, agent: dict, task_text: str):
    """Создаёт задачу в ClickUp от имени любого сотрудника."""
    if not task_text:
        await update.message.reply_text("Укажите описание задачи.")
        return

    assigned_agent = get_least_loaded_agent()
    payload = {
        "name": f"📋 [{agent['name']}] {task_text[:80]}",
        "description": f"Задача от {agent['name']}:\n\n{task_text}",
        "priority": 2,
        "assignees": [assigned_agent["id"]],
    }
    r = requests.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS, json=payload
    )
    if r.status_code in (200, 201):
        task_id = r.json()["id"]
        await update.message.reply_text(
            f"✅ Задача создана!\n"
            f"📝 {task_text[:80]}\n"
            f"👤 Назначено: *{assigned_agent['name']}*\n"
            f"🔖 ID: `{task_id[:8]}`",
            parse_mode="Markdown"
        )
        if SUPPORT_GROUP_CHAT_ID:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": SUPPORT_GROUP_CHAT_ID,
                    "text": f"📋 *Новая задача*\n\n"
                            f"👤 {agent['name']}\n"
                            f"📝 {task_text}\n"
                            f"➡️ Назначено: {assigned_agent['name']}",
                    "parse_mode": "Markdown",
                }
            )
    else:
        await update.message.reply_text("❌ Ошибка создания задачи в ClickUp.")


async def handle_agent_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """AI-powered обработка сообщений от агентов/ISO."""
    tg_id = update.effective_user.id
    agent = agent_sessions[tg_id]

    # ── Явная команда /task ────────────────────────────────────────────────
    if text.startswith("/task "):
        task_text = text[6:].strip()
        await _create_staff_task(update, agent, task_text)
        return

    if text.strip() == "/task":
        await update.message.reply_text(
            "📝 Опишите задачу:\n`/task Нужно поменять фото у Iflowers`",
            parse_mode="Markdown"
        )
        return

    # ── AI понимает любой текст от сотрудника ─────────────────────────────
    system_prompt = (
        "Ты умный ассистент службы поддержки Infinity Pay Inc. (ISO, процессор Tekcard, POS Clover).\n"
        "Сотрудник пишет тебе сообщение. Определи намерение и ответь ТОЛЬКО валидным JSON без markdown:\n"
        '{"intent": "task" или "question" или "other", '
        '"task_title": "краткое название задачи", '
        '"task_description": "подробное описание", '
        '"priority": число 1-4, '
        '"answer": "ответ если question/other"}\n'
        "Приоритеты: 1=urgent, 2=high, 3=normal, 4=low\n"
        "Если сотрудник описывает проблему мерчанта или задачу — intent=task.\n"
        "Если задаёт вопрос — intent=question."
    )
    try:
        resp = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Сотрудник ({agent['name']}) написал: {text}"}]
        )
        import json as _json
        raw = resp.content[0].text.strip()
        # Убираем markdown-обёртку если есть
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = _json.loads(raw)
        intent = data.get("intent", "other")

        if intent == "task":
            title = data.get("task_title", text[:80])
            desc = data.get("task_description", text)
            await update.message.reply_text("🔄 Понял, создаю задачу в ClickUp...")
            await _create_staff_task(update, agent, f"{title}\n\n{desc}")
        else:
            answer = data.get("answer", "")
            if answer:
                await update.message.reply_text(answer)
            else:
                await update.message.reply_text(
                    f"👋 {agent['name']}, используйте команды:\n\n"
                    f"/task описание — создать задачу\n"
                    f"/stats — статистика\n"
                    f"/logout — выйти"
                )
    except Exception as e:
        logging.error(f"handle_agent_message AI error: {e}")
        await update.message.reply_text(
            f"👋 {agent['name']}, используйте команды:\n\n"
            f"/task описание — создать задачу\n"
            f"/stats — статистика\n"
            f"/logout — выйти"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    tg_id = update.effective_user.id
    if tg_id in agent_sessions:
        await update.message.reply_text(
            "🛡️ *Команды агента/ISO:*\n\n"
            "/stats — статистика\n"
            "/task описание — создать задачу (ISO)\n"
            "/logout — выйти",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "📞 *Infinity Pay Support*\n\n"
            "Я могу помочь с:\n"
            "• Clover POS\n• Транзакции\n• Тех. проблемы\n• Выписки\n\n"
            "💬 Напишите текст или 🎙 отправьте голосовое!",
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════════════════════════════════════════
# CLICKUP WEBHOOK — уведомления при смене статуса
# ═══════════════════════════════════════════════════════════════════════════

async def check_ticket_updates(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка обновлений тикетов (каждые 2 мин)."""
    try:
        # Получаем недавно обновлённые тикеты
        r = requests.get(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
            headers=CLICKUP_HEADERS,
            params={
                "include_closed": True,
                "order_by": "updated",
                "reverse": True,
                "subtasks": False,
                "page": 0,
            }
        )
        if r.status_code != 200:
            return

        tasks = r.json().get("tasks", [])
        for task in tasks[:20]:
            status_name = task.get("status", {}).get("status", "").lower()
            task_id = task["id"]
            task_name = task["name"]

            # Ищем Telegram ID мерчанта в описании
            desc = task.get("description", "")
            tg_id = None
            if "Telegram ID:** " in desc:
                try:
                    tg_part = desc.split("Telegram ID:** ")[1].split("\n")[0].strip()
                    tg_id = int(tg_part) if tg_part.isdigit() else None
                except:
                    pass

            if not tg_id:
                continue

            # Проверяем — уведомляли ли уже
            cache_key = f"notified_{task_id}_{status_name}"
            if cache_key in faq_cache:
                continue

            # Отправляем уведомление
            status_emoji = {"closed": "✅", "complete": "✅", "resolved": "✅",
                           "in progress": "🔄", "review": "👀"}.get(status_name, "📌")

            if status_name in ("closed", "complete", "resolved", "in progress", "review"):
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=f"{status_emoji} *Обновление по вашему обращению*\n\n"
                             f"Статус: *{status_name.title()}*\n"
                             f"Тикет: `{task_id[:8]}`\n\n"
                             f"{'Bash вопрос решён Если нужно что-то ещё — напишите.' if 'close' in status_name or 'complete' in status_name else 'Наш специалист работает над вашим вопросом.'}",
                        parse_mode="Markdown"
                    )
                    faqfaq_cache[cache_key] = {"answer": "", "hits": 0, "last_used": time.time()}

                    # Уведомляем в группу
                    if SUPPORT_GROUP_CHAT_ID:
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": SUPPORT_GROUP_CHAT_ID,
                                "text": f"{status_emoji} Тикет `{task_id[:8]}` → *{status_name.title()}*",
                                "parse_mode": "Markdown",
                            }
                        )
                except Exception as e:
                    logger.error(f"Ошибка уведомления мерчанта {tg_id}: {e}")

            # Проверяем комментарии от команды для пересылки мерчанту
            try:
                cr = requests.get(
                    f"{CLICKUP_BASE}/task/{task_id}/comment",
                    headers=CLICKUP_HEADERS
                )
                if cr.status_code == 200:
                    comments = cr.json().get("comments", [])
                    for comment in comments[-3:]:
                        comment_text = comment.get("comment_text", "")
                        comment_id = comment.get("id", "")
                        cache_key_c = f"comment_{comment_id}"
                        if cache_key_c in faq_cache:
                            continue
                        if comment_text and not comment_text.startswith("[Мерчант]"):
                            try:
                                await context.bot.send_message(
                                    chat_id=tg_id,
                                    text=f"💬 *Ответ от поддержки:*\n\n{comment_text}",
                                    parse_mode="Markdown"
                                )
                                faq_cache[cache_key_c] = {"answer": "", "hits": 0, "last_used": time.time()}
                            except:
                                pass
            except:
                pass

    except Exception as e:
        logger.error(f"Ошибка проверки тикетов: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("\n═══════════════════════════════════════════")
    print("  Infinity Pay Bot v2 — Starting...")
    print("═══════════════════════════════════════════\n")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # Голосовые
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # Текстовые
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Периодическая проверка тикетов (каждые 2 мин)
    app.job_queue.run_repeating(check_ticket_updates, interval=120, first=30)

    print("✅ Бот v2 запущен. Ctrl+C для остановки.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

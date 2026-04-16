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
import signal
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from anthropic import Anthropic
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# ─── Загружаем .env ───────────────────────────────────────────────────────
load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
CLAUDE_API_KEY  = os.environ["CLAUDE_API_KEY"]
CLICKUP_TOKEN   = os.environ["CLICKUP_API_TOKEN"]
CLICKUP_LIST_TICKETS   = os.environ["CLICKUP_LIST_TICKETS_ID"]
CLICKUP_LIST_MERCHANTS = os.environ["CLICKUP_LIST_MERCHANTS_ID"]

# Telegram группа поддержки (chat_id, задаётся в .env)
SUPPORT_GROUP_CHAT_ID = os.environ.get("SUPPORT_GROUP_CHAT_ID", "")

# OpenAI API для Whisper (голосовые)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

CLICKUP_HEADERS = {
    "Authorization": CLICKUP_TOKEN,
    "Content-Type": "application/json"
}
CLICKUP_BASE = "https://api.clickup.com/api/v2"

# ─── ClickUp Custom Field IDs (из clickup_ids.json) ─────────────────────
TICKET_FIELDS = {
    "source":         "cce340eb-1ad3-4393-99db-8a4479a4adf8",
    "merchant":       "a1748265-3769-4961-8a97-68f4c790b5ee",
    "mid":            "6b12ba3e-96a6-4068-9eaa-1cba547558ce",
    "category":       "98e62955-2751-45ed-a00a-4d8889e0c09e",
    "priority_level": "aaae7c35-5cbf-4325-be9c-d358b5654ab8",
    "channel":        "688d4913-337f-4f97-bada-3653dcee743c",
    "phone":          "67b7f5f3-2ebb-4b64-9d3f-f87c0a09b4bb",
}

# ─── Dropdown option UUIDs для ClickUp ───────────────────────────────────
CHANNEL_OPTIONS = {
    "Telegram":  "3aff0664-7a5a-4d05-965b-619f0b73f195",
    "WhatsApp":  "66413fde-ef0c-4ca2-a2b1-1acd51827cbb",
    "Phone":     "d825e952-dfc4-4bc9-b820-f271c67c9553",
    "Email":     "0c4530dc-7fd0-4708-b2a9-9ae077e4584a",
    "Internal":  "78b88569-2682-4268-92fa-75f8f7555811",
}
# Маппинг AI-категорий → ClickUp option UUIDs
CATEGORY_OPTIONS = {
    "Hardware":    "056486a2-7b72-4128-951d-dac6ea73acf0",
    "Terminal":    "056486a2-7b72-4128-951d-dac6ea73acf0",  # → Hardware
    "Software":    "2f026484-3968-46e6-978b-7cd1f104a4dd",
    "Statement":   "d9d74adf-84ee-4ac6-a801-7a1252b0bf9a",
    "Payment":     "d2dbf95f-012b-4be7-b990-b3590a984b6d",
    "Account":     "dd3b3139-6def-4003-8222-81611780fa6d",
    "Billing":     "dd3b3139-6def-4003-8222-81611780fa6d",  # → Account
    "Chargeback":  "dd3b3139-6def-4003-8222-81611780fa6d",  # → Account
    "Fraud":       "dd3b3139-6def-4003-8222-81611780fa6d",  # → Account
    "Compliance":  "dd3b3139-6def-4003-8222-81611780fa6d",  # → Account
    "General":     "a00d022d-9004-4158-bec4-e8fd416fba25",  # → Other
    "Other":       "a00d022d-9004-4158-bec4-e8fd416fba25",
}
PRIORITY_OPTIONS = {
    "Urgent": "9bcf9882-3a61-44b6-ac3c-fd2955629fe7",
    "High":   "0beb79b6-4b84-459a-9cc2-34785c4de7ac",
    "Normal": "22316d4f-a89d-4a0d-990b-e36381295228",
    "Low":    "17d14a60-9a6c-4ec3-bb2a-e27b6016235f",
}
SOURCE_OPTIONS = {
    "Merchant Request": "4a39b4c9-a214-4eff-8226-65209281280a",
    "Internal Task":    "06558cbf-04ce-486c-b32e-2f95de77136b",
}
# ID поля "Мерчант" (short_text) — отдельно от "Merchant" (text)
MERCHANT_SHORT_TEXT_FIELD_ID = "459abe18-91a9-4968-bd84-6c95257ebdd4"

# ─── Саппорт-команда ─────────────────────────────────────────────────────
SUPPORT_AGENTS = [
    {"id": 94469635, "name": "Support 1"},
    {"id": 94469636, "name": "Support 2"},
]

# ─── Секретные коды для логина агентов/ISO ────────────────────────────────
_agent_code = os.environ.get("AGENT_CODE_AGENT", "IAMAGENT")
_iso_code   = os.environ.get("AGENT_CODE_ISO", "ISO-MASTER")
AGENT_CODES = {
    _agent_code: {"role": "agent", "name": "Infinity Pay Staff", "clickup_id": None},
    _iso_code:   {"role": "iso",   "name": "Shams (ISO Owner)",  "clickup_id": None},
}

# ─── AI клиенты ──────────────────────────────────────────────────────────
anthropic_client = Anthropic(api_key=CLAUDE_API_KEY)

# ─── Приоритеты с эмодзи ────────────────────────────────────────────────
PRIORITY_EMOJI = {
    "Urgent": "🔴",
    "High":   "🟠",
    "Normal": "🟡",
    "Low":    "🟢",
}
PRIORITY_MAP = {"Urgent": 1, "High": 2, "Normal": 3, "Low": 4}

# ─── Категории (без "Other") ────────────────────────────────────────────
VALID_CATEGORIES = [
    "Terminal", "Payment", "Chargeback", "Statement",
    "Billing", "Account", "Software", "Hardware",
    "Fraud", "Compliance", "General"
]

# ─── Хранилище состояний (в памяти) ──────────────────────────────────────
user_states     = {}  # {tg_id: "awaiting_code"|"identified"|"agent"|"iso"}
merchant_cache  = {}  # {tg_id: merchant_data}
agent_sessions  = {}  # {tg_id: {"role": "agent"|"iso", "name": ..., ...}}

# ─── Сессии сообщений (антидубль) ────────────────────────────────────────
# {tg_id: {"messages": [...], "last_time": timestamp, "ticket_id": str|None}}
message_sessions = {}
SESSION_TIMEOUT = 600  # 10 минут

# ─── FAQ кеш ─────────────────────────────────────────────────────────────
faq_cache = {}  # {"вопрос_хеш": {"answer": str, "hits": int, "last_used": ts}}
FAQ_CACHE_MAX = 200
FAQ_CACHE_TTL = 86400  # 24 часа — записи старше удаляются

# ─── Кеш уведомлений (отдельно от FAQ) ───────────────────────────────────
notification_cache = {}  # {"notified_TASKID_STATUS": timestamp, "comment_ID": timestamp}
NOTIFICATION_CACHE_TTL = 86400  # 24 часа

# ─── Антиспам ────────────────────────────────────────────────────────────
spam_tracker = {}  # {tg_id: {"count": int, "first_msg": timestamp}}

# ticket_id -> tg_id mapping (replaces fragile description text parsing)
ticket_to_tg = {}  # {clickup_ticket_id: tg_id (int)}
SPAM_LIMIT  = 10   # макс 10 сообщений за 60 сек
SPAM_WINDOW = 60

# addmerchant dialog state (agent/ISO only)
addmerchant_state = {}  # {tg_id: {"step": "name"|"mid"|"phone", "name": str, ...}}

# Persistence
STATE_FILE = Path("data/state.json")

# Clover
CLOVER_BASE = os.environ.get("CLOVER_BASE_URL", "https://api.clover.com")

# ─── Статистика ──────────────────────────────────────────────────────────
stats = {
    "total_messages":   0,
    "tickets_created":  0,
    "ai_direct_answers": 0,
    "escalations":      0,
    "voice_messages":   0,
    "haiku_calls":      0,
    "sonnet_calls":     0,
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
        "messages":       [],
        "last_time":      now,
        "ticket_id":      None,
        "awaiting_choice": False,
        "awaiting_phone":  False,
        "phone_number":    None,
        "mode":           None,   # "self_help" | "support" | None
    }
    return message_sessions[tg_id]


def close_session(tg_id: int):
    """Мягко закрывает сессию — сбрасывает тикет и режим."""
    if tg_id in message_sessions:
        message_sessions[tg_id]["ticket_id"] = None
        message_sessions[tg_id]["awaiting_choice"] = False
        message_sessions[tg_id]["mode"] = None


def cleanup_notification_cache():
    """Удаляет старые записи из кеша уведомлений."""
    now = time.time()
    expired = [k for k, v in notification_cache.items()
               if now - v > NOTIFICATION_CACHE_TTL]
    for k in expired:
        del notification_cache[k]


def cleanup_faq_cache():
    """Удаляет старые записи из FAQ кеша."""
    now = time.time()
    expired = [k for k, v in faq_cache.items()
               if now - v.get("last_used", 0) > FAQ_CACHE_TTL]
    for k in expired:
        del faq_cache[k]
    # Если всё ещё слишком большой — удаляем самые старые
    if len(faq_cache) > FAQ_CACHE_MAX:
        sorted_keys = sorted(faq_cache, key=lambda k: faq_cache[k].get("last_used", 0))
        for k in sorted_keys[:len(faq_cache) - FAQ_CACHE_MAX]:
            del faq_cache[k]



# Persistence functions
def load_state():
    """Load merchant_cache, ticket_to_tg, notification_cache from disk."""
    global merchant_cache, ticket_to_tg, notification_cache
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            merchant_cache.update({int(k): v for k, v in data.get('merchant_cache', {}).items()})
            ticket_to_tg.update(data.get('ticket_to_tg', {}))
            notification_cache.update(data.get('notification_cache', {}))
            logger.info(f'State loaded: {len(merchant_cache)} merchants, {len(ticket_to_tg)} tickets')
    except Exception as e:
        logger.error(f'Failed to load state: {e}')


def save_state():
    """Save critical state to disk."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'merchant_cache': {str(k): v for k, v in merchant_cache.items()},
            'ticket_to_tg': ticket_to_tg,
            'notification_cache': notification_cache,
            'saved_at': datetime.utcnow().isoformat(),
        }
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        logger.error(f'Failed to save state: {e}')


def parse_ai_json(text: str) -> dict:
    """Надёжный парсер JSON из AI-ответа (снимает markdown-обёртку)."""
    raw = text.strip()
    # Снимаем ```json ... ``` обёртку
    if raw.startswith("```"):
        # Убираем первую строку (```json) и последнюю (```)
        lines = raw.split("\n")
        # Находим начало и конец блока
        start = 1  # пропускаем ```json
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        raw = "\n".join(lines[start:end]).strip()
    # Пробуем JSON
    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════════
# CLICKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def get_least_loaded_agent() -> dict:
    """Возвращает агента с наименьшим количеством открытых тикетов."""
    agent_loads = []
    for agent in SUPPORT_AGENTS:
        try:
            r = httpx.get(
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
        r = httpx.get(
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
        r = httpx.get(
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
        "task_id":       task["id"],
        "name":          task["name"].split(" | MID:")[0].strip(),
        "mid":           "",
        "phone":         "",
        "email":         "",
        "address":       "",
        "business_type": "",
        "unique_code":   "",
        "telegram_id":   "",
        "clover_merchant_id": "",
        "clover_access_token": "",
    }
    field_map = {
        "MID":           "mid",
        "Phone":         "phone",
        "Email":         "email",
        "Address":       "address",
        "Business Type": "business_type",
        "Unique Code":   "unique_code",
        "Telegram ID":   "telegram_id",
        "Clover MID":    "clover_merchant_id",
        "Clover Token":  "clover_access_token",
    }
    for field in task.get("custom_fields", []):
        key = field_map.get(field.get("name", ""))
        if key:
            data[key] = field.get("value", "") or ""
    return data


def save_telegram_id_to_merchant(task_id: str, telegram_id: int):
    """Сохраняет Telegram ID в карточку мерчанта."""
    r = httpx.get(f"{CLICKUP_BASE}/task/{task_id}", headers=CLICKUP_HEADERS)
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
    r = httpx.post(
        f"{CLICKUP_BASE}/task/{task_id}/field/{tg_field_id}",
        headers=CLICKUP_HEADERS,
        json={"value": str(telegram_id)}
    )
    return r.status_code in (200, 201)


def create_support_ticket(merchant: dict, message: str, ai_analysis: dict, phone: str = None) -> str | None:
    """Создаёт тикет в ClickUp с custom fields."""
    priority = PRIORITY_MAP.get(ai_analysis.get("priority", "Normal"), 3)
    assigned_agent = get_least_loaded_agent()
    category       = ai_analysis.get("category", "General")
    priority_label = ai_analysis.get("priority", "Normal")
    emoji          = PRIORITY_EMOJI.get(priority_label, "🟡")

    # Используем AI-резюме для названия тикета
    summary    = ai_analysis.get("escalation_summary", "")
    task_title = summary[:80] if summary else message[:80]
    task_name  = f"{emoji} [{category}] {merchant['name']} — {task_title}"

    # Описание — только текст сообщения и AI резюме (остальное в custom fields)
    phone_line = f"\n📞 **Телефон для связи:** {phone}" if phone else ""
    description = f"""📩 **Сообщение мерчанта:**
{message}

---
📋 **AI Резюме:** {ai_analysis.get('escalation_summary', '')}
🤖 Уверенность: {ai_analysis.get('confidence')}%
👤 Назначено: {assigned_agent['name']}{phone_line}
"""

    # Custom fields — dropdown поля нужно отправлять как option UUID
    cat_uuid = CATEGORY_OPTIONS.get(category, CATEGORY_OPTIONS.get("Other", ""))
    pri_uuid = PRIORITY_OPTIONS.get(priority_label, PRIORITY_OPTIONS.get("Normal", ""))
    src_uuid = SOURCE_OPTIONS.get("Merchant Request", "")
    chn_uuid = CHANNEL_OPTIONS.get("Telegram", "")

    custom_fields = [
        {"id": TICKET_FIELDS["merchant"],        "value": merchant['name']},
        {"id": MERCHANT_SHORT_TEXT_FIELD_ID,     "value": merchant['name']},   # "Мерчант" short_text
        {"id": TICKET_FIELDS["mid"],             "value": merchant.get('mid', '')},
    ]
    if cat_uuid:
        custom_fields.append({"id": TICKET_FIELDS["category"],       "value": cat_uuid})
    if pri_uuid:
        custom_fields.append({"id": TICKET_FIELDS["priority_level"], "value": pri_uuid})
    if src_uuid:
        custom_fields.append({"id": TICKET_FIELDS["source"],         "value": src_uuid})
    if chn_uuid:
        custom_fields.append({"id": TICKET_FIELDS["channel"],        "value": chn_uuid})
    if phone:
        custom_fields.append({"id": TICKET_FIELDS["phone"], "value": phone})

    payload = {
        "name":          task_name,
        "description":   description,
        "priority":      priority,
        "assignees":     [assigned_agent["id"]],
        "custom_fields": custom_fields,
    }

    r = httpx.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )

    if r.status_code in (200, 201):
        task = r.json()
        ticket_id = task["id"]
        logger.info(f"Тикет создан: {ticket_id}")
        stats["tickets_created"] += 1

        # Store ticket -> tg_id for reliable notification routing (replaces description parsing)
        tg_id_val = merchant.get("telegram_id")
        if tg_id_val:
            try:
                ticket_to_tg[ticket_id] = int(tg_id_val)
            except (ValueError, TypeError):
                pass
        save_state()

        # Дублируем в TG-группу поддержки
        if SUPPORT_GROUP_CHAT_ID:
            try:
                phone_notify = f"\n📞 *Телефон:* {phone}" if phone else ""
                notify_text = (
                    f"🆕 *Новый тикет*\n\n"
                    f"{emoji} *Приоритет:* {priority_label}\n"
                    f"📁 *Категория:* {category}\n"
                    f"🏪 *Мерчант:* {merchant['name']}\n"
                    f"🆔 *MID:* {merchant['mid']}\n"
                   f"👤 *Назначен:* {assigned_agent['name']}{phone_notify}\n\n"
                    f"💬 *ообщение:*\n{message[:300]}\n\n"
                    f"📋 *AI Резюме:*\n{ai_analysis.get('escalation_summary', 'N/A')}\n\n"
                    f"🔗 Тикет ID: `{ticket_id}`"
                )
                httpx.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id":    SUPPORT_GROUP_CHAT_ID,
                        "text":       notify_text,
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
    r = httpx.post(
        f"{CLICKUP_BASE}/task/{ticket_id}/comment",
        headers=CLICKUP_HEADERS,
        json={"comment_text": comment}
    )
    return r.status_code in (200, 201)


async def _create_and_confirm_ticket(update: Update, session: dict, merchant: dict, phone: str = None):
    """Создаёт тикет в ClickUp и уведомляет мерчанта."""
    analysis = session.get("pending_analysis") or session.get("last_analysis") or {}
    full_message = "\n".join(session.get("messages", []))

    # Если анализа нет — делаем быстрый
    if not analysis:
        analysis = analyze_with_claude(merchant, full_message)

    await update.message.reply_text("⏳ Создаю заявку...")

    ticket_id = create_support_ticket(merchant, full_message, analysis, phone)

    if ticket_id:
        session["ticket_id"] = ticket_id
        session["pending_analysis"] = None
        priority = analysis.get("priority", "Normal")
        category = analysis.get("category", "General")
        emoji = PRIORITY_EMOJI.get(priority, "🟡")

        await update.message.reply_text(
            f"✅ *Заявка принята!*\n\n"
            f"{emoji} Приоритет: *{priority}*\n"
            f"📁 Категория: *{category}*\n"
            f"🔖 Номер: `{ticket_id[:8]}`\n\n"
            f"Специалист свяжется с вами в ближайшее время.\n"
            f"Если нужно добавить информацию — просто напишите.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось создать заявку.\n"
            "Напишите напрямую: 📧 Support@infinitypay.us"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AI — ГИБРИД HAIKU/SONNET
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """Ты AI-ассистент поддержки Infinity Pay Inc. — ISO в сфере платёжных услуг.
Процессор: Tekcard. POS: Clover.

Мерчант: {name} | MID: {mid} | Бизнес: {business_type}

ПРАВИЛА:
- Определи язык мерчанта и отвечай ТОЛЬКО на нём (RU/EN/TJ/UZ/AR/ES).
- Понимай уличный/разговорный стиль, сленг, смешанный язык.
- Будь кратким, дружелюбным, по делу. Не растягивай ответ.
- ОТВЕЧАЙ СРАЗУ если уверенность >85%. Давай конкретные шаги решения.
- ЭСКАЛИРУЙ (should_escalate=true) если: чарджбеки, закрытие аккаунта, ставки/rates, возвраты >$500, фрод/PCI, смена банковских реквизитов.
- НИКОГДА не делись данными других мерчантов.
- НИКОГДА не называй ставки (rates) без одобрения владельца ISO.
- НИКОГДА не проси номера карт, SSN, банковские данные.
- Подозрительная активность (>$7,000 в ресторане с обычным чеком $30-60) — ставь should_escalate=true, priority="High".

Категории ТОЛЬКО из списка: Terminal, Payment, Chargeback, Statement, Billing, Account, Software, Hardware, Fraud, Compliance, General

JSON ответ:
{{"confidence":0-100,"should_escalate":true/false,"category":"<из списка>","priority":"Urgent|High|Normal|Low","response_to_merchant":"текст ответа мерчанту","escalation_summary":"краткое резюме для команды","clover_intent":null|"sales_query"|"order_query"|"menu_change","clover_item":""}}"""



# Clover API helpers
def _clover_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_clover_sales_today(merchant):
    mid = merchant.get("clover_merchant_id", "")
    token = merchant.get("clover_access_token", "")
    if not mid or not token:
        return None
    try:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start.timestamp() * 1000)
        r = httpx.get(
            f"{CLOVER_BASE}/v3/merchants/{mid}/orders",
            headers=_clover_headers(token),
            params={"filter": f"createdTime>={start_ms} AND paymentState=PAID",
                    "limit": 1000},
            timeout=10
        )
        if r.status_code != 200:
            return None
        orders = r.json().get("elements", [])
        total_usd = sum(o.get("total", 0) for o in orders) / 100
        return f"{len(orders)} orders, ${total_usd:,.2f} today"
    except Exception as e:
        logger.error(f"Clover sales: {e}")
        return None


def get_clover_last_order(merchant):
    mid = merchant.get("clover_merchant_id", "")
    token = merchant.get("clover_access_token", "")
    if not mid or not token:
        return None
    try:
        r = httpx.get(
            f"{CLOVER_BASE}/v3/merchants/{mid}/orders",
            headers=_clover_headers(token),
            params={"orderBy": "createdTime DESC", "limit": 1, "expand": "lineItems"},
            timeout=10
        )
        if r.status_code != 200:
            return None
        orders = r.json().get("elements", [])
        if not orders:
            return "No orders found"
        o = orders[0]
        total = o.get("total", 0) / 100
        ts = o.get("createdTime", 0)
        dt = datetime.utcfromtimestamp(ts / 1000).strftime("%d.%m %H:%M")
        items = o.get("lineItems", {}).get("elements", [])
        names = ", ".join(it.get("name", "?") for it in items[:5])
        return f"Last order ({dt}): ${total:.2f} | {names or 'no details'}"
    except Exception as e:
        logger.error(f"Clover last order: {e}")
        return None


def toggle_clover_item(merchant, item_name, enable):
    mid = merchant.get("clover_merchant_id", "")
    token = merchant.get("clover_access_token", "")
    if not mid or not token:
        return None
    try:
        r = httpx.get(
            f"{CLOVER_BASE}/v3/merchants/{mid}/items",
            headers=_clover_headers(token),
            timeout=10
        )
        if r.status_code != 200:
            return None
        all_items = r.json().get("elements", [])
        matches = [it for it in all_items if item_name.lower() in it.get("name", "").lower()]
        if not matches:
            return f"Item not found: {item_name}"
        item = matches[0]
        r2 = httpx.post(
            f"{CLOVER_BASE}/v3/merchants/{mid}/items/{item['id']}",
            headers=_clover_headers(token),
            json={"hidden": not enable},
            timeout=10
        )
        if r2.status_code in (200, 201):
            action = "enabled" if enable else "disabled"
            return f"Item '{item['name']}' {action}"
        return None
    except Exception as e:
        logger.error(f"Clover toggle: {e}")
        return None


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

        # Надёжный парсинг JSON из AI-ответа
        result = parse_ai_json(text)

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
            "confidence": 0,
            "should_escalate": True,
            "category": "General",
            "priority": "Normal",
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
            r = httpx.post(
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
            f"👋 *{merchant['name']}*, добро пожаловать!\n\n"
            f"Опишите проблему текстом или отправьте голосовое 🎤",
            parse_mode="Markdown"
        )
    else:
        user_states[tg_id] = "awaiting_code"
        await update.message.reply_text(
            "👋 Здравствуйте! Я AI-ассистент *Infinity Pay*.\n\n"
            "Для начала введите ваш персональный код.\n"
            "Пример: *INF-001*\n\n"
            "_(Код был отправлен при подключении к Infinity Pay)_",
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
            "role":      info["role"],
            "name":      info["name"],
            "clickup_id": info.get("clickup_id"),
            "tg_id":     tg_id,
        }
        user_states[tg_id] = info["role"]

        role_label = "🛡️ Агент" if info["role"] == "agent" else "👑 ISO Owner"
        await update.message.reply_text(
            f"✅ Вход выполнен!\n\n"
            f"{role_label}: *{info['name']}*\n\n"
            f"Просто напишите задачу или вопрос — AI поймёт.\n\n"
            f"Команды:\n"
            f"/stats — статистика бота\n"
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
        pending_agent_tasks.pop(tg_id, None)
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


async def close_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /close_session — закрыть текущую сессию."""
    tg_id = update.effective_user.id
    close_session(tg_id)
    await update.message.reply_text("✅ Сессия закрыта. Можете начать новое обращение.")


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

    # ── Агент/ISO обработка ──────────────────────────────────────────────
    if tg_id in agent_sessions:
        await handle_agent_message(update, context, message_text)
        return

    # ── Ожидаем код ──────────────────────────────────────────────────────
    if state == "awaiting_code":
        code = message_text.upper().strip()
        await update.message.reply_text("🔍 Проверяю код...")
        merchant = search_merchant_by_code(code)
        if merchant:
            save_telegram_id_to_merchant(merchant["task_id"], tg_id)
            merchant["telegram_id"] = str(tg_id)
            merchant_cache[tg_id] = merchant
            save_state()
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

    # ── Не идентифицирован ───────────────────────────────────────────────
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

    # ── Идентифицирован — обработка ──────────────────────────────────────
    merchant = merchant_cache.get(tg_id)
    if not merchant:
        merchant = search_merchant_by_telegram_id(tg_id)
        if not merchant:
            user_states[tg_id] = "awaiting_code"
            await update.message.reply_text("Введите ваш код Infinity Pay:")
            return
        merchant_cache[tg_id] = merchant

    # ── Сессия: проверяем есть ли активная ───────────────────────────────
    session = get_session(tg_id)

    # Если есть активный тикет — добавляем комментарий
    if session.get("ticket_id"):
        session["messages"].append(message_text)
        add_comment_to_ticket(session["ticket_id"], f"[Мерчант] {message_text}")
        await update.message.reply_text(
            "📝 Сообщение добавлено к вашему обращению. Ожидайте ответа."
        )
        return

    # ── Ожидаем телефон для создания тикета ────────────────────────────
    if session.get("awaiting_phone"):
        session["awaiting_phone"] = False
        phone = message_text.strip()
        if phone.lower() in ("пропустить", "skip", "нет", "no", "-", "0"):
            phone = None
        else:
            session["phone_number"] = phone
        await _create_and_confirm_ticket(update, session, merchant, phone)
        return

    # ── Если AI уже ответил — проверяем, хочет ли мерчант саппорт ──────
    if session.get("mode") == "self_help":
        escalation_triggers = ("саппорт", "support", "заявка", "2", "не помогло",
                               "не работает", "всё равно", "все равно", "не понял",
                               "не понятно", "создай заявку", "нужен человек")
        msg_lower = message_text.lower().strip()
        if msg_lower in escalation_triggers or any(t in msg_lower for t in escalation_triggers):
            session["mode"] = "support"
            session["awaiting_phone"] = True
            await update.message.reply_text(
                "📞 Хорошо, создам заявку для специалиста!\n\n"
                "Укажите телефон для связи или напишите *пропустить*:",
                parse_mode="Markdown"
            )
            return
        # Новый вопрос — сбрасываем режим, анализируем заново
        session["mode"] = None
        session["messages"] = []
        session["last_analysis"] = None

    # ── Мерчант пишет сообщение — AI сразу анализирует ──────────────────
    session["messages"].append(message_text)
    full_message = "\n".join(session["messages"])

    # Clover intent check
    if merchant.get("clover_merchant_id") and merchant.get("clover_access_token"):
        msg_lower = message_text.lower()
        sales_kw = ["sales", "revenue", "today", "продажи", "выручка", "заказы сегодня"]
        order_kw = ["last order", "latest order", "последний заказ"]
        toggle_kw = ["disable", "enable", "turn off", "turn on", "выключи", "включи", "убрать из меню", "добавить в меню"]
        clover_resp = None
        if any(kw in msg_lower for kw in sales_kw):
            clover_resp = get_clover_sales_today(merchant)
        elif any(kw in msg_lower for kw in order_kw):
            clover_resp = get_clover_last_order(merchant)
        elif any(kw in msg_lower for kw in toggle_kw):
            enable = any(kw in msg_lower for kw in ["включи", "enable", "turn on", "добавить"])
            clover_resp = toggle_clover_item(merchant, message_text, enable)
        if clover_resp:
            await update.message.reply_text(clover_resp)
            return

    # AI анализирует сразу
    await update.message.reply_text("⏳ Анализирую...")
    analysis = analyze_with_claude(merchant, full_message)
    confidence = analysis.get("confidence", 0)
    should_escalate = analysis.get("should_escalate", False)

    if confidence >= 85 and not should_escalate:
        # AI уверен — отвечает сам
        stats["ai_direct_answers"] += 1
        session["mode"] = "self_help"
        session["last_analysis"] = analysis
        await update.message.reply_text(analysis["response_to_merchant"])
        await update.message.reply_text(
            "💡 Помогло? Если нет — напишите *саппорт* и создадим заявку.",
            parse_mode="Markdown"
        )
    else:
        # Нужен саппорт — спрашиваем телефон и создаём тикет
        stats["escalations"] += 1
        session["mode"] = "support"
        session["awaiting_phone"] = True
        session["pending_analysis"] = analysis
        await update.message.reply_text(
            "📞 Понял! Создаю заявку для команды.\n\n"
            "Укажите телефон для связи или напишите *пропустить*:",
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════════════════════════════════════════
# ADDMERCHANT — создание новых мерчантов
# ═══════════════════════════════════════════════════════════════════════════

def generate_unique_merchant_code() -> str:
    """Генерирует следующий свободный код INF-XXX."""
    page = 0
    max_num = 0
    while True:
        r = httpx.get(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_MERCHANTS}/task",
            headers=CLICKUP_HEADERS,
            params={"include_closed": False, "page": page, "subtasks": False}
        )
        if r.status_code != 200:
            break
        tasks = r.json().get("tasks", [])
        if not tasks:
            break
        for task in tasks:
            for field in task.get("custom_fields", []):
                if field.get("name") == "Unique Code":
                    val = field.get("value", "")
                    if val and val.upper().startswith("INF-"):
                        try:
                            num = int(val.split("-")[1])
                            max_num = max(max_num, num)
                        except Exception:
                            pass
        if len(tasks) < 100:
            break
        page += 1
    return f"INF-{max_num + 1:03d}"


def create_merchant_in_clickup(name: str, mid: str, phone: str, code: str) -> str | None:
    """Создаёт карточку мерчанта в ClickUp."""
    MERCHANT_FIELD_IDS = {
        "MID":         "6b12ba3e-96a6-4068-9eaa-1cba547558ce",
        "Phone":       "67b7f5f3-2ebb-4b64-9d3f-f87c0a09b4bb",
        "Unique Code": "be7d8b56-8466-4328-aee8-08ea04cb8295",
        "Telegram ID": "48e0b107-75f9-41b4-beb6-cecc0e9d9b0d",
        "Contact Name":"a1e9331d-feaa-4e33-97d6-9de70848de6a",
    }
    task_name = f"{name} | MID: {mid}" if mid else name
    custom_fields = [
        {"id": MERCHANT_FIELD_IDS["Unique Code"], "value": code},
    ]
    if mid:
        custom_fields.append({"id": MERCHANT_FIELD_IDS["MID"],   "value": mid})
    if phone:
        custom_fields.append({"id": MERCHANT_FIELD_IDS["Phone"], "value": phone})

    payload = {"name": task_name, "custom_fields": custom_fields}
    r = httpx.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_MERCHANTS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )
    if r.status_code in (200, 201):
        return r.json()["id"]
    logger.error(f"Ошибка создания мерчанта: {r.status_code} {r.text}")
    return None


async def addmerchant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /addmerchant — добавить нового мерчанта (только ISO/агент)."""
    tg_id = update.effective_user.id
    if tg_id not in agent_sessions:
        await update.message.reply_text(
            "🔒 Только для агентов/ISO.\nВойдите через /login CODE"
        )
        return
    addmerchant_state[tg_id] = {"step": "name"}
    await update.message.reply_text(
        "➕ *Добавление нового мерчанта*\n\n"
        "Шаг 1/3 — Введите *название бизнеса*:\n"
        "_(например: Pizza Palace или Ресторан Самарканд)_",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS — АГЕНТЫ/ISO
# ═══════════════════════════════════════════════════════════════════════════

# ─── Ожидающие задачи от сотрудников (для диалога с телефоном) ────────────
pending_agent_tasks = {}  # tg_id -> {"task_data": {...}, "step": "phone", "created_at": ts}

AGENT_AI_PROMPT = """Ты умный ассистент Infinity Pay Inc. (ISO, процессор Tekcard, POS Clover).
Сотрудник пишет сообщение. Проанализируй ГЛУБОКО и извлеки данные.

ОБЯЗАТЕЛЬНО определи:
1. intent — "task" если описывает проблему/задачу/просьбу, "question" если вопрос, "other"
2. merchant_name — ТОЧНОЕ название мерчанта если упоминается, иначе "Не указан"
3. task_title — КРАТКОЕ название задачи (макс 60 символов)
4. task_description — ПОДРОБНОЕ описание что нужно сделать
5. priority — 1=urgent(срочно), 2=high(важно), 3=normal, 4=low(не срочно)
6. category — одна из: Clover POS, Фото/Меню, Документы, Транзакции, Тех.проблема, Обновление данных, Биллинг, Оборудование, Другое
7. answer — ответ если question/other

Примеры:
"Нужно поменять пару фоток у Iflowers срочно"
→ {"intent":"task","merchant_name":"Iflowers","task_title":"Замена фотографий","task_description":"Заменить несколько фотографий у мерчанта Iflowers","priority":1,"category":"Фото/Меню","answer":""}

"У Pizza Palace не проходят транзакции"
→ {"intent":"task","merchant_name":"Pizza Palace","task_title":"Не проходят транзакции","task_description":"У мерчанта Pizza Palace не проходят транзакции. Требуется диагностика процессинга.","priority":1,"category":"Транзакции","answer":""}

Ответь ТОЛЬКО JSON без markdown."""


async def _create_clickup_task(agent: dict, task_data: dict, phone: str = None):
    """Создаёт задачу в ClickUp с custom fields."""
    merchant    = task_data.get("merchant_name", "Не указан")
    title       = task_data.get("task_title", "Новая задача")
    description = task_data.get("task_description", "")
    priority    = task_data.get("priority", 3)
    category    = task_data.get("category", "Другое")

    priority_map = {1: ("🔥", "Urgent"), 2: ("🟠", "High"), 3: ("🟡", "Normal"), 4: ("🟢", "Low")}
    emoji, priority_label = priority_map.get(priority, ("🟡", "Normal"))

    # ── Название задачи — чистое и понятное ──
    task_name = f"{emoji} {title}"

    # ── Описание — только суть задачи ──
    desc_parts = [f"📋 **Задача от {agent['name']}**\n"]
    desc_parts.append(f"📝 {description}")
    if phone:
        desc_parts.append(f"\n📞 **Телефон для связи:** {phone}")

    # ── Тег мерчанта — для фильтрации ──
    tags = []
    if merchant != "Не указан":
        tags.append(merchant.lower().strip())

    assigned_agent = get_least_loaded_agent()

    # ── Custom fields — dropdown поля как option UUID ──
    cat_uuid = CATEGORY_OPTIONS.get(category, CATEGORY_OPTIONS.get("Other", ""))
    pri_uuid = PRIORITY_OPTIONS.get(priority_label, PRIORITY_OPTIONS.get("Normal", ""))
    src_uuid = SOURCE_OPTIONS.get("Internal Task", "")
    chn_uuid = CHANNEL_OPTIONS.get("Telegram", "")

    custom_fields = [
        {"id": TICKET_FIELDS["merchant"],       "value": merchant},
    ]
    if cat_uuid:
        custom_fields.append({"id": TICKET_FIELDS["category"],       "value": cat_uuid})
    if pri_uuid:
        custom_fields.append({"id": TICKET_FIELDS["priority_level"], "value": pri_uuid})
    if src_uuid:
        custom_fields.append({"id": TICKET_FIELDS["source"],         "value": src_uuid})
    if chn_uuid:
        custom_fields.append({"id": TICKET_FIELDS["channel"],        "value": chn_uuid})
    if phone:
        custom_fields.append({"id": TICKET_FIELDS["phone"], "value": phone})

    payload = {
        "name":          task_name,
        "description":   "\n".join(desc_parts),
        "priority":      priority,
        "assignees":     [assigned_agent["id"]],
        "tags":          tags,
        "custom_fields": custom_fields,
    }

    r = httpx.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )

    if r.status_code in (200, 201):
        task_id = r.json()["id"]
        return {
            "success":        True,
            "task_id":        task_id,
            "assigned_to":    assigned_agent["name"],
            "emoji":          emoji,
            "priority_label": priority_label,
            "merchant":       merchant,
            "title":          title,
            "category":       category,
            "phone":          phone,
        }
    else:
        logger.error(f"ClickUp error: {r.status_code} {r.text}")
        return {"success": False}


async def handle_agent_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """AI-powered: понимает текст, спрашивает телефон, создаёт задачу."""
    tg_id = update.effective_user.id
    agent = agent_sessions[tg_id]

    # ── /addmerchant dialog ──────────────────────────────────────────────
    if tg_id in addmerchant_state:
        state = addmerchant_state[tg_id]
        step  = state.get("step")

        if step == "name":
            state["name"] = text.strip()
            state["step"] = "mid"
            await update.message.reply_text(
                f"✅ Название: *{state['name']}*\n\n"
                f"Шаг 2/3 — Введите *MID* (Merchant ID):\n"
                f"_(только цифры, например: 12345678)_\n\n"
                f"Или напишите *пропустить* если MID ещё не назначен",
                parse_mode="Markdown"
            )
            return

        elif step == "mid":
            val = text.strip()
            state["mid"] = "" if val.lower() in ("пропустить", "skip", "-", "нет") else val
            state["step"] = "phone"
            await update.message.reply_text(
                f"✅ MID: *{state['mid'] or 'не указан'}*\n\n"
                f"Шаг 3/3 — Введите *телефон* мерчанта:\n"
                f"_(например: +13471234567)_\n\n"
                f"Или напишите *пропустить*",
                parse_mode="Markdown"
            )
            return

        elif step == "phone":
            val = text.strip()
            state["phone"] = "" if val.lower() in ("пропустить", "skip", "-", "нет") else val

            name  = state["name"]
            mid   = state.get("mid", "")
            phone = state.get("phone", "")

            await update.message.reply_text("⏳ Создаю мерчанта в системе...")
            code    = generate_unique_merchant_code()
            task_id = create_merchant_in_clickup(name, mid, phone, code)

            del addmerchant_state[tg_id]

            if task_id:
                await update.message.reply_text(
                    f"✅ *Мерчант добавлен!*\n\n"
                    f"🏪 *{name}*\n"
                    f"🆔 MID: `{mid or 'не указан'}`\n"
                    f"📞 Телефон: {phone or 'не указан'}\n\n"
                    f"🔑 *Персональный код для бота:*\n`{code}`\n\n"
                    f"Отправьте этот код мерчанту — он вводит его в боте при первом входе.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка создания мерчанта в ClickUp. Попробуйте ещё раз /addmerchant"
                )
            return

    # ── Шаг 2: ожидаем телефон ───────────────────────────────────────────
    if tg_id in pending_agent_tasks:
        pending = pending_agent_tasks[tg_id]

        # Пропустить
        if text.lower() in ("нет", "пропустить", "skip", "no", "-", "0"):
            task_data = pending["task_data"]
            result = await _create_clickup_task(agent, task_data, phone=None)
        else:
            # Принимаем как телефон
            phone = text.strip()
            task_data = pending["task_data"]
            result = await _create_clickup_task(agent, task_data, phone=phone)

        del pending_agent_tasks[tg_id]

        if result.get("success"):
            await update.message.reply_text(
                f"✅ *Задача создана в ClickUp!*\n\n"
                f"{result['emoji']} *{result['title']}*\n"
                f"🏪 Мерчант: *{result['merchant']}* (тег)\n"
                f"⚡ Приоритет: {result['emoji']} {result['priority_label']}\n"
                f"📂 Категория: {result['category']}\n"
                f"👤 Назначено: *{result['assigned_to']}*\n"
                f"{'📞 Телефон: ' + result['phone'] if result.get('phone') else '📞 Без телефона'}\n"
                f"🔖 ID: `{result['task_id'][:8]}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Ошибка создания задачи в ClickUp.")
        return

    # ── Шаг 1: AI анализирует текст ─────────────────────────────────────
    try:
        resp = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=AGENT_AI_PROMPT,
            messages=[{"role": "user", "content": f"Сотрудник ({agent['name']}) написал: {text}"}]
        )

        raw = resp.content[0].text.strip()
        data = parse_ai_json(raw)
        intent = data.get("intent", "other")

        if intent == "task":
            merchant = data.get("merchant_name", "Не указан")
            title = data.get("task_title", text[:60])

            priority_map = {1: "🔥 Urgent", 2: "🟠 High", 3: "🟡 Normal", 4: "🟢 Low"}
            p = data.get("priority", 3)

            # Сохраняем и спрашиваем телефон
            pending_agent_tasks[tg_id] = {
                "task_data": data,
                "created_at": time.time(),
            }

            await update.message.reply_text(
                f"📋 *Новая задача:*\n\n"
                f"📝 {title}\n"
                f"🏪 Мерчант: *{merchant}*\n"
                f"⚡ Приоритет: {priority_map.get(p, '🟡 Normal')}\n"
                f"📂 Категория: {data.get('category', 'Другое')}\n\n"
                f"📞 *Укажите номер телефона мерчанта для обратной связи*\n"
                f"(или напишите *нет* чтобы пропустить)",
                parse_mode="Markdown"
            )

        elif intent == "question":
            answer = data.get("answer", "Не удалось найти ответ.")
            await update.message.reply_text(answer)

        else:
            answer = data.get("answer", "")
            if answer:
                await update.message.reply_text(answer)
            else:
                await update.message.reply_text(
                    f"💡 {agent['name']}, просто напишите задачу или вопрос:\n\n"
                    f"• _Поменять фото у Iflowers срочно_\n"
                    f"• _У Pizza Palace не работает терминал_\n"
                    f"• _Как проверить статус транзакции?_\n\n"
                    f"/stats /logout",
                    parse_mode="Markdown"
                )

    except Exception as e:
        logger.error(f"Agent AI error: {e}")
        await update.message.reply_text(
            f"⚠️ Ошибка AI. Попробуйте ещё раз.\n/stats /logout"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    tg_id = update.effective_user.id
    if tg_id in agent_sessions:
        await update.message.reply_text(
            "🛡️ *Команды агента/ISO:*\n\n"
            "Просто напишите задачу или вопрос — AI поймёт.\n\n"
            "/stats — статистика\n"
            "/logout — выйти\n"
            "/close\\_session — закрыть сессию",
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
        # Чистим старые записи из кешей
        cleanup_notification_cache()
        cleanup_faq_cache()

        # Чистим старые pending_agent_tasks (>30 мин)
        now = time.time()
        expired_pending = [k for k, v in pending_agent_tasks.items()
                          if now - v.get("created_at", 0) > 1800]
        for k in expired_pending:
            del pending_agent_tasks[k]

        # Получаем недавно обновлённые тикеты
        r = httpx.get(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
            headers=CLICKUP_HEADERS,
            params={
                "include_closed": True,
                "order_by":       "updated",
                "reverse":        True,
                "subtasks":       False,
                "page":           0,
            }
        )

        if r.status_code != 200:
            return

        tasks = r.json().get("tasks", [])

        for task in tasks[:20]:
            status_name = task.get("status", {}).get("status", "").lower()
            task_id     = task["id"]
            task_name   = task["name"]

            # Ищем Telegram ID мерчанта в описании
            # Use ticket_to_tg mapping (populated at ticket creation)
            tg_id = ticket_to_tg.get(task_id)

            if not tg_id:
                continue

            # Проверяем — уведомляли ли уже (через отдельный кеш)
            cache_key = f"notified_{task_id}_{status_name}"
            if cache_key in notification_cache:
                continue

            # Отправляем уведомление
            status_emoji = {
                "closed": "✅", "complete": "✅", "resolved": "✅",
                "in progress": "🔄", "review": "👀"
            }.get(status_name, "📌")

            if status_name in ("closed", "complete", "resolved", "in progress", "review"):
                is_closed = "close" in status_name or "complete" in status_name or "resolved" in status_name
                status_text = (
                    "Ваш вопрос решён! Если нужно что-то ещё — напишите."
                    if is_closed
                    else "Наш специалист работает над вашим вопросом."
                )
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=f"{status_emoji} *Обновление по вашему обращению*\n\n"
                             f"Статус: *{status_name.title()}*\n"
                             f"Тикет: `{task_id[:8]}`\n\n"
                             f"{status_text}",
                        parse_mode="Markdown"
                    )
                    notification_cache[cache_key] = time.time()

                    # Уведомляем в группу
                    if SUPPORT_GROUP_CHAT_ID:
                        httpx.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id":    SUPPORT_GROUP_CHAT_ID,
                                "text":       f"{status_emoji} Тикет `{task_id[:8]}` → *{status_name.title()}*",
                                "parse_mode": "Markdown",
                            }
                        )

                    # Если тикет закрыт — сбрасываем сессию мерчанта
                    if is_closed:
                        close_session(tg_id)

                except Exception as e:
                    logger.error(f"Ошибка уведомления мерчанта {tg_id}: {e}")

            # Проверяем комментарии от команды для пересылки мерчанту
            try:
                cr = httpx.get(
                    f"{CLICKUP_BASE}/task/{task_id}/comment",
                    headers=CLICKUP_HEADERS
                )
                if cr.status_code == 200:
                    comments = cr.json().get("comments", [])
                    for comment in comments[-3:]:
                        comment_text = comment.get("comment_text", "")
                        comment_id   = comment.get("id", "")
                        cache_key_c  = f"comment_{comment_id}"
                        if cache_key_c in notification_cache:
                            continue
                        if comment_text and not comment_text.startswith("[Мерчант]") and not comment_text.startswith("[INTERNAL]"):
                            try:
                                await context.bot.send_message(
                                    chat_id=tg_id,
                                    text=f"💬 *Ответ от поддержки:*\n\n{comment_text}",
                                    parse_mode="Markdown"
                                )
                                notification_cache[cache_key_c] = time.time()
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
    print(" Infinity Pay Bot v2 — Starting...")
    print("═══════════════════════════════════════════\n")


    load_state()

    def _sigterm(signum, frame):
        logger.info("SIGTERM: saving state...")
        save_state()
        import sys; sys.exit(0)
    signal.signal(signal.SIGTERM, _sigterm)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("close_session", close_session_command))
    app.add_handler(CommandHandler("addmerchant", addmerchant_command))

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

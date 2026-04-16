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

# Кеш полей ClickUp — обновляется при старте и по требованию
_clickup_fields_cache = {"tickets": None, "tickets_fetched_at": 0}
_CLICKUP_FIELDS_TTL = 3600  # 1 час


def get_ticket_fields(force: bool = False) -> dict:
    """Динамически получает все custom fields листа тикетов.
    Ключ — имя поля в lowercase, значение — {id, type, options: {name_lower: uuid}}.
    """
    now = time.time()
    if (not force and _clickup_fields_cache["tickets"] is not None
            and now - _clickup_fields_cache["tickets_fetched_at"] < _CLICKUP_FIELDS_TTL):
        return _clickup_fields_cache["tickets"]
    try:
        r = httpx.get(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/field",
            headers=CLICKUP_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            logger.error(f"get_ticket_fields: {r.status_code} {r.text}")
            return _clickup_fields_cache["tickets"] or {}
        result = {}
        for f in r.json().get("fields", []):
            name = (f.get("name") or "").strip()
            if not name:
                continue
            options = {}
            for opt in (f.get("type_config") or {}).get("options", []) or []:
                opt_name = (opt.get("name") or "").strip().lower()
                opt_uuid = opt.get("id")
                opt_order = opt.get("orderindex")
                if opt_name and (opt_uuid is not None or opt_order is not None):
                    options[opt_name] = {"uuid": opt_uuid, "orderindex": opt_order}
            result[name.lower()] = {
                "id":      f.get("id"),
                "type":    f.get("type"),
                "name":    name,
                "options": options,
            }
        _clickup_fields_cache["tickets"] = result
        _clickup_fields_cache["tickets_fetched_at"] = now
        logger.info(f"ClickUp поля загружены ({len(result)}): {list(result.keys())}")
        # Логируем опции dropdown полей для дебага
        for name, meta in result.items():
            if meta.get("options"):
                logger.info(f"  └─ {name} (dropdown): {list(meta['options'].keys())}")
        return result
    except Exception as e:
        logger.error(f"get_ticket_fields exception: {e}")
        return _clickup_fields_cache["tickets"] or {}


def build_custom_field(name_candidates: list, value, dropdown: bool = False) -> dict | None:
    """Ищет поле по списку возможных имён и возвращает payload элемент для custom_fields.
    Для dropdown возвращает {"id", "value" (uuid), "orderindex", "field_name", "_dropdown": True, "_option_label": ...}.
    Для текста — {"id", "value"}.
    """
    fields = get_ticket_fields()
    if not fields:
        return None
    field = None
    for nm in name_candidates:
        f = fields.get(nm.lower())
        if f:
            field = f
            break
    if not field:
        return None
    if dropdown:
        val_key = str(value).strip().lower()
        match = field["options"].get(val_key)
        matched_label = val_key if match else None
        if match is None:
            # Попробуем частичное совпадение (игнорируем эмодзи/пробелы)
            import re
            norm_val = re.sub(r"[^a-zа-я0-9]", "", val_key)
            for opt_name, opt_meta in field["options"].items():
                norm_opt = re.sub(r"[^a-zа-я0-9]", "", opt_name)
                if norm_val and norm_opt and (norm_val in norm_opt or norm_opt in norm_val):
                    match = opt_meta
                    matched_label = opt_name
                    break
        if match is None:
            logger.warning(
                f"Dropdown '{field['name']}' option '{value}' не найден. "
                f"Доступные: {list(field['options'].keys())}"
            )
            return None
        return {
            "id": field["id"],
            "value": match.get("uuid"),
            "orderindex": match.get("orderindex"),
            "field_name": field["name"],
            "_option_label": matched_label,
            "_dropdown": True,
        }
    return {"id": field["id"], "value": str(value), "field_name": field["name"]}

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

# ─── Короткие ID тикетов для агентов ─────────────────────────────────────
# T-001, T-002... легко произносить и набирать
short_to_clickup = {}  # {"T-042": "86b9f8a1..."}
clickup_to_short = {}  # обратное — {"86b9f8a1": "T-042"}
ticket_counter = 0     # последний использованный номер


def next_short_ticket_id() -> str:
    """Генерирует следующий короткий ID: T-001, T-002..."""
    global ticket_counter
    ticket_counter += 1
    return f"T-{ticket_counter:03d}"


def register_ticket_short_id(clickup_id: str) -> str:
    """Регистрирует короткий ID для ClickUp тикета. Идемпотентно."""
    if clickup_id in clickup_to_short:
        return clickup_to_short[clickup_id]
    sid = next_short_ticket_id()
    short_to_clickup[sid] = clickup_id
    clickup_to_short[clickup_id] = sid
    save_state()
    return sid


def resolve_ticket_id(ref: str) -> str | None:
    """Принимает T-042 / t042 / полный ClickUp ID / последние 8 символов.
    Возвращает ClickUp ID или None.
    """
    if not ref:
        return None
    r = ref.strip().upper().replace(" ", "")
    # Нормализуем "t42" → "T-042", "T42" → "T-042"
    import re as _re
    m = _re.match(r"^T-?(\d+)$", r)
    if m:
        key = f"T-{int(m.group(1)):03d}"
        return short_to_clickup.get(key)
    # Полный ClickUp ID
    if ref in clickup_to_short:
        return ref
    # Последние 8 символов (префикс) — поиск по известным
    r_lower = ref.lower()
    for cid in clickup_to_short:
        if cid.lower().startswith(r_lower) or cid.lower().endswith(r_lower):
            return cid
    return None
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
    """Load merchant_cache, ticket_to_tg, notification_cache, short IDs from disk."""
    global merchant_cache, ticket_to_tg, notification_cache, short_to_clickup, clickup_to_short, ticket_counter
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            merchant_cache.update({int(k): v for k, v in data.get('merchant_cache', {}).items()})
            ticket_to_tg.update(data.get('ticket_to_tg', {}))
            notification_cache.update(data.get('notification_cache', {}))
            short_to_clickup.update(data.get('short_to_clickup', {}))
            clickup_to_short.update(data.get('clickup_to_short', {}))
            ticket_counter = data.get('ticket_counter', 0)
            logger.info(
                f'State loaded: {len(merchant_cache)} merchants, '
                f'{len(ticket_to_tg)} tickets, short_ids counter={ticket_counter}'
            )
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
            'short_to_clickup': short_to_clickup,
            'clickup_to_short': clickup_to_short,
            'ticket_counter': ticket_counter,
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


_RU_TO_EN = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z',
    'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'sch',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}
# Обратная (одно-к-одному, неоднозначные берём самые частые)
_EN_TO_RU = {
    'a':'а','b':'б','c':'к','d':'д','e':'е','f':'ф','g':'г','h':'х','i':'и',
    'j':'дж','k':'к','l':'л','m':'м','n':'н','o':'о','p':'п','q':'к','r':'р',
    's':'с','t':'т','u':'у','v':'в','w':'в','x':'кс','y':'й','z':'з',
}

def _translit_ru_to_en(s: str) -> str:
    return "".join(_RU_TO_EN.get(ch, ch) for ch in s.lower())

def _translit_en_to_ru(s: str) -> str:
    # Обрабатываем частые диграфы СНАЧАЛА
    s = s.lower()
    for di, ru in [("zh","ж"),("kh","х"),("ts","ц"),("ch","ч"),("sh","ш"),("yu","ю"),("ya","я"),("sch","щ"),("yo","ё")]:
        s = s.replace(di, ru)
    return "".join(_EN_TO_RU.get(ch, ch) for ch in s)


def search_merchants_by_name(query: str, limit: int = 5) -> list:
    """Fuzzy поиск мерчантов по имени.
    Возвращает список совпадений (до `limit`), отсортированных по релевантности.
    Пробует ОРИГИНАЛ + транслитерацию (рус↔лат) чтобы понять 'Тандури' = 'Tandoori'.
    """
    import re
    if not query or not query.strip():
        return []
    q_raw = query.strip().lower()
    q_norm = re.sub(r"[^a-zа-я0-9]+", "", q_raw)
    if not q_norm:
        return []

    # Варианты запроса: оригинал + транслитерации (рус→лат и лат→рус)
    q_variants_raw = {q_raw, _translit_ru_to_en(q_raw), _translit_en_to_ru(q_raw)}
    q_variants_norm = {re.sub(r"[^a-zа-я0-9]+", "", v) for v in q_variants_raw}
    q_variants_norm = {v for v in q_variants_norm if v}

    # Токены (слова ≥3 символов) из всех вариантов
    q_tokens = set()
    for v in q_variants_raw:
        for t in re.split(r"[^a-zа-я0-9]+", v):
            if len(t) >= 3:
                q_tokens.add(t)

    import difflib
    exact_matches   = []
    startswith      = []
    contains        = []
    token_matches   = []
    fuzzy_matches   = []

    def _match_bucket(name_norm: str, name_tokens: set):
        """Определяет в какую корзину попадает имя. None если не совпало."""
        # Точное совпадение с любым вариантом
        if name_norm in q_variants_norm:
            return "exact"
        # Префикс (только если оба ≥4 символов, иначе слишком широко)
        for qn in q_variants_norm:
            if len(qn) >= 4 and len(name_norm) >= 4:
                if name_norm.startswith(qn) or qn.startswith(name_norm):
                    return "startswith"
        # Подстрока (только если длина ≥4)
        for qn in q_variants_norm:
            if len(qn) >= 4 and (qn in name_norm or name_norm in qn):
                return "contains"
        # Токены
        if q_tokens and name_tokens and (q_tokens & name_tokens):
            return "token"
        # Fuzzy по similarity ratio (обрабатывает опечатки типа tanduri/tandoori)
        for qn in q_variants_norm:
            if len(qn) >= 4 and len(name_norm) >= 4:
                ratio = difflib.SequenceMatcher(None, qn, name_norm).ratio()
                if ratio >= 0.75:
                    return "fuzzy"
        # Fuzzy по токенам — каждый токен запроса близок к какому-то токену имени
        if q_tokens and name_tokens:
            matched = 0
            for qt in q_tokens:
                if any(difflib.SequenceMatcher(None, qt, nt).ratio() >= 0.8 for nt in name_tokens):
                    matched += 1
            if matched == len(q_tokens):
                return "fuzzy"
        return None

    page = 0
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
            m = extract_merchant_data(task)
            name = (m.get("name") or "").lower()
            # Варианты имени: оригинал + транслитерации
            name_variants_raw = {name, _translit_ru_to_en(name), _translit_en_to_ru(name)}
            bucket = None
            for nv in name_variants_raw:
                nv_norm = re.sub(r"[^a-zа-я0-9]+", "", nv)
                if not nv_norm:
                    continue
                nv_tokens = set(t for t in re.split(r"[^a-zа-я0-9]+", nv) if len(t) >= 3)
                b = _match_bucket(nv_norm, nv_tokens)
                _order = ["exact","startswith","contains","token","fuzzy"]
                if b and (bucket is None or _order.index(b) < _order.index(bucket)):
                    bucket = b
                    if bucket == "exact":
                        break
            if bucket == "exact":
                exact_matches.append(m)
            elif bucket == "startswith":
                startswith.append(m)
            elif bucket == "contains":
                contains.append(m)
            elif bucket == "token":
                token_matches.append(m)
            elif bucket == "fuzzy":
                fuzzy_matches.append(m)
        if len(tasks) < 100:
            break
        page += 1

    combined = exact_matches + startswith + contains + token_matches + fuzzy_matches
    # Убираем дубли по task_id
    seen = set()
    unique = []
    for m in combined:
        if m["task_id"] not in seen:
            seen.add(m["task_id"])
            unique.append(m)
            if len(unique) >= limit:
                break
    return unique


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

    # Используем AI-сгенерированное ЧИСТОЕ название (без опечаток/сленга)
    # БЕЗ префиксов категории/мерчанта — они живут в отдельных custom fields.
    ticket_title = (ai_analysis.get("ticket_title")
                    or ai_analysis.get("escalation_summary")
                    or message)
    ticket_title = ticket_title.strip().replace("\n", " ")[:120]
    # Префикс эмодзи приоритета — видно цвет в списке задач ClickUp
    task_name = f"{emoji} {ticket_title}"

    # Описание — ПРОФЕССИОНАЛЬНОЕ описание от AI (что нужно саппорту сделать)
    # + оригинальный текст мерчанта для контекста.
    ai_desc = (ai_analysis.get("ticket_description")
               or ai_analysis.get("escalation_summary") or "").strip()
    original_msg = message.strip()
    if ai_desc and ai_desc != original_msg:
        description = f"{ai_desc}\n\n---\n📩 Original message from merchant:\n{original_msg}"
    else:
        description = original_msg or ai_desc

    # Custom fields — динамически находим ВСЕ подходящие поля в ClickUp
    merchant_name_variants = [merchant.get('name', '')]
    custom_fields = []

    # Мерчант — все возможные варианты названия поля
    for name_candidate in ["Merchant", "Мерчант", "Merchant Name", "Название мерчанта", "Мерчант Name"]:
        cf = build_custom_field([name_candidate], merchant.get('name', ''))
        if cf and not any(x["id"] == cf["id"] for x in custom_fields):
            custom_fields.append(cf)

    # MID
    cf = build_custom_field(["MID", "Merchant ID"], merchant.get('mid', ''))
    if cf: custom_fields.append(cf)

    # Category dropdown — маппинг AI-категорий → ClickUp options (с fallback)
    category_map = {
        "Terminal": "Hardware", "Billing": "Account", "Chargeback": "Account",
        "Fraud": "Account", "Compliance": "Account", "General": "Other",
    }
    cat_value = category_map.get(category, category)
    cf = build_custom_field(["Category", "Категория"], cat_value, dropdown=True)
    if cf: custom_fields.append(cf)

    # Priority Level dropdown
    cf = build_custom_field(
        ["Priority Level", "Priority", "Приоритет", "Уровень приоритета"],
        priority_label, dropdown=True
    )
    if cf: custom_fields.append(cf)

    # Source dropdown
    cf = build_custom_field(["Source", "Источник"], "Merchant Request", dropdown=True)
    if cf: custom_fields.append(cf)

    # Channel dropdown
    cf = build_custom_field(["Channel", "Канал"], "Telegram", dropdown=True)
    if cf: custom_fields.append(cf)

    # Phone
    if phone:
        cf = build_custom_field(["Phone", "Телефон"], phone)
        if cf: custom_fields.append(cf)

    # Разделяем: dropdowns ставим ОТДЕЛЬНО через /task/{id}/field/{id}
    # (bulk POST иногда молча теряет dropdown значения — ClickUp баг)
    dropdown_fields = [f for f in custom_fields if f.get("_dropdown")]
    plain_fields = [
        {"id": f["id"], "value": f["value"]}
        for f in custom_fields if not f.get("_dropdown")
    ]

    payload = {
        "name":          task_name,
        "description":   description,
        "priority":      priority,
        "assignees":     [assigned_agent["id"]],
        "custom_fields": plain_fields,
    }

    logger.info(
        f"Creating ticket: plain_fields={len(plain_fields)}, "
        f"dropdowns_deferred={len(dropdown_fields)} "
        f"({[(f.get('field_name'), f.get('_option_label')) for f in dropdown_fields]})"
    )

    r = httpx.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )

    if r.status_code in (200, 201):
        task = r.json()
        ticket_id = task["id"]
        short_id = register_ticket_short_id(ticket_id)
        logger.info(f"Тикет создан: {ticket_id} (short: {short_id})")
        stats["tickets_created"] += 1

        # Теперь ставим dropdown поля по одному — этот endpoint возвращает
        # реальные ошибки вместо тихого пропуска
        for df in dropdown_fields:
            field_id   = df["id"]
            field_name = df.get("field_name", field_id[:8])
            uuid_val   = df.get("value")
            order_val  = df.get("orderindex")
            url = f"{CLICKUP_BASE}/task/{ticket_id}/field/{field_id}"

            # Попытка 1: UUID
            ok = False
            if uuid_val:
                rr = httpx.post(url, headers=CLICKUP_HEADERS, json={"value": uuid_val})
                if rr.status_code in (200, 201):
                    logger.info(f"  ✓ {field_name} = {df.get('_option_label')} (uuid)")
                    ok = True
                else:
                    logger.warning(
                        f"  ✗ {field_name} uuid failed: {rr.status_code} {rr.text[:200]}"
                    )

            # Попытка 2: orderindex (integer)
            if not ok and order_val is not None:
                try:
                    order_int = int(order_val)
                except (TypeError, ValueError):
                    order_int = order_val
                rr = httpx.post(url, headers=CLICKUP_HEADERS, json={"value": order_int})
                if rr.status_code in (200, 201):
                    logger.info(f"  ✓ {field_name} = {df.get('_option_label')} (orderindex={order_int})")
                    ok = True
                else:
                    logger.error(
                        f"  ✗ {field_name} orderindex failed: {rr.status_code} {rr.text[:200]}"
                    )

            if not ok:
                logger.error(
                    f"  ✗✗ {field_name}: ВСЕ попытки провалились (uuid={uuid_val}, order={order_val})"
                )

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
    # Отсеиваем "мета"-сообщения (нет/саппорт/2 и т.п.) — это не часть проблемы
    META_WORDS = {
        "нет", "no", "не", "неа", "nope", "ne", "yox", "nein",
        "саппорт", "support", "заявка", "2", "не помог", "не помогло",
        "не помогает", "не работает", "не получилось", "не получается",
        "не понял", "не понятно", "позови человека", "нужен человек",
        "отдай саппорту", "отдай специалисту", "свяжитесь", "позвоните",
    }
    all_msgs = session.get("messages", [])
    problem_msgs = [m for m in all_msgs
                    if m.strip().lower() not in META_WORDS
                    and not (len(m.strip()) <= 6 and m.strip().lower() in META_WORDS)]
    if not problem_msgs:
        problem_msgs = all_msgs  # fallback: всё же лучше чем пусто

    problem_text = "\n".join(problem_msgs).strip() or "Обращение без деталей"

    await update.message.reply_text("⏳ Анализирую переписку и создаю заявку...")

    # Оборачиваем в явный контекст, чтобы Sonnet не путал "нет" с частью проблемы
    context_msg = (
        f"Мерчант обратился в поддержку Infinity Pay. Суть обращения:\n"
        f"«{problem_text}»\n\n"
        f"AI-бот попытался помочь, но мерчант попросил создать заявку "
        f"для специалиста (ответил отрицательно на вопрос 'Помогло?').\n\n"
        f"Задача: создай профессиональный тикет на русском. "
        f"В ticket_title — чистое название проблемы БЕЗ слов 'нет/саппорт/помогите'. "
        f"В ticket_description — что нужно сделать команде саппорта."
    )

    # ВСЕГДА используем Sonnet для тикета — он лучше чистит опечатки,
    # пишет профессиональное название и описание для команды саппорта.
    analysis = analyze_with_claude(merchant, context_msg, use_sonnet=True)

    # ── Post-processing safety: убираем мета-слова из ticket_title ──
    def _clean_title(t: str) -> str:
        import re
        if not t:
            return t
        t = t.strip().rstrip(".,!?")
        # Убираем trailing мета-слова ("...цены нет" → "...цены")
        for _ in range(3):
            m = re.search(r"[\s\-—,]+(нет|неа|no|nope|не помог[аело]*|не помогло|не работает|саппорт|support)\s*$",
                          t, flags=re.IGNORECASE)
            if not m:
                break
            t = t[:m.start()].rstrip(" -—,.")
        return t.strip()

    if analysis.get("ticket_title"):
        analysis["ticket_title"] = _clean_title(analysis["ticket_title"])
    if analysis.get("escalation_summary"):
        analysis["escalation_summary"] = _clean_title(analysis["escalation_summary"])

    # Если по анализу эскалация не нужна — всё равно создаём тикет
    if not analysis.get("escalation_summary"):
        analysis["escalation_summary"] = problem_text[:80]

    ticket_id = create_support_ticket(merchant, problem_text, analysis, phone)

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
- Понимай уличный/разговорный стиль, сленг, опечатки, смешанный язык, кашу из мыслей.
- Будь кратким, дружелюбным, по делу.
- ОТВЕЧАЙ СРАЗУ если уверенность >85%. Давай конкретные шаги решения.
- ЭСКАЛИРУЙ (should_escalate=true) если: чарджбеки, закрытие аккаунта, ставки/rates, возвраты >$500, фрод/PCI, смена банковских реквизитов.
- НИКОГДА не делись данными других мерчантов.
- НИКОГДА не называй ставки (rates) без одобрения владельца ISO.
- НИКОГДА не проси номера карт, SSN, банковские данные.
- Подозрительная активность (>$7,000 в ресторане с обычным чеком $30-60) — ставь should_escalate=true, priority="High".

ОПРЕДЕЛЕНИЕ ПРИОРИТЕТА — строго по словам-маркерам и смыслу:

🔴 Urgent — ПРЯМО СЕЙЧАС, СРОЧНО, бизнес стоит:
  Маркеры: "срочно", "сейчас", "прямо сейчас", "asap", "urgent", "не работает совсем", "терминал умер",
  "не могу принимать платежи", "клиенты ждут", "ничего не проходит", "всё сломалось",
  "сегодня нужно", "немедленно", "горит", "ЧП", "fraud", "украли", "подозрительная транзакция",
  "chargeback сегодня", "закрыли аккаунт". Также: "гоним", "быстро", "help asap".

🟠 High — ВАЖНО, сегодня-завтра, частично работает:
  Маркеры: "важно", "проблема", "не проходят транзакции иногда", "ошибка", "не работает [что-то одно]",
  "зависает", "глючит", "не печатает чеки", "не видит карту", "ошибка отказа", "declined",
  "нужно к вечеру", "до завтра", "устранить сегодня", "жалоба клиента".

🟡 Normal — обычная задача, нужно начинать работу:
  Маркеры: "поменять", "обновить", "добавить", "изменить меню/цены", "настроить",
  "подключить", "вопрос по", "как сделать", "можно ли", "нужна помощь с настройкой".

🟢 Low — не срочно, когда будет время:
  Маркеры: "когда будет время", "на днях", "не горит", "на следующей неделе",
  "для статистики", "на потом", "по возможности", "fyi", "справка".

Если мерчант явно НЕ указал срочность — по умолчанию Normal. НЕ ставь Low автоматически.

Категории ТОЛЬКО из списка: Terminal, Payment, Chargeback, Statement, Billing, Account, Software, Hardware, Fraud, Compliance, General

ТИКЕТ ДЛЯ КОМАНДЫ (если should_escalate=true) — ВСЁ НА АНГЛИЙСКОМ:
- "ticket_title" — CLEAN, professional English title, NO typos, NO meta-words ("please help/support/no"),
  the essence of the issue in one line (max 70 chars). Переводи на английский ДАЖЕ если мерчант писал на русском/таджикском/etc.
  Плохо: "меню поменять и ценцы увидеть неа"
  Хорошо: "Update Clover POS menu items and view current prices"

- "ticket_description" — DETAILED English description for support team (3-5 sentences):
  1. What exactly the merchant needs
  2. Context (business type, what they already tried)
  3. What AI suggested and why it didn't work (if there was dialog)
  4. Concrete actions support should take
  Пиши как senior support engineer коллегам — по делу, технически, без воды, НА АНГЛИЙСКОМ.

- "response_to_merchant" — остаётся на ЯЗЫКЕ МЕРЧАНТА (не переводи его ответ).

JSON ответ (строго этот формат):
{{"confidence":0-100,"should_escalate":true/false,"category":"<из списка>","priority":"Urgent|High|Normal|Low","response_to_merchant":"ответ мерчанту на его языке","ticket_title":"clean English title","ticket_description":"detailed English description","escalation_summary":"brief English summary 1 line","clover_intent":null|"sales_query"|"order_query"|"menu_change","clover_item":""}}"""



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
    if not text:
        await update.message.reply_text("❌ Не удалось распознать голосовое. Попробуйте текстом.")
        return

    await update.message.reply_text(f"📝 Распознано: _{text}_", parse_mode="Markdown")

    # Роутинг по роли — НЕ мутируем update.message.text (frozen в PTB v20)
    if tg_id in agent_sessions:
        await handle_agent_message(update, context, text)
    else:
        # Для мерчанта: мутируем через object.__setattr__ (обходит _frozen)
        try:
            object.__setattr__(update.message, "text", text)
        except Exception as e:
            logger.warning(f"Could not set message.text: {e}")
        await handle_message(update, context)


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
        msg_lower = message_text.lower().strip()

        # Короткие "нет/no" — сразу эскалация (ответ на "помогло?")
        short_no = {"нет", "no", "не", "неа", "nope", "ne", "yox", "nein"}
        is_short_no = msg_lower in short_no

        # Фразы-триггеры эскалации (частичное совпадение)
        escalation_phrases = (
            "саппорт", "support", "заявка", "не помог", "не помогло", "не помогает",
            "не работает", "всё равно", "все равно", "не понял", "не понятно",
            "создай заявку", "нужен человек", "отдай саппорт", "отдай специалист",
            "позови человека", "не получилось", "не получается", "не то",
            "неправильно", "свяжитесь", "позвоните",
        )
        is_phrase = any(t in msg_lower for t in escalation_phrases) or msg_lower == "2"

        if is_short_no or is_phrase:
            session["mode"] = "support"
            session["awaiting_phone"] = True
            # ВАЖНО: добавляем это сообщение в сессию — оно содержит контекст эскалации
            session["messages"].append(message_text)
            # Сбрасываем старый анализ — _create_and_confirm_ticket сделает свежий
            session["last_analysis"] = None
            session["pending_analysis"] = None
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

ВАЖНО: сотрудник может описать НЕСКОЛЬКО задач для РАЗНЫХ мерчантов в одном сообщении
(особенно в голосовых). Раздели их на отдельные задачи — одну на мерчанта/проблему.

ОБЯЗАТЕЛЬНО определи:
1. intent — "task" если описывает проблему/задачу/просьбу, "question" если вопрос, "other"
2. tasks — МАССИВ задач. Каждая задача это объект с полями:
   - merchant_name: ТОЧНОЕ название мерчанта как написал сотрудник (оригинал), иначе "Не указан"
   - task_title: CLEAN ENGLISH title (max 70 chars). ВСЕГДА на английском.
   - task_description: DETAILED ENGLISH description (2-4 sentences).
   - priority: 1|2|3|4 (см. ниже)
   - category: одна из списка
3. priority — определи по словам-маркерам:
   • 1 = URGENT 🔴 — прямо сейчас, бизнес стоит: "срочно", "сейчас", "asap", "urgent",
     "не работает совсем", "терминал умер", "не могу принимать", "горит", "немедленно",
     "сегодня нужно", "fraud", "chargeback сегодня", "закрыли аккаунт"
   • 2 = HIGH 🟠 — важно, частично работает: "важно", "проблема", "ошибка", "зависает",
     "глючит", "не печатает", "declined", "нужно к вечеру", "до завтра", "жалоба клиента"
   • 3 = NORMAL 🟡 — обычная задача, нужно начинать: "поменять", "обновить", "добавить",
     "изменить меню/цены", "настроить", "подключить", "вопрос по", "как сделать" (по умолчанию)
   • 4 = LOW 🟢 — не срочно: "когда будет время", "на днях", "не горит", "на следующей неделе",
     "по возможности", "fyi", "справка", "на потом"
Категории: Clover POS, Фото/Меню, Документы, Транзакции, Тех.проблема, Обновление данных, Биллинг, Оборудование, Другое
4. answer — ответ если intent="question" или "other" (на языке сотрудника)

Примеры:

"Нужно поменять пару фоток у Iflowers срочно"
→ {"intent":"task","tasks":[{"merchant_name":"Iflowers","task_title":"Replace photos in Clover POS menu","task_description":"Merchant Iflowers needs to replace several menu photos in Clover POS. Urgent — contact merchant to get new photos and upload via Inventory.","priority":1,"category":"Фото/Меню"}],"answer":""}

"У Pizza Palace не проходят транзакции и у BGI обнови адрес когда будет время"
→ {"intent":"task","tasks":[
    {"merchant_name":"Pizza Palace","task_title":"Transactions not going through","task_description":"Merchant Pizza Palace reports transactions failing. Need to diagnose processing: check terminal connection, Tekcard gateway status, and recent declines.","priority":1,"category":"Транзакции"},
    {"merchant_name":"BGI","task_title":"Update merchant address on file","task_description":"Non-urgent — update address for merchant BGI. Contact merchant for new address and update in MPA system.","priority":4,"category":"Обновление данных"}
],"answer":""}

"Нужно поменять цены на пловхаус, а потом нужно узнать, почему принтер не работает в Nomads ресторан и какие-то вопросы у Taco Food. Открою три разные тикеты"
→ {"intent":"task","tasks":[
    {"merchant_name":"Plove House","task_title":"Update menu prices in Clover POS","task_description":"Merchant Plove House needs menu price updates in Clover POS. Contact merchant to collect new price list, then update via Inventory.","priority":3,"category":"Фото/Меню"},
    {"merchant_name":"Nomads","task_title":"Printer not working at terminal","task_description":"Merchant Nomads reports their receipt printer is not working. Need to diagnose: check cable, paper roll, and pairing with Clover device. Dispatch tech if hardware fault.","priority":2,"category":"Оборудование"},
    {"merchant_name":"Taco Food","task_title":"General inquiry — needs clarification","task_description":"Merchant Taco Food has questions (content not specified by agent). Agent to follow up with merchant to clarify specific questions and route to correct team.","priority":3,"category":"Другое"}
],"answer":""}

Ответь ТОЛЬКО JSON без markdown."""


async def _create_clickup_task(agent: dict, task_data: dict, phone: str = None, resolved_merchant: dict = None):
    """Создаёт задачу в ClickUp с custom fields.
    Если resolved_merchant передан — тянем из него MID/код/телефон и тд.
    """
    merchant_name = task_data.get("merchant_name", "Не указан")
    title         = task_data.get("task_title", "Новая задача")
    description   = task_data.get("task_description", "")
    priority      = task_data.get("priority", 3)
    category      = task_data.get("category", "Другое")

    # Маппинг внутренних русских категорий на ClickUp dropdown options
    cat_ru_to_en = {
        "Clover POS":        "Software",
        "Фото/Меню":         "Software",
        "Документы":         "Account",
        "Транзакции":        "Payment",
        "Тех.проблема":      "Hardware",
        "Оборудование":      "Hardware",
        "Обновление данных": "Account",
        "Биллинг":           "Account",
        "Другое":            "Other",
    }
    category_mapped = cat_ru_to_en.get(category, category)

    priority_map = {1: ("🔥", "Urgent"), 2: ("🟠", "High"), 3: ("🟡", "Normal"), 4: ("🟢", "Low")}
    emoji, priority_label = priority_map.get(priority, ("🟡", "Normal"))

    # Если мерчант найден в базе — берём актуальное имя и подмешиваем данные
    mid           = ""
    unique_code   = ""
    merchant_phone = ""
    if resolved_merchant:
        merchant_name  = resolved_merchant.get("name") or merchant_name
        mid            = resolved_merchant.get("mid", "") or ""
        unique_code    = resolved_merchant.get("unique_code", "") or ""
        merchant_phone = resolved_merchant.get("phone", "") or ""

    # Если агент не дал телефон — берём из базы мерчанта
    effective_phone = phone or merchant_phone or None

    task_name = f"{emoji} {title.strip().replace(chr(10), ' ')[:120]}"

    desc_parts = [f"📋 **Task from {agent['name']}**"]
    if resolved_merchant:
        desc_parts.append(
            f"🏪 Merchant: **{merchant_name}** (MID: `{mid or '—'}`, Code: `{unique_code or '—'}`)"
        )
    else:
        desc_parts.append(f"🏪 Merchant: **{merchant_name}**")
    desc_parts.append(f"\n📝 {description}")
    if effective_phone:
        desc_parts.append(f"\n📞 **Phone:** {effective_phone}")

    tags = []
    if merchant_name and merchant_name != "Не указан":
        tags.append(merchant_name.lower().strip())
    if unique_code:
        tags.append(unique_code.lower())

    assigned_agent = get_least_loaded_agent()

    # ── Custom fields — dynamic lookup + dropdown per-field endpoint ──
    custom_fields = []

    # Merchant name (text field)
    for name_candidate in ["Merchant", "Мерчант", "Merchant Name", "Название мерчанта"]:
        cf = build_custom_field([name_candidate], merchant_name)
        if cf and not any(x["id"] == cf["id"] for x in custom_fields):
            custom_fields.append(cf)

    # MID
    if mid:
        cf = build_custom_field(["MID", "Merchant ID"], mid)
        if cf: custom_fields.append(cf)

    # Unique Code (INF-XXX)
    if unique_code:
        cf = build_custom_field(["Unique Code", "Код мерчанта", "INF Code"], unique_code)
        if cf: custom_fields.append(cf)

    # Category dropdown
    cf = build_custom_field(["Category", "Категория"], category_mapped, dropdown=True)
    if cf: custom_fields.append(cf)

    # Priority Level dropdown
    cf = build_custom_field(
        ["Priority Level", "Priority", "Приоритет", "Уровень приоритета"],
        priority_label, dropdown=True
    )
    if cf: custom_fields.append(cf)

    # Source dropdown — задача от агента = Internal Task
    cf = build_custom_field(["Source", "Источник"], "Internal Task", dropdown=True)
    if cf: custom_fields.append(cf)

    # Channel dropdown
    cf = build_custom_field(["Channel", "Канал"], "Telegram", dropdown=True)
    if cf: custom_fields.append(cf)

    # Phone
    if effective_phone:
        cf = build_custom_field(["Phone", "Телефон"], effective_phone)
        if cf: custom_fields.append(cf)

    # Разделяем: dropdowns отдельно
    dropdown_fields = [f for f in custom_fields if f.get("_dropdown")]
    plain_fields = [
        {"id": f["id"], "value": f["value"]}
        for f in custom_fields if not f.get("_dropdown")
    ]

    payload = {
        "name":          task_name,
        "description":   "\n".join(desc_parts),
        "priority":      priority,
        "assignees":     [assigned_agent["id"]],
        "tags":          tags,
        "custom_fields": plain_fields,
    }

    logger.info(
        f"[agent task] Creating: plain={len(plain_fields)}, dropdowns={len(dropdown_fields)} "
        f"({[(f.get('field_name'), f.get('_option_label')) for f in dropdown_fields]})"
    )

    r = httpx.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )

    if r.status_code in (200, 201):
        task_id = r.json()["id"]

        # Ставим dropdowns по одному
        for df in dropdown_fields:
            field_id   = df["id"]
            field_name = df.get("field_name", field_id[:8])
            uuid_val   = df.get("value")
            order_val  = df.get("orderindex")
            url = f"{CLICKUP_BASE}/task/{task_id}/field/{field_id}"

            ok = False
            if uuid_val:
                rr = httpx.post(url, headers=CLICKUP_HEADERS, json={"value": uuid_val})
                if rr.status_code in (200, 201):
                    logger.info(f"  ✓ {field_name} = {df.get('_option_label')} (uuid)")
                    ok = True
                else:
                    logger.warning(f"  ✗ {field_name} uuid failed: {rr.status_code} {rr.text[:200]}")

            if not ok and order_val is not None:
                try:
                    order_int = int(order_val)
                except (TypeError, ValueError):
                    order_int = order_val
                rr = httpx.post(url, headers=CLICKUP_HEADERS, json={"value": order_int})
                if rr.status_code in (200, 201):
                    logger.info(f"  ✓ {field_name} = {df.get('_option_label')} (orderindex={order_int})")
                    ok = True
                else:
                    logger.error(f"  ✗ {field_name} orderindex failed: {rr.status_code} {rr.text[:200]}")

            if not ok:
                logger.error(f"  ✗✗ {field_name}: ВСЕ попытки провалились")

        short_id = register_ticket_short_id(task_id)

        # Дублируем в TG-группу поддержки (как и мерчантские тикеты)
        if SUPPORT_GROUP_CHAT_ID:
            try:
                phone_notify = f"\n📞 *Телефон:* {effective_phone}" if effective_phone else ""
                mid_notify = f"\n🆔 *MID:* `{mid}`" if mid else ""
                code_notify = f"\n🔑 *Код:* `{unique_code}`" if unique_code else ""
                desc_preview = "\n".join(desc_parts)[:400]
                notify_text = (
                    f"🆕 *Новый тикет от агента* `{short_id}`\n\n"
                    f"{emoji} *Приоритет:* {priority_label}\n"
                    f"📁 *Категория:* {category_mapped}\n"
                    f"🏪 *Мерчант:* {merchant_name}"
                    f"{mid_notify}{code_notify}\n"
                    f"👤 *Назначен:* {assigned_agent['name']}\n"
                    f"🧑‍💼 *Создал:* {agent.get('name', 'Agent')}{phone_notify}\n\n"
                    f"📝 *{title}*\n"
                    f"{desc_preview}"
                )
                httpx.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id":    SUPPORT_GROUP_CHAT_ID,
                        "text":       notify_text,
                        "parse_mode": "Markdown",
                    },
                    timeout=5.0,
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления в группу (agent task): {e}")

        return {
            "success":        True,
            "task_id":        task_id,
            "short_id":       short_id,
            "assigned_to":    assigned_agent["name"],
            "emoji":          emoji,
            "priority_label": priority_label,
            "merchant":       merchant_name,
            "mid":            mid,
            "unique_code":    unique_code,
            "title":          title,
            "category":       category_mapped,
            "phone":          effective_phone,
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

    # ── Шаг 1.5: выбор мерчанта из кандидатов ────────────────────────────
    if tg_id in pending_agent_tasks and pending_agent_tasks[tg_id].get("step") == "pick_merchant":
        pending = pending_agent_tasks[tg_id]
        candidates = pending["candidates"]
        choice = text.strip().lower()

        picked = None
        if choice in ("0", "нет", "пропустить", "skip", "без", "no"):
            picked = "none"  # задача без привязки к мерчанту
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                picked = candidates[idx]
        else:
            # попробуем по имени
            for c in candidates:
                if choice in c["name"].lower():
                    picked = c
                    break

        if picked is None:
            names_list = "\n".join(
                f"{i+1}. *{c['name']}* — MID: `{c.get('mid') or '—'}`, код: `{c.get('unique_code') or '—'}`"
                for i, c in enumerate(candidates)
            )
            await update.message.reply_text(
                f"🤔 Не понял. Выберите номер:\n\n{names_list}\n\n"
                f"0 — создать задачу без мерчанта",
                parse_mode="Markdown"
            )
            return

        if picked == "none":
            pending["resolved_merchant"] = None
        else:
            pending["resolved_merchant"] = picked
            pending["task_data"]["merchant_name"] = picked["name"]

        pending["step"] = "phone"
        m = pending.get("resolved_merchant")
        info = ""
        if m:
            info = (
                f"✅ Мерчант: *{m['name']}*\n"
                f"🆔 MID: `{m.get('mid') or '—'}`\n"
                f"🔑 Код: `{m.get('unique_code') or '—'}`\n\n"
            )
        else:
            info = "⚠️ Задача будет создана без привязки к мерчанту\n\n"
        await update.message.reply_text(
            f"{info}📞 *Укажите номер телефона мерчанта для обратной связи*\n"
            f"(или напишите *нет* чтобы пропустить)",
            parse_mode="Markdown"
        )
        return

    # ── Шаг 2: ожидаем телефон ───────────────────────────────────────────
    if tg_id in pending_agent_tasks and pending_agent_tasks[tg_id].get("step") == "phone":
        pending = pending_agent_tasks[tg_id]
        resolved = pending.get("resolved_merchant")

        # Пропустить
        if text.lower() in ("нет", "пропустить", "skip", "no", "-", "0"):
            task_data = pending["task_data"]
            result = await _create_clickup_task(agent, task_data, phone=None, resolved_merchant=resolved)
        else:
            # Валидация: похоже ли на телефон?
            import re as _re
            stripped = _re.sub(r"[\s\-\(\)\+]", "", text.strip())
            is_phone_like = stripped.isdigit() and 7 <= len(stripped) <= 15

            if not is_phone_like:
                # Не телефон — значит агент хочет уточнить мерчанта. Ищем заново.
                new_query = text.strip()
                try:
                    new_candidates = search_merchants_by_name(new_query, limit=5)
                except Exception as e:
                    logger.error(f"retry search error: {e}")
                    new_candidates = []

                if len(new_candidates) == 1:
                    # Нашли — обновляем и сохраняем состояние, ждём телефон снова
                    pending["resolved_merchant"] = new_candidates[0]
                    pending["task_data"]["merchant_name"] = new_candidates[0]["name"]
                    m = new_candidates[0]
                    await update.message.reply_text(
                        f"✅ Найден: *{m['name']}*\n"
                        f"🆔 MID: `{m.get('mid') or '—'}`\n"
                        f"🔑 Код: `{m.get('unique_code') or '—'}`\n\n"
                        f"📞 Теперь укажите *телефон* (или *нет* чтобы пропустить)",
                        parse_mode="Markdown"
                    )
                    return
                elif len(new_candidates) > 1:
                    pending["candidates"] = new_candidates
                    pending["step"] = "pick_merchant"
                    names_list = "\n".join(
                        f"{i+1}. *{c['name']}* — MID: `{c.get('mid') or '—'}`, код: `{c.get('unique_code') or '—'}`"
                        for i, c in enumerate(new_candidates)
                    )
                    await update.message.reply_text(
                        f"🔎 Найдено {len(new_candidates)} мерчантов по *{new_query}*:\n\n"
                        f"{names_list}\n\n"
                        f"Напишите *номер* (1-{len(new_candidates)}) или *0* чтобы без мерчанта.",
                        parse_mode="Markdown"
                    )
                    return
                else:
                    await update.message.reply_text(
                        f"❌ По запросу *{new_query}* ничего не найдено.\n\n"
                        f"Варианты:\n"
                        f"• Напишите другое имя мерчанта\n"
                        f"• Напишите *номер телефона* для связи\n"
                        f"• Напишите *нет* чтобы создать задачу без мерчанта",
                        parse_mode="Markdown"
                    )
                    return

            # Принимаем как телефон
            phone = text.strip()
            task_data = pending["task_data"]
            result = await _create_clickup_task(agent, task_data, phone=phone, resolved_merchant=resolved)

        del pending_agent_tasks[tg_id]

        if result.get("success"):
            await update.message.reply_text(
                f"✅ *Задача создана!*  `{result.get('short_id','?')}`\n\n"
                f"{result['emoji']} *{result['title']}*\n"
                f"🏪 Мерчант: *{result['merchant']}*"
                + (f"\n🆔 MID: `{result['mid']}`" if result.get('mid') else "")
                + (f"\n🔑 Код: `{result['unique_code']}`" if result.get('unique_code') else "")
                + f"\n⚡ Приоритет: {result['emoji']} {result['priority_label']}\n"
                f"📂 Категория: {result['category']}\n"
                f"👤 Назначено: *{result['assigned_to']}*\n"
                f"{'📞 Телефон: ' + result['phone'] if result.get('phone') else '📞 Без телефона'}\n\n"
                f"_Команды: /delete {result.get('short_id','?')} · /priority {result.get('short_id','?')} urgent · /status {result.get('short_id','?')} done_",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Ошибка создания задачи в ClickUp.")
        return

    # ── Шаг 1: AI анализирует текст ─────────────────────────────────────
    try:
        resp = anthropic_client.messages.create(
            model="claude-sonnet-4-6",  # Sonnet для умного разбора речи агентов (было haiku — тупил)
            max_tokens=2000,            # больше для массива задач + reasoning
            system=AGENT_AI_PROMPT,
            messages=[{"role": "user", "content": f"Сотрудник ({agent['name']}) написал: {text}"}]
        )

        raw = resp.content[0].text.strip()
        data = parse_ai_json(raw)
        intent = data.get("intent", "other")

        if intent == "task":
            # Поддержка и нового формата (tasks array), и старого (плоский объект)
            tasks = data.get("tasks")
            if not tasks:
                # Обратная совместимость — оборачиваем плоский в массив
                tasks = [{
                    "merchant_name":    data.get("merchant_name", "Не указан"),
                    "task_title":       data.get("task_title", text[:60]),
                    "task_description": data.get("task_description", ""),
                    "priority":         data.get("priority", 3),
                    "category":         data.get("category", "Другое"),
                }]

            priority_map = {1: "🔥 Urgent", 2: "🟠 High", 3: "🟡 Normal", 4: "🟢 Low"}

            # ─── Одна задача — интерактивный флоу (как раньше) ──────────
            if len(tasks) == 1:
                task = tasks[0]
                merchant = task.get("merchant_name", "Не указан")
                title    = task.get("task_title", text[:60])
                p        = task.get("priority", 3)

                resolved = None
                candidates = []
                if merchant and merchant.lower() not in ("не указан", "unknown", ""):
                    try:
                        candidates = search_merchants_by_name(merchant, limit=5)
                    except Exception as e:
                        logger.error(f"search_merchants_by_name error: {e}")
                        candidates = []

                if len(candidates) == 1:
                    resolved = candidates[0]
                    task["merchant_name"] = resolved["name"]

                pending_agent_tasks[tg_id] = {
                    "task_data": task,
                    "candidates": candidates,
                    "resolved_merchant": resolved,
                    "created_at": time.time(),
                    "step": "phone" if (resolved is not None or not candidates) else "pick_merchant",
                }

                if len(candidates) > 1:
                    names_list = "\n".join(
                        f"{i+1}. *{c['name']}* — MID: `{c.get('mid') or '—'}`, код: `{c.get('unique_code') or '—'}`"
                        for i, c in enumerate(candidates)
                    )
                    await update.message.reply_text(
                        f"📋 *Новая задача:* {title}\n"
                        f"⚡ {priority_map.get(p, '🟡 Normal')}  📂 {task.get('category', 'Другое')}\n\n"
                        f"🔎 По запросу *{merchant}* найдено {len(candidates)} мерчантов:\n\n"
                        f"{names_list}\n\n"
                        f"Напишите *номер* (1-{len(candidates)}) или *0* чтобы без привязки.",
                        parse_mode="Markdown"
                    )
                    return

                if resolved:
                    info_block = (
                        f"✅ Найден: *{resolved['name']}*\n"
                        f"🆔 MID: `{resolved.get('mid') or '—'}`\n"
                        f"🔑 Код: `{resolved.get('unique_code') or '—'}`\n"
                    )
                elif merchant and merchant.lower() not in ("не указан", "unknown", ""):
                    info_block = (
                        f"⚠️ Мерчант *{merchant}* не найден в базе.\n"
                        f"Задача будет создана с этим именем, без MID/кода.\n"
                    )
                else:
                    info_block = f"🏪 Мерчант: *{merchant}*\n"

                await update.message.reply_text(
                    f"📋 *Новая задача:*\n\n"
                    f"📝 {title}\n"
                    f"{info_block}"
                    f"⚡ Приоритет: {priority_map.get(p, '🟡 Normal')}\n"
                    f"📂 Категория: {task.get('category', 'Другое')}\n\n"
                    f"📞 *Укажите телефон* (или *нет* чтобы пропустить)",
                    parse_mode="Markdown"
                )
                return

            # ─── Несколько задач — batch-режим, без интерактива ─────────
            await update.message.reply_text(
                f"🎯 Распознано *{len(tasks)}* задач. Создаю тикеты...",
                parse_mode="Markdown"
            )

            results = []
            for task in tasks:
                merchant = task.get("merchant_name", "Не указан")
                resolved = None
                try:
                    cands = search_merchants_by_name(merchant, limit=3) if merchant and merchant.lower() not in ("не указан", "unknown", "") else []
                except Exception as e:
                    logger.error(f"batch search error for {merchant}: {e}")
                    cands = []
                # Автовыбор: если есть кандидаты — берём первый (наиболее релевантный)
                if cands:
                    resolved = cands[0]
                    task["merchant_name"] = resolved["name"]

                res = await _create_clickup_task(agent, task, phone=None, resolved_merchant=resolved)
                results.append((task, resolved, res))

            # Сводка по всем тикетам
            summary_lines = [f"✅ *Создано {sum(1 for _,_,r in results if r.get('success'))} из {len(results)} тикетов:*\n"]
            for i, (task, resolved, res) in enumerate(results, 1):
                if not res.get("success"):
                    summary_lines.append(f"{i}. ❌ *{task.get('task_title','?')}* — ошибка создания")
                    continue
                mname = res.get("merchant", task.get("merchant_name"))
                code_part = f" [`{res.get('unique_code')}`]" if res.get('unique_code') else ""
                mid_part  = f" MID:`{res.get('mid')}`" if res.get('mid') else ""
                summary_lines.append(
                    f"{i}. `{res.get('short_id','?')}`  {res['emoji']} *{res['title']}*\n"
                    f"   🏪 {mname}{code_part}{mid_part}\n"
                    f"   📂 {res['category']}  👤 {res['assigned_to']}"
                )
            await update.message.reply_text("\n\n".join(summary_lines), parse_mode="Markdown")
            return

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
            "Просто напишите задачу/голосовое — AI поймёт.\n"
            "Несколько задач в одном сообщении → отдельные тикеты.\n\n"
            "*Тикеты:*\n"
            "/tickets — список последних\n"
            "/ticket T-042 — инфа по тикету\n"
            "/delete T-042 — удалить\n"
            "/priority T-042 urgent — сменить приоритет (urgent/high/normal/low)\n"
            "/status T-042 done — сменить статус\n\n"
            "*Мерчанты:*\n"
            "/addmerchant — добавить мерчанта\n\n"
            "*Остальное:*\n"
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
# ТИКЕТ-МЕНЕДЖМЕНТ (ТОЛЬКО АГЕНТЫ/ISO)
# ═══════════════════════════════════════════════════════════════════════════

async def _agent_only_check(update: Update) -> bool:
    """Возвращает True если можно продолжать. Иначе отвечает и возвращает False."""
    tg_id = update.effective_user.id
    if tg_id not in agent_sessions:
        await update.message.reply_text(
            "🔒 Команда только для агентов/ISO.\nВойдите через /login CODE"
        )
        return False
    return True


async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список последних тикетов с короткими ID."""
    if not await _agent_only_check(update):
        return
    if not short_to_clickup:
        await update.message.reply_text("Пока нет тикетов в системе.")
        return
    # Последние 15 по убыванию номера
    items = sorted(short_to_clickup.items(),
                   key=lambda x: int(x[0].split("-")[1]), reverse=True)[:15]
    lines = ["📋 *Последние тикеты:*\n"]
    for sid, cid in items:
        try:
            r = httpx.get(f"{CLICKUP_BASE}/task/{cid}", headers=CLICKUP_HEADERS, timeout=5)
            if r.status_code == 200:
                task = r.json()
                name = task.get("name", "?")[:60]
                status = task.get("status", {}).get("status", "?")
                lines.append(f"`{sid}`  {name}\n  _status: {status}_")
            else:
                lines.append(f"`{sid}`  _(недоступен)_")
        except Exception:
            lines.append(f"`{sid}`  _(ошибка)_")
    await update.message.reply_text(
        "\n\n".join(lines) + "\n\n_Команды: /ticket T-001 · /delete T-001 · /priority T-001 urgent · /status T-001 done_",
        parse_mode="Markdown"
    )


async def ticket_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инфа по тикету: /ticket T-042"""
    if not await _agent_only_check(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /ticket T-042")
        return
    ref = args[0]
    cid = resolve_ticket_id(ref)
    if not cid:
        await update.message.reply_text(f"❌ Тикет `{ref}` не найден. /tickets — список.",
                                        parse_mode="Markdown")
        return
    r = httpx.get(f"{CLICKUP_BASE}/task/{cid}", headers=CLICKUP_HEADERS, timeout=10)
    if r.status_code != 200:
        await update.message.reply_text(f"❌ ClickUp вернул {r.status_code}")
        return
    task = r.json()
    sid = clickup_to_short.get(cid, ref)
    name = task.get("name", "?")
    status = task.get("status", {}).get("status", "?")
    pr = task.get("priority") or {}
    pr_name = pr.get("priority", "?") if isinstance(pr, dict) else str(pr)
    url = task.get("url", "")
    assignees = ", ".join(a.get("username", "?") for a in task.get("assignees", [])) or "—"
    desc = (task.get("description") or "")[:500]
    await update.message.reply_text(
        f"🔖 `{sid}`  *{name}*\n\n"
        f"📊 Статус: *{status}*\n"
        f"⚡ Приоритет: *{pr_name}*\n"
        f"👤 Назначено: {assignees}\n\n"
        f"{desc}\n\n"
        f"🔗 {url}",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def delete_ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет тикет: /delete T-042"""
    if not await _agent_only_check(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /delete T-042")
        return
    ref = args[0]
    cid = resolve_ticket_id(ref)
    if not cid:
        await update.message.reply_text(f"❌ Тикет `{ref}` не найден.", parse_mode="Markdown")
        return
    sid = clickup_to_short.get(cid, ref)
    r = httpx.delete(f"{CLICKUP_BASE}/task/{cid}", headers=CLICKUP_HEADERS, timeout=10)
    if r.status_code in (200, 204):
        # Чистим локальные маппинги
        short_to_clickup.pop(sid, None)
        clickup_to_short.pop(cid, None)
        ticket_to_tg.pop(cid, None)
        save_state()
        await update.message.reply_text(f"🗑 Тикет `{sid}` удалён.", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ Не удалось удалить `{sid}`: {r.status_code} {r.text[:200]}",
            parse_mode="Markdown"
        )


async def priority_ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меняет приоритет: /priority T-042 urgent|high|normal|low"""
    if not await _agent_only_check(update):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: /priority T-042 urgent|high|normal|low"
        )
        return
    ref, new_pri_raw = args[0], args[1].lower()
    pri_map = {"urgent": 1, "срочно": 1, "high": 2, "важно": 2,
               "normal": 3, "обычный": 3, "low": 4, "низкий": 4}
    if new_pri_raw not in pri_map:
        await update.message.reply_text(
            "Приоритет: urgent / high / normal / low"
        )
        return
    cid = resolve_ticket_id(ref)
    if not cid:
        await update.message.reply_text(f"❌ Тикет `{ref}` не найден.", parse_mode="Markdown")
        return
    sid = clickup_to_short.get(cid, ref)
    new_pri = pri_map[new_pri_raw]
    # 1) Обновляем built-in priority
    r = httpx.put(
        f"{CLICKUP_BASE}/task/{cid}",
        headers=CLICKUP_HEADERS,
        json={"priority": new_pri}
    )
    built_in_ok = r.status_code in (200, 201)
    # 2) Обновляем кастомный dropdown Priority Level
    pri_label = {1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}[new_pri]
    cf = build_custom_field(
        ["Priority Level", "Priority", "Приоритет", "Уровень приоритета"],
        pri_label, dropdown=True
    )
    dropdown_ok = False
    if cf and cf.get("_dropdown"):
        url = f"{CLICKUP_BASE}/task/{cid}/field/{cf['id']}"
        if cf.get("value"):
            rr = httpx.post(url, headers=CLICKUP_HEADERS, json={"value": cf["value"]})
            dropdown_ok = rr.status_code in (200, 201)
        if not dropdown_ok and cf.get("orderindex") is not None:
            try:
                oi = int(cf["orderindex"])
            except (TypeError, ValueError):
                oi = cf["orderindex"]
            rr = httpx.post(url, headers=CLICKUP_HEADERS, json={"value": oi})
            dropdown_ok = rr.status_code in (200, 201)

    emoji = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢"}[new_pri]
    if built_in_ok or dropdown_ok:
        await update.message.reply_text(
            f"{emoji} Приоритет `{sid}` → *{pri_label}*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось обновить приоритет: {r.status_code} {r.text[:200]}",
            parse_mode="Markdown"
        )


async def status_ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меняет статус: /status T-042 open|in progress|done|closed"""
    if not await _agent_only_check(update):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: /status T-042 <статус>\n"
            "Примеры: open, in progress, done, closed, complete"
        )
        return
    ref = args[0]
    new_status = " ".join(args[1:]).strip()
    cid = resolve_ticket_id(ref)
    if not cid:
        await update.message.reply_text(f"❌ Тикет `{ref}` не найден.", parse_mode="Markdown")
        return
    sid = clickup_to_short.get(cid, ref)
    r = httpx.put(
        f"{CLICKUP_BASE}/task/{cid}",
        headers=CLICKUP_HEADERS,
        json={"status": new_status}
    )
    if r.status_code in (200, 201):
        await update.message.reply_text(
            f"📊 Статус `{sid}` → *{new_status}*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось. ClickUp: {r.status_code} {r.text[:250]}\n"
            f"_Доступные статусы зависят от настроек листа в ClickUp._",
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("\n═══════════════════════════════════════════")
    print(" Infinity Pay Bot v2 — Starting...")
    print("═══════════════════════════════════════════\n")

    load_state()

    # Прогреваем кеш полей ClickUp — чтобы первый же тикет правильно заполнил поля
    try:
        get_ticket_fields(force=True)
    except Exception as e:
        logger.error(f"Не удалось загрузить поля ClickUp при старте: {e}")

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
    app.add_handler(CommandHandler("tickets", tickets_command))
    app.add_handler(CommandHandler("delete", delete_ticket_command))
    app.add_handler(CommandHandler("priority", priority_ticket_command))
    app.add_handler(CommandHandler("status", status_ticket_command))
    app.add_handler(CommandHandler("ticket", ticket_info_command))

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

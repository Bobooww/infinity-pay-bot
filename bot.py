"""
Infinity Pay â Telegram Support Bot v2
ÐÐ°Ð¿ÑÑÐºÐ°ÐµÑÑÑ ÐºÐ¾Ð¼Ð°Ð½Ð´Ð¾Ð¹: python bot.py

Ð¤Ð¸ÑÐ¸ v2:
- ÐÐ¸Ð±ÑÐ¸Ð´ AI: Haiku Ð´Ð»Ñ Ð¿ÑÐ¾ÑÑÑÑ â Sonnet Ð´Ð»Ñ ÑÐ»Ð¾Ð¶Ð½ÑÑ
- Ð£Ð¼Ð½ÑÐµ ÐºÐ°ÑÐµÐ³Ð¾ÑÐ¸Ð¸ Ð±ÐµÐ· "Other"
- ÐÑÐ¸Ð¾ÑÐ¸ÑÐµÑÑ Urgent/High/Normal/Low Ñ ÑÐ¼Ð¾Ð´Ð·Ð¸
- Ð¡ÐµÑÑÐ¸Ð¸: Ð³ÑÑÐ¿Ð¿Ð¸ÑÐ¾Ð²ÐºÐ° ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹ Ð² Ð¾Ð´Ð¸Ð½ ÑÐ¸ÐºÐµÑ (ÑÐ°Ð¹Ð¼Ð°ÑÑ 10 Ð¼Ð¸Ð½)
- ÐÐ¾Ð»Ð¾ÑÐ¾Ð²ÑÐµ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ñ (Whisper API)
- ÐÑÐ±Ð»Ð¸ÑÐ¾Ð²Ð°Ð½Ð¸Ðµ ÑÐ¸ÐºÐµÑÐ¾Ð² Ð² TG-Ð³ÑÑÐ¿Ð¿Ñ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ¸
- ÐÐ¾Ð³Ð¸Ð½ Ð°Ð³ÐµÐ½ÑÐ¾Ð²/ISO ÑÐµÑÐµÐ· /login + ÑÐµÐºÑÐµÑÐ½ÑÐ¹ ÐºÐ¾Ð´
- Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¿ÑÐ¸ ÑÐ¼ÐµÐ½Ðµ ÑÑÐ°ÑÑÑÐ° ÑÐ¸ÐºÐµÑÐ° (ClickUp webhook)
- FAQ ÐºÐµÑ, Ð°Ð½ÑÐ¸ÑÐ¿Ð°Ð¼, ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ°
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
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# âââ ÐÐ°Ð³ÑÑÐ¶Ð°ÐµÐ¼ .env âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
load_dotenv()

# âââ Logging ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# âââ Config âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
CLAUDE_API_KEY  = os.environ["CLAUDE_API_KEY"]
CLICKUP_TOKEN   = os.environ["CLICKUP_API_TOKEN"]
CLICKUP_LIST_TICKETS   = os.environ["CLICKUP_LIST_TICKETS_ID"]
CLICKUP_LIST_MERCHANTS = os.environ["CLICKUP_LIST_MERCHANTS_ID"]

# Telegram Ð³ÑÑÐ¿Ð¿Ð° Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ¸ (chat_id, Ð·Ð°Ð´Ð°ÑÑÑÑ Ð² .env)
SUPPORT_GROUP_CHAT_ID = os.environ.get("SUPPORT_GROUP_CHAT_ID", "")

# OpenAI API Ð´Ð»Ñ Whisper (Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²ÑÐµ)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

CLICKUP_HEADERS = {
    "Authorization": CLICKUP_TOKEN,
    "Content-Type": "application/json"
}
CLICKUP_BASE = "https://api.clickup.com/api/v2"

# âââ ClickUp Custom Field IDs (Ð¸Ð· clickup_ids.json) âââââââââââââââââââââ
TICKET_FIELDS = {
    "source":         "cce340eb-1ad3-4393-99db-8a4479a4adf8",
    "merchant":       "a1748265-3769-4961-8a97-68f4c790b5ee",
    "mid":            "6b12ba3e-96a6-4068-9eaa-1cba547558ce",
    "category":       "98e62955-2751-45ed-a00a-4d8889e0c09e",
    "priority_level": "aaae7c35-5cbf-4325-be9c-d358b5654ab8",
    "channel":        "688d4913-337f-4f97-bada-3653dcee743c",
    "phone":          "67b7f5f3-2ebb-4b64-9d3f-f87c0a09b4bb",
}

# âââ Ð¡Ð°Ð¿Ð¿Ð¾ÑÑ-ÐºÐ¾Ð¼Ð°Ð½Ð´Ð° âââââââââââââââââââââââââââââââââââââââââââââââââââââ
SUPPORT_AGENTS = [
    {"id": 94469635, "name": "Support 1"},
    {"id": 94469636, "name": "Support 2"},
]

# âââ Ð¡ÐµÐºÑÐµÑÐ½ÑÐµ ÐºÐ¾Ð´Ñ Ð´Ð»Ñ Ð»Ð¾Ð³Ð¸Ð½Ð° Ð°Ð³ÐµÐ½ÑÐ¾Ð²/ISO ââââââââââââââââââââââââââââââââ
AGENT_CODES = {
    "IAMAGENT": {"role": "agent", "name": "Infinity Pay Staff", "clickup_id": None},
    "ISO-MASTER": {"role": "iso", "name": "Shams (ISO Owner)", "clickup_id": None},
}

# âââ AI ÐºÐ»Ð¸ÐµÐ½ÑÑ ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
anthropic_client = Anthropic(api_key=CLAUDE_API_KEY)

# âââ ÐÑÐ¸Ð¾ÑÐ¸ÑÐµÑÑ Ñ ÑÐ¼Ð¾Ð´Ð·Ð¸ ââââââââââââââââââââââââââââââââââââââââââââââââ
PRIORITY_EMOJI = {
    "Urgent": "ð´",
    "High":   "ð ",
    "Normal": "ð¡",
    "Low":    "ð¢",
}
PRIORITY_MAP = {"Urgent": 1, "High": 2, "Normal": 3, "Low": 4}

# âââ ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ð¸ (Ð±ÐµÐ· "Other") ââââââââââââââââââââââââââââââââââââââââââââ
VALID_CATEGORIES = [
    "Terminal", "Payment", "Chargeback", "Statement",
    "Billing", "Account", "Software", "Hardware",
    "Fraud", "Compliance", "General"
]

# âââ Ð¥ÑÐ°Ð½Ð¸Ð»Ð¸ÑÐµ ÑÐ¾ÑÑÐ¾ÑÐ½Ð¸Ð¹ (Ð² Ð¿Ð°Ð¼ÑÑÐ¸) ââââââââââââââââââââââââââââââââââââââ
user_states     = {}  # {tg_id: "awaiting_code"|"identified"|"agent"|"iso"}
merchant_cache  = {}  # {tg_id: merchant_data}
agent_sessions  = {}  # {tg_id: {"role": "agent"|"iso", "name": ..., ...}}

# âââ Ð¡ÐµÑÑÐ¸Ð¸ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹ (Ð°Ð½ÑÐ¸Ð´ÑÐ±Ð»Ñ) ââââââââââââââââââââââââââââââââââââââââ
# {tg_id: {"messages": [...], "last_time": timestamp, "ticket_id": str|None}}
message_sessions = {}
SESSION_TIMEOUT = 600  # 10 Ð¼Ð¸Ð½ÑÑ

# âââ FAQ ÐºÐµÑ âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
faq_cache = {}  # {"Ð²Ð¾Ð¿ÑÐ¾Ñ_ÑÐµÑ": {"answer": str, "hits": int, "last_used": ts}}
FAQ_CACHE_MAX = 200
FAQ_CACHE_TTL = 86400  # 24 ÑÐ°ÑÐ° â Ð·Ð°Ð¿Ð¸ÑÐ¸ ÑÑÐ°ÑÑÐµ ÑÐ´Ð°Ð»ÑÑÑÑÑ

# âââ ÐÐµÑ ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ð¹ (Ð¾ÑÐ´ÐµÐ»ÑÐ½Ð¾ Ð¾Ñ FAQ) âââââââââââââââââââââââââââââââââââ
notification_cache = {}  # {"notified_TASKID_STATUS": timestamp, "comment_ID": timestamp}
NOTIFICATION_CACHE_TTL = 86400  # 24 ÑÐ°ÑÐ°

# âââ ÐÐ½ÑÐ¸ÑÐ¿Ð°Ð¼ ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
spam_tracker = {}  # {tg_id: {"count": int, "first_msg": timestamp}}
SPAM_LIMIT  = 10   # Ð¼Ð°ÐºÑ 10 ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹ Ð·Ð° 60 ÑÐµÐº
SPAM_WINDOW = 60

# âââ Ð¡ÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ° ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
stats = {
    "total_messages":   0,
    "tickets_created":  0,
    "ai_direct_answers": 0,
    "escalations":      0,
    "voice_messages":   0,
    "haiku_calls":      0,
    "sonnet_calls":     0,
}


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# Ð£Ð¢ÐÐÐÐ¢Ð«
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def is_spam(tg_id: int) -> bool:
    """ÐÐ½ÑÐ¸ÑÐ¿Ð°Ð¼: >10 ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹ Ð·Ð° 60 ÑÐµÐº."""
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
    """ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ ÑÐµÐºÑÑÑÑ ÑÐµÑÑÐ¸Ñ Ð¸Ð»Ð¸ ÑÐ¾Ð·Ð´Ð°ÑÑ Ð½Ð¾Ð²ÑÑ."""
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
    """ÐÑÐ³ÐºÐ¾ Ð·Ð°ÐºÑÑÐ²Ð°ÐµÑ ÑÐµÑÑÐ¸Ñ â ÑÐ±ÑÐ°ÑÑÐ²Ð°ÐµÑ ÑÐ¸ÐºÐµÑ Ð¸ ÑÐµÐ¶Ð¸Ð¼."""
    if tg_id in message_sessions:
        message_sessions[tg_id]["ticket_id"] = None
        message_sessions[tg_id]["awaiting_choice"] = False
        message_sessions[tg_id]["mode"] = None


def cleanup_notification_cache():
    """Ð£Ð´Ð°Ð»ÑÐµÑ ÑÑÐ°ÑÑÐµ Ð·Ð°Ð¿Ð¸ÑÐ¸ Ð¸Ð· ÐºÐµÑÐ° ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ð¹."""
    now = time.time()
    expired = [k for k, v in notification_cache.items()
               if now - v > NOTIFICATION_CACHE_TTL]
    for k in expired:
        del notification_cache[k]


def cleanup_faq_cache():
    """Ð£Ð´Ð°Ð»ÑÐµÑ ÑÑÐ°ÑÑÐµ Ð·Ð°Ð¿Ð¸ÑÐ¸ Ð¸Ð· FAQ ÐºÐµÑÐ°."""
    now = time.time()
    expired = [k for k, v in faq_cache.items()
               if now - v.get("last_used", 0) > FAQ_CACHE_TTL]
    for k in expired:
        del faq_cache[k]
    # ÐÑÐ»Ð¸ Ð²ÑÑ ÐµÑÑ ÑÐ»Ð¸ÑÐºÐ¾Ð¼ Ð±Ð¾Ð»ÑÑÐ¾Ð¹ â ÑÐ´Ð°Ð»ÑÐµÐ¼ ÑÐ°Ð¼ÑÐµ ÑÑÐ°ÑÑÐµ
    if len(faq_cache) > FAQ_CACHE_MAX:
        sorted_keys = sorted(faq_cache, key=lambda k: faq_cache[k].get("last_used", 0))
        for k in sorted_keys[:len(faq_cache) - FAQ_CACHE_MAX]:
            del faq_cache[k]


def parse_ai_json(text: str) -> dict:
    """ÐÐ°Ð´ÑÐ¶Ð½ÑÐ¹ Ð¿Ð°ÑÑÐµÑ JSON Ð¸Ð· AI-Ð¾ÑÐ²ÐµÑÐ° (ÑÐ½Ð¸Ð¼Ð°ÐµÑ markdown-Ð¾Ð±ÑÑÑÐºÑ)."""
    raw = text.strip()
    # Ð¡Ð½Ð¸Ð¼Ð°ÐµÐ¼ ```json ... ``` Ð¾Ð±ÑÑÑÐºÑ
    if raw.startswith("```"):
        # Ð£Ð±Ð¸ÑÐ°ÐµÐ¼ Ð¿ÐµÑÐ²ÑÑ ÑÑÑÐ¾ÐºÑ (```json) Ð¸ Ð¿Ð¾ÑÐ»ÐµÐ´Ð½ÑÑ (```)
        lines = raw.split("\n")
        # ÐÐ°ÑÐ¾Ð´Ð¸Ð¼ Ð½Ð°ÑÐ°Ð»Ð¾ Ð¸ ÐºÐ¾Ð½ÐµÑ Ð±Ð»Ð¾ÐºÐ°
        start = 1  # Ð¿ÑÐ¾Ð¿ÑÑÐºÐ°ÐµÐ¼ ```json
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        raw = "\n".join(lines[start:end]).strip()
    # ÐÑÐ¾Ð±ÑÐµÐ¼ JSON
    return json.loads(raw)


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# CLICKUP HELPERS
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def get_least_loaded_agent() -> dict:
    """ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ Ð°Ð³ÐµÐ½ÑÐ° Ñ Ð½Ð°Ð¸Ð¼ÐµÐ½ÑÑÐ¸Ð¼ ÐºÐ¾Ð»Ð¸ÑÐµÑÑÐ²Ð¾Ð¼ Ð¾ÑÐºÑÑÑÑÑ ÑÐ¸ÐºÐµÑÐ¾Ð²."""
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
            logger.error(f"ÐÑÐ¸Ð±ÐºÐ° Ð½Ð°Ð³ÑÑÐ·ÐºÐ¸ {agent['name']}: {e}")
            agent_loads.append({"agent": agent, "open_tickets": 999})
    agent_loads.sort(key=lambda x: x["open_tickets"])
    chosen = agent_loads[0]["agent"]
    logger.info(f"ÐÐ°Ð·Ð½Ð°ÑÐ°ÐµÐ¼ Ð½Ð°: {chosen['name']}")
    return chosen


def search_merchant_by_code(code: str) -> dict | None:
    """ÐÑÐµÑ Ð¼ÐµÑÑÐ°Ð½ÑÐ° Ð¿Ð¾ ÑÐ½Ð¸ÐºÐ°Ð»ÑÐ½Ð¾Ð¼Ñ ÐºÐ¾Ð´Ñ."""
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
    """ÐÑÐµÑ Ð¼ÐµÑÑÐ°Ð½ÑÐ° Ð¿Ð¾ Telegram ID."""
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
    """ÐÐ·Ð²Ð»ÐµÐºÐ°ÐµÑ Ð´Ð°Ð½Ð½ÑÐµ Ð¼ÐµÑÑÐ°Ð½ÑÐ°."""
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
    }
    field_map = {
        "MID":           "mid",
        "Phone":         "phone",
        "Email":         "email",
        "Address":       "address",
        "Business Type": "business_type",
        "Unique Code":   "unique_code",
        "Telegram ID":   "telegram_id",
    }
    for field in task.get("custom_fields", []):
        key = field_map.get(field.get("name", ""))
        if key:
            data[key] = field.get("value", "") or ""
    return data


def save_telegram_id_to_merchant(task_id: str, telegram_id: int):
    """Ð¡Ð¾ÑÑÐ°Ð½ÑÐµÑ Telegram ID Ð² ÐºÐ°ÑÑÐ¾ÑÐºÑ Ð¼ÐµÑÑÐ°Ð½ÑÐ°."""
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


def create_support_ticket(merchant: dict, message: str, ai_analysis: dict, phone: str = None) -> str | None:
    """Ð¡Ð¾Ð·Ð´Ð°ÑÑ ÑÐ¸ÐºÐµÑ Ð² ClickUp Ñ custom fields."""
    priority = PRIORITY_MAP.get(ai_analysis.get("priority", "Normal"), 3)
    assigned_agent = get_least_loaded_agent()
    category       = ai_analysis.get("category", "General")
    priority_label = ai_analysis.get("priority", "Normal")
    emoji          = PRIORITY_EMOJI.get(priority_label, "ð¡")

    # ÐÑÐ¿Ð¾Ð»ÑÐ·ÑÐµÐ¼ AI-ÑÐµÐ·ÑÐ¼Ðµ Ð´Ð»Ñ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ ÑÐ¸ÐºÐµÑÐ°
    summary    = ai_analysis.get("escalation_summary", "")
    task_title = summary[:80] if summary else message[:80]
    task_name  = f"{emoji} [{category}] {merchant['name']} â {task_title}"

    # ÐÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ â ÑÐ¾Ð»ÑÐºÐ¾ ÑÐµÐºÑÑ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ñ Ð¸ AI ÑÐµÐ·ÑÐ¼Ðµ (Ð¾ÑÑÐ°Ð»ÑÐ½Ð¾Ðµ Ð² custom fields)
    phone_line = f"\nð **Ð¢ÐµÐ»ÐµÑÐ¾Ð½ Ð´Ð»Ñ ÑÐ²ÑÐ·Ð¸:** {phone}" if phone else ""
    description = f"""ð© **Ð¡Ð¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ Ð¼ÐµÑÑÐ°Ð½ÑÐ°:**
{message}

---
ð **AI Ð ÐµÐ·ÑÐ¼Ðµ:** {ai_analysis.get('escalation_summary', '')}
ð¤ Ð£Ð²ÐµÑÐµÐ½Ð½Ð¾ÑÑÑ: {ai_analysis.get('confidence')}%
ð¤ ÐÐ°Ð·Ð½Ð°ÑÐµÐ½Ð¾: {assigned_agent['name']}{phone_line}
"""

    # Custom fields â ÐºÐ°Ð¶Ð´Ð¾Ðµ Ð¿Ð¾Ð»Ðµ Ð¾ÑÐ´ÐµÐ»ÑÐ½Ð¾ Ð² ClickUp
    custom_fields = [
        {"id": TICKET_FIELDS["merchant"],       "value": merchant['name']},
        {"id": TICKET_FIELDS["mid"],            "value": merchant.get('mid', '')},
        {"id": TICKET_FIELDS["category"],       "value": category},
        {"id": TICKET_FIELDS["priority_level"], "value": priority_label},
        {"id": TICKET_FIELDS["source"],         "value": "Telegram Bot"},
        {"id": TICKET_FIELDS["channel"],        "value": "Telegram"},
    ]
    if phone:
        custom_fields.append({"id": TICKET_FIELDS["phone"], "value": phone})

    payload = {
        "name":          task_name,
        "description":   description,
        "priority":      priority,
        "assignees":     [assigned_agent["id"]],
        "custom_fields": custom_fields,
    }

    r = requests.post(
        f"{CLICKUP_BASE}/list/{CLICKUP_LIST_TICKETS}/task",
        headers=CLICKUP_HEADERS,
        json=payload
    )

    if r.status_code in (200, 201):
        task = r.json()
        ticket_id = task["id"]
        logger.info(f"Ð¢Ð¸ÐºÐµÑ ÑÐ¾Ð·Ð´Ð°Ð½: {ticket_id}")
        stats["tickets_created"] += 1

        # ÐÑÐ±Ð»Ð¸ÑÑÐµÐ¼ Ð² TG-Ð³ÑÑÐ¿Ð¿Ñ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ¸
        if SUPPORT_GROUP_CHAT_ID:
            try:
                phone_notify = f"\nð *Ð¢ÐµÐ»ÐµÑÐ¾Ð½:* {phone}" if phone else ""
                notify_text = (
                    f"ð *ÐÐ¾Ð²ÑÐ¹ ÑÐ¸ÐºÐµÑ*\n\n"
                    f"{emoji} *ÐÑÐ¸Ð¾ÑÐ¸ÑÐµÑ:* {priority_label}\n"
                    f"ð *ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ñ:* {category}\n"
                    f"ðª *ÐÐµÑÑÐ°Ð½Ñ:* {merchant['name']}\n"
                    f"ð *MID:* {merchant['mid']}\n"
                   f"ð¤ *ÐÐ°Ð·Ð½Ð°ÑÐµÐ½:* {assigned_agent['name']}{phone_notify}\n\n"
                    f"ð¬ *Ð¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ:*\n{message[:300]}\n\n"
                    f"ð *AI Ð ÐµÐ·ÑÐ¼Ðµ:*\n{ai_analysis.get('escalation_summary', 'N/A')}\n\n"
                    f"ð Ð¢Ð¸ÐºÐµÑ ID: `{ticket_id}`"
                )
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id":    SUPPORT_GROUP_CHAT_ID,
                        "text":       notify_text,
                        "parse_mode": "Markdown",
                    }
                )
            except Exception as e:
                logger.error(f"ÐÑÐ¸Ð±ÐºÐ° ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð² Ð³ÑÑÐ¿Ð¿Ñ{ {e}")

        return ticket_id
    else:
        logger.error(f"ÐÑÐ¸Ð±ÐºÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð¸Ñ ÑÐ¸ÐºÐµÑÐ°: {r.status_code} {r.text}")
        return None


def add_comment_to_ticket(ticket_id: str, comment: str):
    """ÐÐ¾Ð±Ð°Ð²Ð»ÑÐµÑ ÐºÐ¾Ð¼Ð¼ÐµÐ½ÑÐ°ÑÐ¸Ð¹ Ðº ÑÐ¸ÐºÐµÑÑ Ð² ClickUp."""
    r = requests.post(
        f"{CLICKUP_BASE}/task/{ticket_id}/comment",
        headers=CLICKUP_HEADERS,
        json={"comment_text": comment}
    )
    return r.status_code in (200, 201)


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# AI â ÐÐÐÐ ÐÐ HAIKU/SONNET
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

SYSTEM_PROMPT_TEMPLATE = """Ð¢Ñ AI-Ð°ÑÑÐ¸ÑÑÐµÐ½Ñ Infinity Pay Inc. â ISO Ð² ÑÑÐµÑÐµ Ð¿Ð»Ð°ÑÑÐ¶Ð½ÑÑ ÑÑÐ»ÑÐ³.
ÐÑÐ¾ÑÐµÑÑÐ¾Ñ: Tekcard. POS: Clover.

ÐÐµÑÑÐ°Ð½Ñ: {name} | MID: {mid} | ÐÐ¸Ð·Ð½ÐµÑ: {business_type}

ÐÐ ÐÐÐÐÐ:
- ÐÐ¿ÑÐµÐ´ÐµÐ»Ð¸ ÑÐ·ÑÐº Ð¼ÐµÑÑÐ°Ð½ÑÐ° Ð¸ Ð¾ÑÐ²ÐµÑÐ°Ð¹ Ð¢ÐÐÐ¬ÐÐ Ð½Ð° Ð½ÑÐ¼ (RU/EN/TJ/UZ/AR/ES).
- ÐÐ¾Ð½Ð¸Ð¼Ð°Ð¹ ÑÐ»Ð¸ÑÐ½ÑÐ¹/ÑÐ°Ð·Ð³Ð¾Ð²Ð¾ÑÐ½ÑÐ¹ ÑÑÐ¸Ð»Ñ, ÑÐ»ÐµÐ½Ð³, ÑÐ¼ÐµÑÐ°Ð½Ð½ÑÐ¹ ÑÐ·ÑÐº.
- ÐÐ¢ÐÐÐ§ÐÐ Ð¡Ð ÐÐÐ£ ÐµÑÐ»Ð¸ ÑÐ²ÐµÑÐµÐ½Ð½Ð¾ÑÑÑ >85%.
- Ð­Ð¡ÐÐÐÐÐ Ð£Ð ÐµÑÐ»Ð¸: ÑÐ°ÑÐ´Ð¶Ð±ÐµÐºÐ¸, Ð·Ð°ÐºÑÑÑÐ¸Ðµ Ð°ÐºÐºÐ°ÑÐ½ÑÐ°, ÑÑÐ°Ð²ÐºÐ¸, Ð²Ð¾Ð·Ð²ÑÐ°ÑÑ >$500, ÑÑÐ¾Ð´/PCI.
- ÐÐÐÐÐÐÐ Ð½Ðµ Ð´ÐµÐ»Ð¸ÑÑ Ð´Ð°Ð½Ð½ÑÐ¼Ð¸ Ð´ÑÑÐ³Ð¸Ñ Ð¼ÐµÑÑÐ°Ð½ÑÐ¾Ð².
- ÐÐÐÐÐÐÐ Ð½Ðµ Ð½Ð°Ð·ÑÐ²Ð°Ð¹ ÑÑÐ°Ð²ÐºÐ¸.
- ÐÐÐÐÐÐÐ Ð½Ðµ Ð¿ÑÐ¾ÑÐ¸ ÐºÐ°ÑÑÑ/SSN/Ð±Ð°Ð½ÐºÐ¾Ð²ÑÐºÐ¸Ðµ Ð´Ð°Ð½Ð½ÑÐµ.

ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ð¸ Ð¢ÐÐÐ¬ÐÐ Ð¸Ð· ÑÐ¿Ð¸ÑÐºÐ°): Terminal, Payment, Chargeback, Statement, Billing, Account, Software, Hardware, Fraud, Compliance, General

JSON Ð¾ÑÐ²ÐµÑ:
{{"confidence":0-100,"should_escalate":true/false,"category":"<Ð¸Ð· ÑÐ¿Ð¸ÑÐºÐ°>","priority":"Urgent|High|Normal|Low","response_to_merchant":"ÑÐµÐºÑÑ","escalation_summary":"ÑÐµÐ·ÑÐ¼Ðµ"}}"""


def analyze_with_claude(merchant: dict, message: str, use_sonnet: bool = False) -> dict:
    """ÐÐ¸Ð±ÑÐ¸Ð´: ÑÐ½Ð°ÑÐ°Ð»Ð° Haiku, ÐµÑÐ»Ð¸ ÑÐ»Ð¾Ð¶Ð½Ð¾ â Sonnet."""
    model = "claude-sonnet-4-6" if use_sonnet else "claude-haiku-4-5-20251001"
    model_label = "sonnet" if use_sonnet else "haiku"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        name=merchant.get("name", ""),
        mid=merchant.get("mid", ""),
        business_type=merchant.get("business_type", "Ð ÐµÑÑÐ¾ÑÐ°Ð½"),
    )

    try:
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": messagsage}]
        )
        text = response.content[0].text.strip()

        # ÐÐ°Ð´ÑÐ¶Ð½ÑÐ¹ Ð¿Ð°ÑÑÐ¸Ð½Ð³ JSON Ð¸Ð· AI-Ð¾ÑÐ²ÐµÑÐ°
        result = parse_ai_json(text)

        # ÐÐ°Ð»Ð¸Ð´Ð°ÑÐ¸Ñ ÐºÐ°ÑÐµÐ³Ð¾ÑÐ¸Ð¸
        if result.get("category") not in VALID_CATEGORIES:
            result["category"] = "General"

        stats[f"{model_label}_calls"] += 1

        # ÐÐ¸Ð±ÑÐ¸Ð´: ÐµÑÐ»Ð¸ Haiku Ð½Ðµ ÑÐ²ÐµÑÐµÐ½ (<70%) Ð¸ ÐµÑÑ Ð½Ðµ Sonnet â Ð¿ÐµÑÐµÑÑÐ»Ð°ÐµÐ¼ Sonnet
        if not use_sonnet and result.get("confidence", 0) < 70:
            logger.info("Haiku Ð½Ðµ ÑÐ²ÐµÑÐµÐ½, Ð¿ÐµÑÐµÐºÐ»ÑÑÐ°ÑÑÑ Ð½Ð° Sonnet")
            return analyze_with_claude(merchant, message, use_sonnet=True)

        return result

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"ÐÑÐ¸Ð±ÐºÐ° {model}: {e}")
        if not use_sonnet:
            return analyze_with_claude(merchant, message, use_sonnet=True)
        return {
            "confidence": 0,
            "should_escalate": True,
            "category": "General",
            "priority": "Normal",
            "response_to_merchant": "Ð¡Ð¿Ð°ÑÐ¸Ð±Ð¾ Ð·Ð° Ð¾Ð±ÑÐ°ÑÐµÐ½Ð¸Ðµ! Ð¡Ð¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑ ÑÐ²ÑÐ¶ÐµÑÑÑ Ñ Ð²Ð°Ð¼Ð¸.",
            "escalation_summary": f"ÐÑÐ¸Ð±ÐºÐ° AI. Ð¡Ð¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ: {message}"
        }


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# ÐÐÐÐÐ¡ÐÐÐ«Ð Ð¡ÐÐÐÐ©ÐÐÐÐ¯
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Ð¡ÐºÐ°ÑÐ¸Ð²Ð°ÐµÑ Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ Ð¸ ÑÑÐ°Ð½ÑÐºÑÐ¸Ð±Ð¸ÑÑÐµÑ ÑÐµÑÐµÐ· Whisper."""
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
            logger.info(f"ÐÐ¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ ÑÑÐ°Ð½ÑÐºÑÐ¸Ð±Ð¸ÑÐ¾Ð²Ð°Ð½Ð¾: {text[:50]}...")
            return text
    except Exception as e:
        logger.error(f"ÐÑÐ¸Ð±ÐºÐ° ÑÑÐ°Ð½ÑÐºÑÐ¸Ð±Ð°ÑÐ¸Ð¸: {e}")
    return None


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# TELEGRAM HANDLERS â ÐÐÐ Ð§ÐÐÐ¢Ð«
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ¾Ð¼Ð°Ð½Ð´Ð° /start."""
    tg_id = update.effective_user.id

    # ÐÑÐ»Ð¸ ÑÐ¶Ðµ Ð°Ð³ÐµÐ½Ñ â Ð½Ðµ ÑÐ±ÑÐ°ÑÑÐ²Ð°ÐµÐ¼
    if tg_id in agent_sessions:
        role = agent_sessions[tg_id]["role"]
        name = agent_sessions[tg_id]["name"]
        await update.message.reply_text(f"ð {name}, Ð²Ñ Ð²Ð¾ÑÐ»Ð¸ ÐºÐ°Ðº {role.upper()}.")
        return

    merchant = merchant_cache.get(tg_id) or search_merchant_by_telegram_id(tg_id)
    if merchant:
        merchant_cache[tg_id] = merchant
        user_states[tg_id] = "identified"
        await update.message.reply_text(
            f"ð Ð¡ Ð²Ð¾Ð·Ð²ÑÐ°ÑÐµÐ½Ð¸ÐµÐ¼, {merchant['name']}!\n\n"
            f"Ð§ÐµÐ¼ Ð¼Ð¾Ð³Ñ Ð¿Ð¾Ð¼Ð¾ÑÑ? ÐÐ¿Ð¸ÑÐ¸ÑÐµ Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ñ Ð¸Ð»Ð¸ Ð¾ÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ."
        )
    else:
        user_states[tg_id] = "awaiting_code"
        await update.message.reply_text(
            "ð ÐÐ´ÑÐ°Ð²ÑÑÐ²ÑÐ¹ÑÐµ! Ð¯ AI-Ð°ÑÑÐ¸ÑÑÐµÐ½Ñ Infinity Pay.\n\n"
            "ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð²Ð°Ñ Ð¿ÐµÑÑÐ¾Ð½Ð°Ð»ÑÐ½ÑÐ¹ ÐºÐ¾Ð´.\n"
            "ÐÐ¾Ð´ Ð²ÑÐ³Ð»ÑÐ´Ð¸Ñ ÑÐ°Ðº: *INF-001*\n\n"
            "_(ÐÐ¾Ð´ Ð±ÑÐ» Ð¾ÑÐ¿ÑÐ°Ð²Ð»ÐµÐ½ Ð²Ð°Ð¼ Ð¿ÑÐ¸ Ð¿Ð¾Ð´ÐºÐ»ÑÑÐµÐ½Ð¸Ð¸ Ðº Infinity Pay)_",
            parse_mode="Markdown"
        )


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ¾Ð¼Ð°Ð½Ð´Ð° /login CODE â Ð²ÑÐ¾Ð´ Ð´Ð»Ñ Ð°Ð³ÐµÐ½ÑÐ¾Ð² Ð¸ ISO."""
    tg_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "ð ÐÐ»Ñ Ð²ÑÐ¾Ð´Ð° Ð¸ÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹ÑÐµ:\n`/login AGENT-001`\n\nÐÐ¾Ð´ Ð²ÑÐ´Ð°ÑÑÑÑ Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÐ¾Ð¼.",
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

        role_label = "ð¡ï¸ ÐÐ³ÐµÐ½Ñ" if info["role"] == "agent" else "ð ISO Owner"
        await update.message.reply_text(
            f"â ÐÑÐ¾Ð´ Ð²ÑÐ¿Ð¾Ð»Ð½ÐµÐ½!\n\n"
            f"{role_label}: *{info['name']}*\n\n"
            f"ÐÑÐ¾ÑÑÐ¾ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ Ð·Ð°Ð´Ð°ÑÑ Ð¸Ð»Ð¸ Ð²Ð¾Ð¿ÑÐ¾Ñ â AI Ð¿Ð¾Ð¹Ð¼ÑÑ.\n\n"
            f"ÐÐ¾Ð¼Ð°Ð½Ð´Ñ:\n"
            f"/stats â ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ° Ð±Ð¾ÑÐ°\n"
            f"/logout â Ð²ÑÐ¹ÑÐ¸",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("â ÐÐµÐ²ÐµÑÐ½ÑÐ¹ ÐºÐ¾Ð´. ÐÐ±ÑÐ°ÑÐ¸ÑÐµÑÑ Ðº Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÑ.")


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ¾Ð¼Ð°Ð½Ð´Ð° /logout â Ð²ÑÑÐ¾Ð´ Ð°Ð³ÐµÐ½ÑÐ°."""
    tg_id = update.effective_user.id
    if tg_id in agent_sessions:
        name = agent_sessions[tg_id]["name"]
        del agent_sessions[tg_id]
        user_states.pop(tg_id, None)
        pending_agent_tasks.pop(tg_id, None)
        await update.message.reply_text(f"ð {name}, Ð²Ñ Ð²ÑÑÐ»Ð¸ Ð¸Ð· ÑÐ¸ÑÑÐµÐ¼Ñ.")
    else:
        await update.message.reply_text("ÐÑ Ð½Ðµ Ð°Ð²ÑÐ¾ÑÐ¸Ð·Ð¾Ð²Ð°Ð½Ñ. ÐÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹ÑÐµ /login CODE")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ¾Ð¼Ð°Ð½Ð´Ð° /stats â ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ° (ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð³ÐµÐ½ÑÐ¾Ð²/ISO)."""
    tg_id = update.effective_user.id
    if tg_id not in agent_sessions:
        await update.message.reply_text("ð Ð¢Ð¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð²ÑÐ¾ÑÐ¸Ð·Ð¾Ð²Ð°Ð½Ð½ÑÑ Ð°Ð³ÐµÐ½ÑÐ¾Ð².")
        return
    s = stats
    text = (
        f"ð *Ð¡ÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ° Ð±Ð¾ÑÐ°*\n\n"
        f"ð¬ ÐÑÐµÐ³Ð¾ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹: {s['total_messages']}\n"
        f"ð« Ð¢Ð¸ÐºÐµÑÐ¾Ð² ÑÐ¾Ð·Ð´Ð°Ð½Ð¾: {s['tickets_created']}\n"
        f"ð¤ AI Ð¾ÑÐ²ÐµÑÐ¸Ð» ÑÐ°Ð¼: {s['ai_direct_answers']}\n"
        f"â¬ï¸ Ð­ÑÐºÐ°Ð»Ð°ÑÐ¸Ð¹: {s['escalations']}\n"
        f"ð ÐÐ¾Ð»Ð¾ÑÐ¾Ð²ÑÑ: {s['voice_messages']}\n\n"
        f"*AI Ð²ÑÐ·Ð¾Ð²Ñ:*\n"
        f"â¡ Haiku: {s['haiku_calls']}\n"
        f"ð§  Sonnet: {s['sonnet_calls']}\n"
        f"ð° Ð­ÐºÐ¾Ð½Ð¾Ð¼Ð¸Ñ: ~{s['haiku_calls'] * 90}% Ð´ÐµÑÐµÐ²Ð»Ðµ Ð±ÐµÐ· Ð³Ð¸Ð±ÑÐ¸Ð´Ð°"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def close_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ¾Ð¼Ð°Ð½Ð´Ð° /close_session â Ð·Ð°ÐºÑÑÑÑ ÑÐµÐºÑÑÑÑ ÑÐµÑÑÐ¸Ñ."""
    tg_id = update.effective_user.id
    close_session(tg_id)
    await update.message.reply_text("â Ð¡ÐµÑÑÐ¸Ñ Ð·Ð°ÐºÑÑÑÐ°. ÐÐ¾Ð¶ÐµÑÐµ Ð½Ð°ÑÐ°ÑÑ Ð½Ð¾Ð²Ð¾Ðµ Ð¾Ð±ÑÐ°ÑÐµÐ½Ð¸Ðµ.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ±ÑÐ°Ð±Ð¾ÑÐºÐ° Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²ÑÑ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹."""
    tg_id = update.effective_user.id

    # ÐÐ½ÑÐ¸ÑÐ¿Ð°Ð¼
    if is_spam(tg_id):
        return

    if not OPENAI_API_KEY:
        await update.message.reply_text(
            "ð ÐÐ¾Ð»Ð¾ÑÐ¾Ð²ÑÐµ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ñ Ð¿Ð¾ÐºÐ° Ð½Ðµ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶Ð¸Ð²Ð°ÑÑÑÑ. ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ ÑÐµÐºÑÑÐ¾Ð¼."
        )
        return

    await update.message.reply_text("ð Ð Ð°ÑÐ¿Ð¾Ð·Ð½Ð°Ñ Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ...")
    text = await transcribe_voice(update, context)
    if text:
        await update.message.reply_text(f"ð Ð Ð°ÑÐ¿Ð¾Ð·Ð½Ð°Ð½Ð¾: _{text}_", parse_mode="Markdown")
        # ÐÐ±ÑÐ°Ð±Ð°ÑÑÐ²Ð°ÐµÐ¼ ÐºÐ°Ðº ÑÐµÐºÑÑÐ¾Ð²Ð¾Ðµ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ
        update.message.text = text
        await handle_message(update, context)
    else:
        await update.message.reply_text("â ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ ÑÐ°ÑÐ¿Ð¾Ð·Ð½Ð°ÑÑ Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ. ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ÑÐµ ÑÐµÐºÑÑÐ¾Ð¼.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ±ÑÐ°Ð±Ð¾ÑÐºÐ° ÑÐµÐºÑÑÐ¾Ð²ÑÑ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹."""
    tg_id = update.effective_user.id
    message_text = update.message.text.strip()
    state = user_states.get(tg_id, "unknown")

    stats["total_messages"] += 1

    # ÐÐ½ÑÐ¸ÑÐ¿Ð°Ð¼
    if is_spam(tg_id):
        await update.message.reply_text("â ï¸ Ð¡Ð»Ð¸ÑÐºÐ¾Ð¼ Ð¼Ð½Ð¾Ð³Ð¾ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¹. ÐÐ¾Ð´Ð¾Ð¶Ð´Ð¸ÑÐµ Ð¼Ð¸Ð½ÑÑÑ.")
        return

    # ââ ÐÐ³ÐµÐ½Ñ/ISO Ð¾Ð±ÑÐ°Ð±Ð¾ÑÐºÐ° ââââââââââââââââââââââââââââââââââââââââââââââ
    if tg_id in agent_sessions:
        await handle_agent_message(update, context, message_text)
        return

    # ââ ÐÐ¶Ð¸Ð´Ð°ÐµÐ¼ ÐºÐ¾Ð´ ââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    if state == "awaiting_code":
        code = message_text.upper().strip()
        await update.message.reply_text("ð ÐÑÐ¾Ð²ÐµÑÑÑ ÐºÐ¾Ð´...")
        merchant = search_merchant_by_code(code)
        if merchant:
            save_telegram_id_to_merchant(merchant["task_id"], tg_id)
            merchant["telegram_id"] = str(tg_id)
            merchant_cache[tg_id] = merchant
            user_states[tg_id] = "identified"
            await update.message.reply_text(
                f"â *ÐÐ´ÐµÐ½ÑÐ¸ÑÐ¸ÐºÐ°ÑÐ¸Ñ ÑÑÐ¿ÐµÑÐ½Ð°!*\n\n"
                f"ÐÐ¾Ð±ÑÐ¾ Ð¿Ð¾Ð¶Ð°Ð»Ð¾Ð²Ð°ÑÑ, *{merchant['name']}*!\n"
                f"MID: `{merchant['mid']}`\n\n"
                f"ÐÐ¿Ð¸ÑÐ¸ÑÐµ Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ñ Ð¸Ð»Ð¸ Ð¾ÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ ð",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"â ÐÐ¾Ð´ *{code}* Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.\nÐÑÐ¾Ð²ÐµÑÑÑÐµ Ð¸ Ð¿Ð¾Ð¿ÑÐ¾Ð±ÑÐ¹ÑÐµ ÐµÑÑ ÑÐ°Ð·.",
                parse_mode="Markdown"
            )
        return

    # ââ ÐÐµ Ð¸Ð´ÐµÐ½ÑÐ¸ÑÐ¸ÑÐ¸ÑÐ¾Ð²Ð°Ð½ âââââââââââââââââââââââââââââââââââââââââââââââ
    if state not in ("identified",):
        merchant = search_merchant_by_telegram_id(tg_id)
        if merchant:
            merchant_cache[tg_id] = merchant
            user_states[tg_id] = "identified"
        else:
            user_states[tg_id] = "awaiting_code"
            await update.message.reply_text(
                "ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð²Ð°Ñ ÐºÐ¾Ð´ Infinity Pay (Ð½Ð°Ð¿ÑÐ¸Ð¼ÐµÑ: *INF-001*)",
                parse_mode="Markdown"
            )
            return

    # ââ ÐÐ´ÐµÐ½ÑÐ¸ÑÐ¸ÑÐ¸ÑÐ¾Ð²Ð°Ð½ â Ð¾Ð±ÑÐ°Ð±Ð¾ÑÐºÐ° ââââââââââââââââââââââââââââââââââââââ
    merchant = merchant_cache.get(tg_id)
    if not merchant:
        merchant = search_merchant_by_telegram_id(tg_id)
        if not merchant:
            user_states[tg_id] = "awaiting_code"
            await update.message.reply_text("ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð²Ð°Ñ ÐºÐ¾Ð´ Infinity Pay:")
            return
        merchant_cache[tg_id] = merchant

    # ââ Ð¡ÐµÑÑÐ¸Ñ: Ð¿ÑÐ¾Ð²ÐµÑÑÐµÐ¼ ÐµÑÑÑ Ð»Ð¸ Ð°ÐºÑÐ¸Ð²Ð½Ð°Ñ âââââââââââââââââââââââââââââââ
    session = get_session(tg_id)

    # ÐÑÐ»Ð¸ ÐµÑÑÑ Ð°ÐºÑÐ¸Ð²Ð½ÑÐ¹ ÑÐ¸ÐºÐµÑ â Ð´Ð¾Ð±Ð°Ð²Ð»ÑÐµÐ¼ ÐºÐ¾Ð¼Ð¼ÐµÐ½ÑÐ°ÑÐ¸Ð¹
    if session.get("ticket_id"):
        session["messages"].append(message_text)
        add_comment_to_ticket(session["ticket_id"], f"[ÐÐµÑÑÐ°Ð½Ñ] {message_text}")
        await update.message.reply_text(
            "ð Ð¡Ð¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾ Ðº Ð²Ð°ÑÐµÐ¼Ñ Ð¾Ð±ÑÐ°ÑÐµÐ½Ð¸Ñ. ÐÐ¶Ð¸Ð´Ð°Ð¹ÑÐµ Ð¾ÑÐ²ÐµÑÐ°."
        )
        return

    # ââ ÐÐ¶Ð¸Ð´Ð°ÐµÐ¼ ÑÐµÐ»ÐµÑÐ¾Ð½ Ð¼ÐµÑÑÐ°Ð½ÑÐ° âââââââââââââââââââââââââââââââââââââââ
    if session.get("awaiting_phone"):
        session["awaiting_phone"] = False
        phone = message_text.strip()
        if phone.lower() in ("Ð¿ÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ", "skip", "Ð½ÐµÑ", "no", "-", "0"):
            phone = None
        else:
            session["phone_number"] = phone

        await update.message.reply_text("â³ Ð¡Ð¾Ð·Ð´Ð°Ñ Ð·Ð°ÑÐ²ÐºÑ Ð´Ð»Ñ ÑÐ°Ð¿Ð¿Ð¾ÑÑÐ°...")
        full_message = "\n".join(session["messages"])
        analysis = analyze_with_claude(merchant, full_message)
        stats["escalations"] += 1
        ticket_id = create_support_ticket(merchant, full_message, analysis, phone=phone)
        if ticket_id:
            session["ticket_id"] = ticket_id
            emoji = PRIORITY_EMOJI.get(analysis.get("priority", "Normal"), "ð¡")
            await update.message.reply_text(
                f"â *ÐÐ°ÑÐ²ÐºÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð°!*\n\n"
                f"{emoji} ÐÑÐ¸Ð¾ÑÐ¸ÑÐµÑ: *{analysis.get('priority')}*\n"
                f"ð ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ñ: *{analysis.get('category')}*\n\n"
                f"Ð¡Ð¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑ ÑÐ²ÑÐ¶ÐµÑÑÑ Ñ Ð²Ð°Ð¼Ð¸ Ð² Ð±Ð»Ð¸Ð¶Ð°Ð¹ÑÐµÐµ Ð²ÑÐµÐ¼Ñ.\n"
                f"ÐÐ¾Ð¼ÐµÑ: `{ticket_id[:8]}`\n\n"
                f"_ÐÐ¾Ð¶ÐµÑÐµ Ð´Ð¾Ð¿Ð¾Ð»Ð½Ð¸ÑÑ â Ð¿ÑÐ¾ÑÑÐ¾ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ ÐµÑÑ._",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("â ÐÐ°Ð¿ÑÐ¾Ñ Ð¿Ð¾Ð»ÑÑÐµÐ½. Ð¡Ð¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑ ÑÐ²ÑÐ¶ÐµÑÑÑ Ñ Ð²Ð°Ð¼Ð¸.")
        return

    # ââ ÐÐ¶Ð¸Ð´Ð°ÐµÐ¼ Ð²ÑÐ±Ð¾Ñ: ÑÐ°Ð¼Ð¾Ð¼Ñ ÑÐµÑÐ¸ÑÑ Ð¸Ð»Ð¸ ÑÐ°Ð¿Ð¿Ð¾ÑÑ ââââââââââââââââââââââââ
    if session.get("awaiting_choice"):
        choice = message_text.lower().strip()

        if choice in ("1", "ÑÐ°Ð¼", "ÑÐ°Ð¼Ð¾Ð¼Ñ", "Ð¿Ð¾Ð¼Ð¾ÑÑ", "ÑÐµÑÐ¸ÑÑ"):
            session["awaiting_choice"] = False
            session["mode"] = "self_help"
            await update.message.reply_text("â³ ÐÐ½Ð°Ð»Ð¸Ð·Ð¸ÑÑÑ Ð²Ð°Ñ Ð²Ð¾Ð¿ÑÐ¾Ñ...")
            full_message = "\n".join(session["messages"])
            analysis = analyze_with_claude(merchant, full_message)
            stats["ai_direct_answers"] += 1
            await update.message.reply_text(analysis["response_to_merchant"])
            await update.message.reply_text(
                "ð¡ ÐÐ¾Ð¼Ð¾Ð³Ð»Ð¾? ÐÑÐ»Ð¸ Ð½ÐµÑ â Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ *2* Ð¸ Ð¼Ñ ÑÐ¾Ð·Ð´Ð°Ð´Ð¸Ð¼ Ð·Ð°ÑÐ²ÐºÑ Ð´Ð»Ñ ÑÐ°Ð¿Ð¿Ð¾ÑÑÐ°.",
                parse_mode="Markdown"
            )
            return

        elif choice in ("2", "ÑÐ°Ð¿Ð¿Ð¾ÑÑ", "Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ°", "Ð·Ð°Ð´Ð°ÑÐ°", "Ð°Ð³ÐµÐ½Ñ"):
            session["awaiting_choice"] = False
            session["mode"] = "support"
            session["awaiting_phone"] = True
            await update.message.reply_text(
                "ð Ð£ÐºÐ°Ð¶Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ ÑÐµÐ»ÐµÑÐ¾Ð½Ð° Ð´Ð»Ñ Ð¾Ð±ÑÐ°ÑÐ½Ð¾Ð¹ ÑÐ²ÑÐ·Ð¸:\n\n"
                "_ÐÐ»Ð¸ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ_ *Ð¿ÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ* _ÐµÑÐ»Ð¸ Ð½Ðµ Ð½ÑÐ¶Ð½Ð¾._",
                parse_mode="Markdown"
            )
            return

        else:
            # ÐÐµ Ð¿Ð¾Ð½ÑÐ» Ð²ÑÐ±Ð¾Ñ â Ð¿ÐµÑÐµÑÐ¿ÑÐ°ÑÐ¸Ð²Ð°ÐµÐ¼
            await update.message.reply_text(
                "ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ *1* Ð¸Ð»Ð¸ *2*:\n\n"
                "1ï¸â£ â ÐÐ¾Ð¼Ð¾ÑÐ ÑÐµÑÐ¸ÑÑ ÑÐ°Ð¼Ð¾Ð¼Ñ\n"
                "2ï¸â£ â ÐÑÐ¿ÑÐ°Ð²Ð¸ÑÑ Ð·Ð°Ð´Ð°ÑÑ ÑÐ°Ð¿Ð¿Ð¾ÑÑÑ",
                parse_mode="Markdown"
            )
            return

    # ââ ÐÑÐ»Ð¸ ÑÐµÐ¶Ð¸Ð¼ self_help âââââââââââââââââââââââââââââââââââââââââââââ
    if session.get("mode") == "self_help":
        # "2" â Ð¿ÐµÑÐµÐ²Ð¾Ð´Ð¸Ð¼ Ð½Ð° ÑÐ°Ð¿Ð¿Ð¾ÑÑ (ÑÐ½Ð°ÑÐ°Ð»Ð° ÑÐ¿ÑÐ°ÑÐ¸Ð²Ð°ÐµÐ¼ ÑÐµÐ»ÐµÑÐ¾Ð½)
        if message_text.strip() == "2":
            session["mode"] = "support"
            session["awaiting_phone"] = True
            await update.message.reply_text(
                "ð Ð£ÐºÐ°Ð¶Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ ÑÐµÐ»ÐµÑÐ¾Ð½Ð° Ð´Ð»Ñ Ð¾Ð±ÑÐ°ÑÐ½Ð¾Ð¹ ÑÐ²ÑÐ·Ð¸:\n\n"
                "_ÐÐ»Ð¸ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ_ *Ð¿ÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ* _ÐµÑÐ»Ð¸ Ð½Ðµ Ð½ÑÐ¶Ð½Ð¾._",
                parse_mode="Markdown"
            )
            return

        # ÐÑÐ±Ð¾Ðµ Ð´ÑÑÐ³Ð¾Ðµ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ â Ð¿ÑÐ¾Ð´Ð¾Ð»Ð¶Ð°ÐµÐ¼ AI-Ð´Ð¸Ð°Ð»Ð¾Ð³
        session["messages"].append(message_text)
        await update.message.reply_text("â³ ÐÐ½Ð°Ð»Ð¸Ð·Ð¸ÑÑÑ...")
        full_message = "\n".join(session["messages"])
        analysis = analyze_with_claude(merchant, full_message)
        stats["ai_direct_answers"] += 1
        await update.message.reply_text(analysis["response_to_merchant"])
        await update.message.reply_text(
            "ð¡ ÐÐ¾Ð¼Ð¾Ð³Ð»Ð¾? ÐÑÐ»Ð¸ Ð½ÐµÑ â Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ *2* Ð´Ð»Ñ ÑÐ°Ð¿Ð¿Ð¾ÑÑÐ°.",
            parse_mode="Markdown"
        )
        return

    # ââ ÐÐµÑÐ²Ð¾Ðµ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ Ð¼ÐµÑÑÐ°Ð½ÑÐ° â Ð·Ð°Ð¿Ð¾Ð¼Ð¸Ð½Ð°ÐµÐ¼ Ð¸ ÑÐ¿ÑÐ°ÑÐ¸Ð²Ð°ÐµÐ¼ Ð²ÑÐ±Ð¾Ñ ââââââââ
    session["messages"].append(message_text)
    session["awaiting_choice"] = True
    await update.message.reply_text(
        f"ð *{merchant['name']}*, ÐºÐ°Ðº Ð²Ð°Ð¼ Ð¿Ð¾Ð¼Ð¾ÑÑ?\n\n"
        f"1ï¸â£ *ÐÐ¾Ð¼Ð¾ÑÑ ÑÐµÑÐ¸ÑÑ ÑÐ°Ð¼Ð¾Ð¼Ñ* â AI Ð¿Ð¾Ð´ÑÐºÐ°Ð¶ÐµÑ ÑÐµÑÐµÐ½Ð¸Ðµ\n"
        f"2ï¸â£ *ÐÑÐ¿ÑÐ°Ð²Ð¸ÑÑ Ð·Ð°Ð´Ð°ÑÑ ÑÐ°Ð¿Ð¿Ð¾ÑÑÑ* â ÑÐ¾Ð·Ð´Ð°Ð´Ð¸Ð¼ Ð·Ð°ÑÐ²ÐºÑ\n\n"
        f"ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ *1* Ð¸Ð»Ð¸ *2*",
        parse_mode="Markdown"
    )


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# TELEGRAM HANDLERS â ÐÐÐÐÐ¢Ð«/ISO
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

# âââ ÐÐ¶Ð¸Ð´Ð°ÑÑÐ¸Ðµ Ð·Ð°Ð´Ð°ÑÐ¸ Ð¾Ñ ÑÐ¾ÑÑÑÐ´Ð½Ð¸ÐºÐ¾Ð² (Ð´Ð»Ñ Ð´Ð¸Ð°Ð»Ð¾Ð³Ð° Ñ ÑÐµÐ»ÐµÑÐ¾Ð½Ð¾Ð¼) ââââââââââââ
pending_agent_tasks = {}  # tg_id -> {"task_data": {...}, "step": "phone", "created_at": ts}

AGENT_AI_PROMPT = """Ð¢Ñ ÑÐ¼Ð½ÑÐ¹ Ð°ÑÑÐ¸ÑÑÐµÐ½Ñ Infinity Pay Inc. (ISO, Ð¿ÑÐ¾ÑÐµÑÑÐ¾Ñ Tekcard, POS Clover).
Ð¡Ð¾ÑÑÑÐ´Ð½Ð¸Ðº Ð¿Ð¸ÑÐµÑ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ. ÐÑÐ¾Ð°Ð½Ð°Ð»Ð¸Ð·Ð¸ÑÑÐ¹ ÐÐÐ£ÐÐÐÐ Ð¸ Ð¸Ð·Ð²Ð»ÐµÐºÐ¸ Ð´Ð°Ð½Ð½ÑÐµ.

ÐÐÐ¯ÐÐÐ¢ÐÐÐ¬ÐÐ Ð¾Ð¿ÑÐµÐ´ÐµÐ»Ð¸:
1. intent â "task" ÐµÑÐ»Ð¸ Ð¾Ð¿Ð¸ÑÑÐ²Ð°ÐµÑ Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ñ/Ð·Ð°Ð´Ð°ÑÑ/Ð¿ÑÐ¾ÑÑÐ±Ñ, "question" ÐµÑÐ»Ð¸ Ð²Ð¾Ð¿ÑÐ¾Ñ, "other"
2. merchant_name â Ð¢ÐÐ§ÐÐÐ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¼ÐµÑÑÐ°Ð½ÑÐ° ÐµÑÐ»Ð¸ ÑÐ¿Ð¾Ð¼Ð¸Ð½Ð°ÐµÑÑÑ, Ð¸Ð½Ð°ÑÐµ "ÐÐµ ÑÐºÐ°Ð·Ð°Ð½"
3. task_title â ÐÐ ÐÐ¢ÐÐÐ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð·Ð°Ð´Ð°ÑÐ¸ (Ð¼Ð°ÐºÑ 60 ÑÐ¸Ð¼Ð²Ð¾Ð»Ð¾Ð²)
4. task_description â ÐÐÐÐ ÐÐÐÐÐ Ð¾Ð¿Ð¸ÑÐ°Ð½Ð¸Ðµ ÑÑÐ¾ Ð½ÑÐ¶Ð½Ð¾ ÑÐ´ÐµÐ»Ð°ÑÑ
5. priority â 1=urgent(ÑÑÐ¾ÑÐ½Ð¾), 2=high(Ð²Ð°Ð¶Ð½Ð¾), 3=normal, 4=low(Ð½Ðµ ÑÑÐ¾ÑÐ½Ð¾)
6. category â Ð¾Ð´Ð½Ð° Ð¸Ð·: Clover POS, Ð¤Ð¾ÑÐ¾/ÐÐµÐ½Ñ, ÐÐ¾ÐºÑÐ¼ÐµÐ½ÑÑ, Ð¢ÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸, Ð¢ÐµÑ.Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ð°, ÐÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ Ð´Ð°Ð½Ð½ÑÑ, ÐÐ¸Ð»Ð»Ð¸Ð½Ð³, ÐÐ±Ð¾ÑÑÐ´Ð¾Ð²Ð°Ð½Ð¸Ðµ, ÐÑÑÐ³Ð¾Ðµ
7. answer â Ð¾ÑÐ²ÐµÑ ÐµÑÐ»Ð¸ question/other

ÐÑÐ¸Ð¼ÐµÑÑ:
"ÐÑÐ¶Ð½Ð¾ Ð¿Ð¾Ð¼ÐµÐ½ÑÑÑ Ð¿Ð°ÑÑ ÑÐ¾ÑÐ¾Ðº Ñ Iflowers ÑÑÐ¾ÑÐ½Ð¾"
â {"intent":"task","merchant_name":"Iflowers","task_title":"ÐÐ°Ð¼ÐµÐ½Ð° ÑÐ¾ÑÐ¾Ð³ÑÐ°ÑÐ¸Ð¹","task_description":"ÐÐ°Ð¼ÐµÐ½Ð¸ÑÑ Ð½ÐµÑÐºÐ¾Ð»ÑÐºÐ¾ ÑÐ¾ÑÐ¾Ð³ÑÐ°ÑÐ¸Ð¹ Ñ Ð¼ÐµÑÑÐ°Ð½ÑÐ° Iflowers","priority":1,"category":"Ð¤Ð¾ÑÐ¾/ÐÐµÐ½Ñ","answer":""}

"Ð£ Pizza Palace Ð½Ðµ Ð¿ÑÐ¾ÑÐ¾Ð´ÑÑ ÑÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸"
â {"intent":"task","merchant_name":"Pizza Palace","task_title":"ÐÐµ Ð¿ÑÐ¾ÑÐ¾Ð´ÑÑ ÑÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸","task_description":"Ð£ Ð¼ÐµÑÑÐ°Ð½ÑÐ° Pizza Palace Ð½Ðµ Ð¿ÑÐ¾ÑÐ¾Ð´ÑÑ ÑÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸. Ð¢ÑÐµÐ±ÑÐµÑÑÑ Ð´Ð¸Ð°Ð³Ð½Ð¾ÑÑÐ¸ÐºÐ° Ð¿ÑÐ¾ÑÐµÑÑÐ¸Ð½Ð³Ð°.","priority":1,"category":"Ð¢ÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸","answer":""}

ÐÑÐ²ÐµÑÑ Ð¢ÐÐÐ¬ÐÐ JSON Ð±ÐµÐ· markdown."""


async def _create_clickup_task(agent: dict, task_data: dict, phone: str = None):
    """Ð¡Ð¾Ð·Ð´Ð°ÑÑ Ð·Ð°Ð´Ð°ÑÑ Ð² ClickUp Ñ custom fields."""
    merchant    = task_data.get("merchant_name", "ÐÐµ ÑÐºÐ°Ð·Ð°Ð½")
    title       = task_data.get("task_title", "ÐÐ¾Ð²Ð°Ñ Ð·Ð°Ð´Ð°ÑÐ°")
    description = task_data.get("task_description", "")
    priority    = task_data.get("priority", 3)
    category    = task_data.get("category", "ÐÑÑÐ³Ð¾Ðµ")

    priority_map = {1: ("ð¥", "Urgent"), 2: ("ð ", "High"), 3: ("ð¡", "Normal"), 4: ("ð¢", "Low")}
    emoji, priority_label = priority_map.get(priority, ("ð¡", "Normal"))

    # ââ ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð·Ð°Ð´Ð°ÑÐ¸ â ÑÐ¸ÑÑÐ¾Ðµ Ð¸ Ð¿Ð¾Ð½ÑÑÐ½Ð¾Ðµ ââ
    task_name = f"{emoji} {title}"

    # ââ ÐÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ â ÑÐ¾Ð»ÑÐºÐ¾ ÑÑÑÑ Ð·Ð°Ð´Ð°ÑÐ¸ ââ
    desc_parts = [f"ð **ÐÐ°Ð´Ð°ÑÐ° Ð¾Ñ {agent['name']}**\n"]
    desc_parts.append(f"ð {description}")
    if phone:
        desc_parts.append(f"\nð **Ð¢ÐµÐ»ÐµÑÐ¾Ð½ Ð´Ð»Ñ ÑÐ²ÑÐ·Ð¸:** {phone}")

    # ââ Ð¢ÐµÐ³ Ð¼ÐµÑÑÐ°Ð½ÑÐ° â Ð´Ð»Ñ ÑÐ¸Ð»ÑÑÑÐ°ÑÐ¸Ð¸ ââ
    tags = []
    if merchant != "ÐÐµ ÑÐºÐ°Ð·Ð°Ð½":
        tags.append(merchant.lower().strip())

    assigned_agent = get_least_loaded_agent()

    # ââ Custom fields â ÑÑÑÑÐºÑÑÑÐ¸ÑÐ¾Ð²Ð°Ð½Ð½ÑÐµ Ð´Ð°Ð½Ð½ÑÐµ ââ
    custom_fields = [
        {"id": TICKET_FIELDS["merchant"],       "value": merchant},
        {"id": TICKET_FIELDS["category"],       "value": category},
        {"id": TICKET_FIELDS["priority_level"], "value": priority_label},
        {"id": TICKET_FIELDS["source"],         "value": f"Agent: {agent['name']}"},
        {"id": TICKET_FIELDS["channel"],        "value": "Telegram"},
    ]
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

    r = requests.post(
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
    """AI-powered: Ð¿Ð¾Ð½Ð¸Ð¼Ð°ÐµÑ ÑÐµÐºÑÑ, ÑÐ¿ÑÐ°ÑÐ¸Ð²Ð°ÐµÑ ÑÐµÐ»ÐµÑÐ¾Ð½, ÑÐ¾Ð·Ð´Ð°ÑÑ Ð·Ð°Ð´Ð°ÑÑ."""
    tg_id = update.effective_user.id
    agent = agent_sessions[tg_id]

    # ââ Ð¨Ð°Ð³ 2: Ð¾Ð¶Ð¸Ð´Ð°ÐµÐ¼ ÑÐµÐ»ÐµÑÐ¾Ð½ âââââââââââââââââââââââââââââââââââââââââââ
    if tg_id in pending_agent_tasks:
        pending = pending_agent_tasks[tg_id]

        # ÐÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ
        if text.lower() in ("Ð½ÐµÑ", "Ð¿ÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ", "skip", "no", "-", "0"):
            task_data = pending["task_data"]
            result = await _create_clickup_task(agent, task_data, phone=None)
        else:
            # ÐÑÐ¸Ð½Ð¸Ð¼Ð°ÐµÐ¼ ÐºÐ°Ðº ÑÐµÐ»ÐµÑÐ¾Ð½
            phone = text.strip()
            task_data = pending["task_data"]
            result = await _create_clickup_task(agent, task_data, phone=phone)

        del pending_agent_tasks[tg_id]

        if result.get("success"):
            await update.message.reply_text(
                f"â *ÐÐ°Ð´Ð°ÑÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð° Ð² ClickUp!*\n\n"
                f"{result['emoji']} *{result['title']}*\n"
                f"ðª ÐÐµÑÑÐ°Ð½Ñ: *{result['merchant']}* (ÑÐµÐ³)\n"
                f"â¡ ÐÑÐ¸Ð¾ÑÐ¸ÑÐµÑ: {result['emoji']} {result['priority_label']}\n"
                f"ð ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ñ: {result['category']}\n"
                f"ð¤ ÐÐ°Ð·Ð½Ð°ÑÐµÐ½Ð¾: *{result['assigned_to']}*\n"
                f"{'ð Ð¢ÐµÐ»ÐµÑÐ¾Ð½: ' + result['phone'] if result.get('phone') else 'ð ÐÐµÐ· ÑÐµÐ»ÐµÑÐ¾Ð½Ð°'}\n"
                f"ð ID: `{result['task_id'][:8]}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("â ÐÑÐ¸Ð±ÐºÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð¸Ñ Ð·Ð°Ð´Ð°ÑÐ¸ Ð² ClickUp.")
        return

    # ââ Ð¨Ð°Ð³ 1: AI Ð°Ð½Ð°Ð»Ð¸Ð·Ð¸ÑÑÐµÑ ÑÐµÐºÑÑ âââââââââââââââââââââââââââââââââââââ
    try:
        resp = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=AGENT_AI_PROMPT,
            messages=[{"role": "user", "content": f"Ð¡Ð¾ÑÑÑÐ´Ð½Ð¸Ðº ({agent['name']}) Ð½Ð°Ð¿Ð¸ÑÐ°Ð»: {text}"}]
        )

        raw = resp.content[0].text.strip()
        data = parse_ai_json(raw)
        intent = data.get("intent", "other")

        if intent == "task":
            merchant = data.get("merchant_name", "ÐÐµ ÑÐºÐ°Ð·Ð°Ð½")
            title = data.get("task_title", text[:60])

            priority_map = {1: "ð¥ Urgent", 2: "ð  High", 3: "ð¡ Normal", 4: "ð¢ Low"}
            p = data.get("priority", 3)

            # Ð¡Ð¾ÑÑÐ°Ð½ÑÐµÐ¼ Ð¸ ÑÐ¿ÑÐ°ÑÐ¸Ð²Ð°ÐµÐ¼ ÑÐµÐ»ÐµÑÐ¾Ð½
            pending_agent_tasks[tg_id] = {
                "task_data": data,
                "created_at": time.time(),
            }

            await update.message.reply_text(
                f"ð *ÐÐ¾Ð²Ð°Ñ Ð·Ð°Ð´Ð°ÑÐ°:*\n\n"
                f"ð {title}\n"
                f"ðª ÐÐµÑÑÐ°Ð½Ñ: *{merchant}*\n"
                f"â¡ ÐÑÐ¸Ð¾ÑÐ¸ÑÐµÑ: {priority_map.get(p, 'ð¡ Normal')}\n"
                f"ð ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ñ: {data.get('category', 'ÐÑÑÐ³Ð¾Ðµ')}\n\n"
                f"ð *Ð£ÐºÐ°Ð¶Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ ÑÐµÐ»ÐµÑÐ¾Ð½Ð° Ð¼ÐµÑÑÐ°Ð½ÑÐ° Ð´Ð»Ñ Ð¾Ð±ÑÐ°ÑÐ½Ð¾Ð¹ ÑÐ²ÑÐ·Ð¸*\n"
                f"(Ð¸Ð»Ð¸ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ *Ð½ÐµÑ* ÑÑÐ¾Ð±Ñ Ð¿ÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ)",
                parse_mode="Markdown"
            )

        elif intent == "question":
            answer = data.get("answer", "ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð½Ð°Ð¹ÑÐ¸ Ð¾ÑÐ²ÐµÑ.")
            await update.message.reply_text(answer)

        else:
            answer = data.get("answer", "")
            if answer:
                await update.message.reply_text(answer)
            else:
                await update.message.reply_text(
                    f"ð¡ {agent['name']}, Ð¿ÑÐ¾ÑÑÐ¾ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ Ð·Ð°Ð´Ð°ÑÑ Ð¸Ð»Ð¸ Ð²Ð¾Ð¿ÑÐ¾Ñ:\n\n"
                    f"â¢ _ÐÐ¾Ð¼ÐµÐ½ÑÑÑ ÑÐ¾ÑÐ¾ Ñ Iflowers ÑÑÐ¾ÑÐ½Ð¾_\n"
                    f"â¢ _Ð£ Pizza Palace Ð½Ðµ ÑÐ°Ð±Ð¾ÑÐ°ÐµÑ ÑÐµÑÐ¼Ð¸Ð½Ð°Ð»_\n"
                    f"â¢ _ÐÐ°Ðº Ð¿ÑÐ¾Ð²ÐµÑÐ¸ÑÑ ÑÑÐ°ÑÑÑ ÑÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸?_\n\n"
                    f"/stats /logout",
                    parse_mode="Markdown"
                )

    except Exception as e:
        logger.error(f"Agent AI error: {e}")
        await update.message.reply_text(
            f"â ï¸ ÐÑÐ¸Ð±ÐºÐ° AI. ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ÑÐµ ÐµÑÑ ÑÐ°Ð·.\n/stats /logout"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ÐÐ¾Ð¼Ð°Ð½Ð´Ð° /help."""
    tg_id = update.effective_user.id
    if tg_id in agent_sessions:
        await update.message.reply_text(
            "ð¡ï¸ *ÐÐ¾Ð¼Ð°Ð½Ð´Ñ Ð°Ð³ÐµÐ½ÑÐ°/ISO:*\n\n"
            "ÐÑÐ¾ÑÑÐ¾ Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ Ð·Ð°Ð´Ð°ÑÑ Ð¸Ð»Ð¸ Ð²Ð¾Ð¿ÑÐ¾Ñ â AI Ð¿Ð¾Ð¹Ð¼ÑÑ.\n\n"
            "/stats â ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ°\n"
            "/logout â Ð²ÑÐ¹ÑÐ¸\n"
            "/close\\_session â Ð·Ð°ÐºÑÑÑÑ ÑÐµÑÑÐ¸Ñ",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ð *Infinity Pay Support*\n\n"
            "Ð¯ Ð¼Ð¾Ð³Ñ Ð¿Ð¾Ð¼Ð¾ÑÑ Ñ:\n"
            "â¢ Clover POS\nâ¢ Ð¢ÑÐ°Ð½Ð·Ð°ÐºÑÐ¸Ð¸\nâ¢ Ð¢ÐµÑ. Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ñ\nâ¢ ÐÑÐ¿Ð¸ÑÐºÐ¸\n\n"
            "ð¬ ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ ÑÐµÐºÑÑ Ð¸Ð»Ð¸ ð Ð¾ÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð³Ð¾Ð»Ð¾ÑÐ¾Ð²Ð¾Ðµ!",
            parse_mode="Markdown"
        )


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# CLICKUP WEBHOOK â ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¿ÑÐ¸ ÑÐ¼ÐµÐ½Ðµ ÑÑÐ°ÑÑÑÐ°
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def check_ticket_updates(context: ContextTypes.DEFAULT_TYPE):
    """ÐÐµÑÐ¸Ð¾Ð´Ð¸ÑÐµÑÐºÐ°Ñ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ° Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ð¹ ÑÐ¸ÐºÐµÑÐ¾Ð² (ÐºÐ°Ð¶Ð´ÑÐµ 2 Ð¼Ð¸Ð½)."""
    try:
        # Ð§Ð¸ÑÑÐ¸Ð¼ ÑÑÐ°ÑÑÐµ Ð·Ð°Ð¿Ð¸ÑÐ¸ Ð¸Ð· ÐºÐµÑÐµÐ¹
        cleanup_notification_cache()
        cleanup_faq_cache()

        # Ð§Ð¸ÑÑÐ¸Ð¼ ÑÑÐ°ÑÑÐµ pending_agent_tasks (>30 Ð¼Ð¸Ð½)
        now = time.time()
        expired_pending = [k for k, v in pending_agent_tasks.items()
                          if now - v.get("created_at", 0) > 1800]
        for k in expired_pending:
            del pending_agent_tasks[k]

        # ÐÐ¾Ð»ÑÑÐ°ÐµÐ¼ Ð½ÐµÐ´Ð°Ð²Ð½Ð¾ Ð¾Ð±Ð½Ð¾Ð²Ð»ÑÐ½Ð½ÑÐµ ÑÐ¸ÐºÐµÑÑ
        r = requests.get(
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

            # ÐÑÐµÐ¼ Telegram ID Ð¼ÐµÑÑÐ°Ð½ÑÐ° Ð² Ð¾Ð¿Ð¸ÑÐ°Ð½Ð¸Ð¸
            desc  = task.get("description", "")
            tg_id = None
            if "Telegram ID:** " in desc:
                try:
                    tg_part = desc.split("Telegram ID:** ")[1].split("\n")[0].strip()
                    tg_id = int(tg_part) if tg_part.isdigit() else None
                except:
                    pass

            if not tg_id:
                continue

            # ÐÑÐ¾Ð²ÐµÑÑÐµÐ¼ â ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÑÐ»Ð¸ Ð»Ð¸ ÑÐ¶Ðµ (ÑÐµÑÐµÐ· Ð¾ÑÐ´ÐµÐ»ÑÐ½ÑÐ¹ ÐºÐµÑ)
            cache_key = f"notified_{task_id}_{status_name}"
            if cache_key in notification_cache:
                continue

            # ÐÑÐ¿ÑÐ°Ð²Ð»ÑÐµÐ¼ ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ðµ
            status_emoji = {
                "closed": "â", "complete": "â", "resolved": "â",
                "in progress": "ð", "review": "ð"
            }.get(status_name, "ð")

            if status_name in ("closed", "complete", "resolved", "in progress", "review"):
                is_closed = "close" in status_name or "complete" in status_name or "resolved" in status_name
                status_text = (
                    "ÐÐ°Ñ Ð²Ð¾Ð¿ÑÐ¾Ñ ÑÐµÑÑÐ½! ÐÑÐ»Ð¸ Ð½ÑÐ¶Ð½Ð¾ ÑÑÐ¾-ÑÐ¾ ÐµÑÑ â Ð½Ð°Ð¿Ð¸ÑÐ¸ÑÐµ."
                    if is_closed
                    else "ÐÐ°Ñ ÑÐ¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑ ÑÐ°Ð±Ð¾ÑÐ°ÐµÑ Ð½Ð°Ð´ Ð²Ð°ÑÐ¸Ð¼ Ð²Ð¾Ð¿ÑÐ¾ÑÐ¾Ð¼."
                )
                try:
                    await context.bot.send_message(
                        chat_id=tg_id,
                        text=f"{status_emoji} *ÐÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ Ð¿Ð¾ Ð²Ð°ÑÐµÐ¼Ñ Ð¾Ð±ÑÐ°ÑÐµÐ½Ð¸Ñ*\n\n"
                             f"Ð¡ÑÐ°ÑÑÑ: *{status_name.title()}*\n"
                             f"Ð¢Ð¸ÐºÐµÑ: `{task_id[:8]}`\n\n"
                             f"{status_text}",
                        parse_mode="Markdown"
                    )
                    notification_cache[cache_key] = time.time()

                    # Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÑÐµÐ¼ Ð² Ð³ÑÑÐ¿Ð¿Ñ
                    if SUPPORT_GROUP_CHAT_ID:
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id":    SUPPORT_GROUP_CHAT_ID,
                                "text":       f"{status_emoji} Ð¢Ð¸ÐºÐµÑ `{task_id[:8]}` â *{status_name.title()}*",
                                "parse_mode": "Markdown",
                            }
                        )

                    # ÐÑÐ»Ð¸ ÑÐ¸ÐºÐµÑ Ð·Ð°ÐºÑÑÑ â ÑÐ±ÑÐ°ÑÑÐ²Ð°ÐµÐ¼ ÑÐµÑÑÐ¸Ñ Ð¼ÐµÑÑÐ°Ð½ÑÐ°
                    if is_closed:
                        close_session(tg_id)

                except Exception as e:
                    logger.error(f"ÐÑÐ¸Ð±ÐºÐ° ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¼ÐµÑÑÐ°Ð½ÑÐ° {tg_id}: {e}")

            # ÐÑÐ¾Ð²ÐµÑÑÐµÐ¼ ÐºÐ¾Ð¼Ð¼ÐµÐ½ÑÐ°ÑÐ¸Ð¸ Ð¾Ñ ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ Ð´Ð»Ñ Ð¿ÐµÑÐµÑÑÐ»ÐºÐ¸ Ð¼ÐµÑÑÐ°Ð½ÑÑ
            try:
                cr = requests.get(
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
                        if comment_text and not comment_text.startswith("[ÐÐµÑÑÐ°Ð½Ñ]"):
                            try:
                                await context.bot.send_message(
                                    chat_id=tg_id,
                                    text=f"ð¬ *ÐÑÐ²ÐµÑ Ð¾Ñ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ¸:*\n\n{comment_text}",
                                    parse_mode="Markdown"
                                )
                                notification_cache[cache_key_c] = time.time()
                            except:
                                pass
            except:
                pass

    except Exception as e:
        logger.error(f"ÐÑÐ¸Ð±ÐºÐ° Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸ ÑÐ¸ÐºÐµÑÐ¾Ð²: {e}")


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# MAIN
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def main():
    print("\nâââââââââââââââââââââââââââââââââââââââââââ")
    print(" Infinity Pay Bot v2 â Starting...")
    print("âââââââââââââââââââââââââââââââââââââââââââ\n")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # ÐÐ¾Ð¼Ð°Ð½Ð´Ñ
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("close_session", close_session_command))

    # ÐÐ¾Ð»Ð¾ÑÐ¾Ð²ÑÐµ
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # Ð¢ÐµÐºÑÑÐ¾Ð²ÑÐµ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ÐÐµÑÐ¸Ð¾Ð´Ð¸ÑÐµÑÐºÐ°Ñ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ° ÑÐ¸ÐºÐµÑÐ¾Ð² (ÐºÐ°Ð¶Ð´ÑÐµ 2 Ð¼Ð¸Ð½)
    app.job_queue.run_repeating(check_ticket_updates, interval=120, first=30)

    print("â ÐÐ¾Ñ v2 Ð·Ð°Ð¿ÑÑÐµÐ½. Ctrl+C Ð´Ð»Ñ Ð¾ÑÑÐ°Ð½Ð¾Ð²ÐºÐ¸.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

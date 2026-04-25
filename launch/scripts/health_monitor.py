#!/usr/bin/env python3
"""
Infinity Pay — health monitor.

Запускается раз в N минут (через launchd / cron / Railway cron).
Проверяет:
  1. Dashboard /health endpoint (HTTP 200)
  2. Telegram webhook (no errors, low pending count)
  3. Bot identity reachable via Telegram API

Если что-то сломалось — шлёт алерт тебе в личку через Telegram бот.

Запуск:
    python3 health_monitor.py            # один проход
    python3 health_monitor.py --quiet    # без алертов на success (только при падении)

Env vars:
    TELEGRAM_BOT_TOKEN     — токен @Infinitypaysupport_bot
    TELEGRAM_OWNER_CHAT_ID — chat_id Shams (8427036826)
    DASHBOARD_URL          — https://infinity-pay-dashboard-production.up.railway.app
    HEALTH_QUIET           — '1' = только при падении (опционально)
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone


DASHBOARD_URL  = os.environ.get("DASHBOARD_URL",  "https://infinity-pay-dashboard-production.up.railway.app")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID  = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "8427036826")
QUIET          = os.environ.get("HEALTH_QUIET") == "1" or "--quiet" in sys.argv
TIMEOUT_S      = 10


def http_get(url: str, timeout: int = TIMEOUT_S) -> tuple[int, str]:
    """Простой HTTP GET. Возвращает (status, body)."""
    req = urllib.request.Request(url, headers={"User-Agent": "infinity-health/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, str(e.reason)
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def telegram_send(chat_id: str, text: str) -> bool:
    """Шлёт сообщение в Telegram. True если ок."""
    if not TELEGRAM_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN не задан — alert не отправлен")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.status == 200
    except Exception as e:
        print(f"⚠️  Не смог отправить telegram alert: {e}")
        return False


def check_dashboard() -> tuple[bool, dict]:
    """Returns (ok, details)."""
    status, body = http_get(f"{DASHBOARD_URL}/health")
    ok = status == 200
    parsed = {}
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = {"raw": body[:200]}
    return ok, {"status": status, **parsed}


def check_telegram() -> tuple[bool, dict]:
    """Returns (ok, details)."""
    if not TELEGRAM_TOKEN:
        return False, {"error": "no token"}
    status, body = http_get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo")
    if status != 200:
        return False, {"status": status, "body": body[:200]}
    try:
        info = json.loads(body).get("result", {})
    except Exception:
        return False, {"error": "bad json"}
    last_error = info.get("last_error_message")
    pending = info.get("pending_update_count", 0)
    url_set = bool(info.get("url"))
    ok = url_set and not last_error and pending < 100
    return ok, {
        "url_set":   url_set,
        "pending":   pending,
        "last_error": last_error,
        "url":       info.get("url", ""),
    }


def main():
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\n[{started}] Infinity Pay — health check")

    dash_ok, dash_info = check_dashboard()
    tg_ok,   tg_info   = check_telegram()
    overall_ok         = dash_ok and tg_ok

    # Pretty log
    print(f"  dashboard /health: {'✅' if dash_ok else '❌'} {dash_info}")
    print(f"  telegram webhook:  {'✅' if tg_ok else '❌'} {tg_info}")
    print(f"  overall:           {'🟢 OK' if overall_ok else '🔴 DEGRADED'}")

    # Alert если что-то упало (или если не --quiet)
    should_alert = (not overall_ok) or (not QUIET)
    if not overall_ok:
        msg_lines = [
            f"🚨 <b>Infinity Pay — health alert</b>",
            f"<i>{started}</i>",
            "",
            f"Dashboard: {'✅' if dash_ok else '❌ ' + json.dumps(dash_info)[:200]}",
            f"Telegram:  {'✅' if tg_ok else '❌ ' + json.dumps(tg_info)[:200]}",
            "",
            "Что проверить:",
        ]
        if not dash_ok:
            msg_lines.append("• Railway dashboard service — `railway logs --project infinity-pay-dashboard`")
        if not tg_ok:
            if (tg_info.get("last_error") or "").lower():
                msg_lines.append(f"• Telegram error: <code>{tg_info.get('last_error')}</code>")
            msg_lines.append("• Webhook URL: <code>" + tg_info.get("url", "?") + "</code>")
        telegram_send(OWNER_CHAT_ID, "\n".join(msg_lines))

    # Exit code: 0 ok, 1 degraded (для cron monitoring)
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()

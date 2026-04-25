#!/usr/bin/env python3
"""
Удаление тестовых данных с POS LA POLLERA.

ЗАПУСКАТЬ ТОЛЬКО когда Clover production verification пришла и
у LA POLLERA подключён реальный access_token.

Что удаляется:
  - Сотрудник:     ID 2DMEQP0771JG4 ("INFINITY PAY TEST", PIN 999001)
  - Меню-позиция:  ID 72TK8XC6DV22G ("INFINITY PAY SPECIAL 🔥")

Запуск:
    # Сначала dry-run (показать что бы удалилось)
    python3 cleanup_la_pollera_test.py --dry-run

    # Реальное удаление
    python3 cleanup_la_pollera_test.py

Env vars (из Railway):
    CLOVER_ACCESS_TOKEN — token конкретно от LA POLLERA (расшифровать из БД)
    CLOVER_MERCHANT_ID  — Clover MID для LA POLLERA
    CLOVER_ENV          — 'production' или 'sandbox'
"""
import os
import sys
import json
import urllib.request
import urllib.error


# ── IDs тестовых данных (зафиксированы в брейне) ─────────────────────────
TEST_EMPLOYEE_ID = "2DMEQP0771JG4"   # "INFINITY PAY TEST" PIN 999001
TEST_ITEM_ID     = "72TK8XC6DV22G"   # "INFINITY PAY SPECIAL 🔥"

DRY_RUN = "--dry-run" in sys.argv or "-n" in sys.argv


def clover_base() -> str:
    env = os.environ.get("CLOVER_ENV", "production")
    return "https://sandbox.dev.clover.com" if env == "sandbox" else "https://api.clover.com"


def clover_request(method: str, path: str, token: str) -> tuple[int, str]:
    """Делает запрос в Clover API. Возвращает (status, body)."""
    url = f"{clover_base()}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def confirm_target_exists(mid: str, token: str, target_type: str, target_id: str) -> dict:
    """Проверяет что объект существует. Возвращает данные или {}."""
    path = f"/v3/merchants/{mid}/{target_type}/{target_id}"
    status, body = clover_request("GET", path, token)
    if status == 200:
        try:
            return json.loads(body)
        except Exception:
            return {}
    if status == 404:
        return {}
    raise RuntimeError(f"Failed to fetch {target_type}/{target_id}: {status} {body[:200]}")


def delete_target(mid: str, token: str, target_type: str, target_id: str) -> bool:
    """Удаляет объект. True если успешно (или уже удалён)."""
    path = f"/v3/merchants/{mid}/{target_type}/{target_id}"
    status, body = clover_request("DELETE", path, token)
    if status in (200, 204):
        return True
    if status == 404:
        print(f"  ℹ️  {target_type}/{target_id} уже не существует")
        return True
    print(f"  ❌ DELETE {target_type}/{target_id} failed: {status} {body[:200]}")
    return False


def main():
    token = os.environ.get("CLOVER_ACCESS_TOKEN", "")
    mid   = os.environ.get("CLOVER_MERCHANT_ID", "")

    if not token or not mid:
        print("⚠️  CLOVER_ACCESS_TOKEN и CLOVER_MERCHANT_ID должны быть в env.")
        print("   Получи их так:")
        print("     1. railway link --project infinity-pay-dashboard")
        print("     2. railway run -- node -e \"const {query}=require('./src/db');")
        print("        const {decrypt}=require('./src/lib/crypto');")
        print("        query('SELECT clover_access_token, clover_merchant_id FROM merchants WHERE business_name ILIKE %s', ['%la pollera%'])")
        print("        .then(r => console.log({mid: r.rows[0].clover_merchant_id,")
        print("        token: decrypt(r.rows[0].clover_access_token)}))\"")
        sys.exit(2)

    env = os.environ.get("CLOVER_ENV", "production")
    print(f"🧹 Очистка тестовых данных LA POLLERA")
    print(f"   Clover env: {env}")
    print(f"   MID:        {mid}")
    print(f"   DRY-RUN:    {'YES (ничего не удаляется)' if DRY_RUN else 'NO (РЕАЛЬНОЕ УДАЛЕНИЕ)'}")
    print()

    targets = [
        ("employees", TEST_EMPLOYEE_ID, "сотрудник 'INFINITY PAY TEST'"),
        ("items",     TEST_ITEM_ID,     "блюдо 'INFINITY PAY SPECIAL 🔥'"),
    ]

    found_count = 0
    deleted_count = 0
    for target_type, target_id, label in targets:
        print(f"→ Проверяю {label} ({target_id})...")
        try:
            obj = confirm_target_exists(mid, token, target_type, target_id)
        except RuntimeError as e:
            print(f"  ❌ Ошибка проверки: {e}")
            continue

        if not obj:
            print(f"  ✅ Уже не существует")
            continue

        found_count += 1
        # Покажем детали для верификации
        name = obj.get("name", "?")
        print(f"  📋 Найдено: {name}")

        if DRY_RUN:
            print(f"  🔵 DRY-RUN: пропускаю удаление")
            continue

        if delete_target(mid, token, target_type, target_id):
            print(f"  ✅ Удалено")
            deleted_count += 1

    print()
    print(f"Итого: найдено {found_count}, удалено {deleted_count}")
    if DRY_RUN and found_count > 0:
        print("Для реального удаления запусти без --dry-run")


if __name__ == "__main__":
    main()

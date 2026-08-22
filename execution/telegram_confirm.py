"""
텔레그램으로 매매 시그널을 보내고 버튼 응답(승인/거부)을 폴링으로 대기하는 콜백.
GitHub Actions처럼 표준입력이 없는 환경에서 cli_confirm 대신 사용.

환경변수:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  TELEGRAM_CONFIRM_TIMEOUT_SEC (기본 300초, 타임아웃 시 자동 거부 = 안전 기본값)

사용법:
  from execution.telegram_confirm import telegram_confirm
  execute_intent(broker, intent, confirm_callback=telegram_confirm)
"""
import os
import time
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TIMEOUT_SEC = int(os.getenv("TELEGRAM_CONFIRM_TIMEOUT_SEC", "300"))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _send_confirm_message(intent) -> int:
    text = (
        f"🔔 매매 확인 요청\n"
        f"브로커: {intent.broker}\n"
        f"종목: {intent.symbol}\n"
        f"방향: {intent.side.value}\n"
        f"수량: {intent.qty}\n"
        f"스코어: {intent.score:.2f}\n"
        f"근거: {intent.reason}\n"
        f"손절가: {intent.stop_loss_price:.2f}\n\n"
        f"{TIMEOUT_SEC}초 내 응답 없으면 자동 거부됩니다."
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ 승인", "callback_data": "approve"},
            {"text": "❌ 거부", "callback_data": "reject"},
        ]]
    }
    r = requests.post(f"{API}/sendMessage", json={
        "chat_id": CHAT_ID, "text": text, "reply_markup": reply_markup,
    }, timeout=10)
    r.raise_for_status()
    return r.json()["result"]["message_id"]


def _poll_response(message_id: int, timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    last_update_id = None
    while time.time() < deadline:
        params = {"timeout": 10}
        if last_update_id is not None:
            params["offset"] = last_update_id + 1
        r = requests.get(f"{API}/getUpdates", params=params, timeout=15)
        r.raise_for_status()
        for update in r.json().get("result", []):
            last_update_id = update["update_id"]
            cb = update.get("callback_query")
            if cb and cb.get("message", {}).get("message_id") == message_id:
                requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=10)
                return cb["data"] == "approve"
        time.sleep(3)
    return False  # 타임아웃 -> 안전하게 거부


def telegram_confirm(intent) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("[telegram_confirm] TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 - 자동 거부")
        return False
    try:
        message_id = _send_confirm_message(intent)
        return _poll_response(message_id, TIMEOUT_SEC)
    except Exception as e:
        print(f"[telegram_confirm] 에러 - 안전하게 거부: {e}")
        return False

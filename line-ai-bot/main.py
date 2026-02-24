import os
import random
import logging
import google.generativeai as genai

from flask import request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import LineBotApiError, InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from pytz import timezone
from datetime import datetime
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

# --------------------
# logging 設定
# --------------------
logging.getLogger().setLevel(logging.INFO)

# --------------------
# 環境変数
# --------------------
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USER_ID = os.getenv("USER_ID")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN or not GEMINI_API_KEY:
    raise ValueError("環境変数が正しく設定されていません")

# --------------------
# Gemini
# --------------------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.5-flash")

# --------------------
# LINE
# --------------------
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 会話履歴（簡易）
session_data = {}

# ==================================================
# LINE Webhook
# ==================================================
def webhook(request):
    if request.method != "POST":
        return "Only POST requests are allowed", 405

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.warning("Invalid signature")
        return "Invalid signature", 400
    except LineBotApiError as e:
        logging.error(f"LINE API Error: {e}")
        return "LINE API error", 500

    return "OK", 200


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    logging.info(f"Received message from {user_id}: {user_message}")

    try:
        with open("prompt.txt", encoding="utf-8") as f:
            base_prompt = f.read()
    except Exception as e:
        logging.error(f"Prompt read failed: {e}")
        return

    if user_id not in session_data:
        session_data[user_id] = []

    if len(session_data[user_id]) >= 2:
        session_data[user_id].pop(0)

    session_data[user_id].append(f"ユーザー: {user_message}")
    conversation_history = "\n".join(session_data[user_id])

    try:
        response = model.generate_content(
            f"""{base_prompt}
                文章は90文字以内でお願いします。

                【会話履歴】
                {conversation_history}

                【新しいメッセージ】
                {user_message}
            """
        )
        ai_reply = response.text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        ai_reply = "ちょっと今忙しいからあとでねー"

    session_data[user_id].append(f"さくら: {ai_reply}")

    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_reply)
        )
    except LineBotApiError as e:
        logging.error(f"Reply failed: {e}")

# ==================================================
# Cloud Scheduler 用（抽選だけ）
# ==================================================
def send_random_message(request):
    now = datetime.now(timezone("Asia/Tokyo"))
    hour = now.hour
    chance = random.randint(1, 100)

    logging.info(f"[Scheduler] time={now}, chance={chance}")

    # ---- 抽選ルール ----
    if hour in [9, 12, 15, 19, 20]:
        if chance > 80:
            logging.info("Skip: daytime rule")
            return "skip", 200
    elif hour in range(0, 8):
        logging.info("Skip: midnight rule")
        return "skip", 200
    else:
        if chance > 10:
            logging.info("Skip: normal rule")
            return "skip", 200

    delay_minutes = random.randint(0, 59)
    delay_seconds = delay_minutes * 60

    logging.info(f"Passed lottery → enqueue task (delay {delay_minutes} min)")
    enqueue_send_message(delay_seconds)
    return "enqueued", 200

# ==================================================
# Cloud Tasks Queueへの追加
# ==================================================
def enqueue_send_message(delay_seconds: int):
    client = tasks_v2.CloudTasksClient()

    project = os.environ["GCP_PROJECT"]
    location = "asia-northeast1"
    queue = "line-message-queue"

    parent = client.queue_path(project, location, queue)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": os.environ["TASK_TARGET_URL"],
            "headers": {
                "Content-Type": "application/json"
            },
        }
    }

    if delay_seconds > 0:
        schedule_time = timestamp_pb2.Timestamp()
        schedule_time.FromSeconds(int(datetime.utcnow().timestamp()) + delay_seconds)
        task["schedule_time"] = schedule_time

    response = client.create_task(parent=parent, task=task)
    logging.info(f"Task created: {response.name}, delay={delay_seconds}s")

# ==================================================
# 実送信
# ==================================================
def send_message_task(request):
    try:
        with open("prompt.txt", encoding="utf-8") as f:
            base_prompt = f.read()
    except Exception as e:
        logging.error(f"Prompt read failed: {e}")
        return "prompt error", 200

    try:
        response = model.generate_content(
            f"""{base_prompt}
                今の気分で一言送ってください。
                40文字以内。
            """
        )
        message = response.text
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        message = "ちょっと今忙しいからあとでねー"

    try:
        line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
        logging.info("LINE push message sent")
    except Exception as e:
        logging.error(f"LINE push failed: {e}")

    return "ok", 200

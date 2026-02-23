import os
import random
import time
import logging
from datetime import datetime
from pytz import timezone
from flask import request

logging.basicConfig(level=logging.INFO)

# ----------------------------
# 共通ユーティリティ
# ----------------------------
def get_env(name):
    value = os.getenv(name)
    if not value:
        logging.error(f"Missing env var: {name}")
    return value


# =====================================================
# LINE Webhook
# =====================================================
def webhook(request):
    logging.info("=== webhook called ===")

    if request.method != "POST":
        return "Only POST requests are allowed", 405

    try:
        from linebot import WebhookHandler
        from linebot.exceptions import InvalidSignatureError
        from linebot import LineBotApi

        handler = WebhookHandler(get_env("LINE_CHANNEL_SECRET"))

        signature = request.headers.get("X-Line-Signature", "")
        body = request.get_data(as_text=True)

        handler.handle(body, signature)

        return "OK", 200

    except InvalidSignatureError:
        return "Invalid signature", 400
    except Exception:
        logging.exception("webhook failed")
        return "ERROR", 500


# =====================================================
# LINE メッセージ処理
# =====================================================
def handle_message(event):
    logging.info("=== handle_message ===")

    try:
        from linebot import LineBotApi
        from linebot.models import TextSendMessage
        import google.generativeai as genai

        LINE_CHANNEL_ACCESS_TOKEN = get_env("LINE_CHANNEL_ACCESS_TOKEN")
        GEMINI_API_KEY = get_env("GEMINI_API_KEY")

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        user_message = event.message.text

        with open("prompt.txt", encoding="utf-8") as f:
            base_prompt = f.read()

        response = model.generate_content(
            f"""
            {base_prompt}
            文章は90文字以内でお願いします。
            ユーザー: {user_message}
            """
        )

        reply = response.text if hasattr(response, "text") else "……ちょっと調子悪いかも"

        line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )

    except Exception:
        logging.exception("handle_message failed")


# =====================================================
# Cloud Tasks / Scheduler 用
# =====================================================
def send_message_task(request):
    logging.info("=== send_message_task START ===")

    try:
        from linebot import LineBotApi
        from linebot.models import TextSendMessage
        import google.generativeai as genai

        LINE_CHANNEL_ACCESS_TOKEN = get_env("LINE_CHANNEL_ACCESS_TOKEN")
        GEMINI_API_KEY = get_env("GEMINI_API_KEY")
        USER_ID = get_env("USER_ID")

        # ランダム遅延（Cloud Tasks 前提）
        delay = random.randint(30, 300)
        logging.info(f"sleep {delay}s")
        time.sleep(delay)

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        now = datetime.now(timezone("Asia/Tokyo"))
        prompt = f"""
        {now.strftime('%Y年%m月%d日 %H時%M分')}ごろの会話をイメージして
        40文字以内で返事してください。
        """

        response = model.generate_content(prompt)
        message = response.text if hasattr(response, "text") else "……なに？"

        line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        line_bot_api.push_message(
            USER_ID,
            TextSendMessage(text=message)
        )

        logging.info("send_message_task OK")
        return "OK", 200

    except Exception:
        logging.exception("send_message_task failed")
        return "ERROR", 500

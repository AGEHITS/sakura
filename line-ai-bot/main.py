import os
import random
import time
import logging
from datetime import datetime
from pytz import timezone

logging.basicConfig(level=logging.INFO)

# =========
# HTTP ENTRY POINT（最重要）
# =========
def send_message_task(request):
    """
    Gen2 Cloud Functions / Cloud Run 用 HTTP ハンドラ
    """
    logging.info("=== send_message_task START ===")

    try:
        # ===== 環境変数 =====
        LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        USER_ID = os.getenv("USER_ID")

        if not LINE_CHANNEL_ACCESS_TOKEN or not GEMINI_API_KEY or not USER_ID:
            logging.error("環境変数が不足しています")
            return "Missing env vars", 500

        # ===== 遅延（Cloud Tasks 前提なので今は短く）=====
        delay = random.randint(1, 5)
        logging.info(f"sleep {delay}s")
        time.sleep(delay)

        # ===== Gemini =====
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        now = datetime.now(timezone("Asia/Tokyo"))
        prompt = f"""
        {now.strftime('%Y年%m月%d日 %H時%M分')}ごろの会話をイメージして返事してください。
        文章は40文字以内でお願いします。
        """

        response = model.generate_content(prompt)
        message = response.text if hasattr(response, "text") else "……なに？"

        # ===== LINE Push =====
        from linebot import LineBotApi
        from linebot.models import TextSendMessage

        line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        line_bot_api.push_message(
            USER_ID,
            TextSendMessage(text=message)
        )

        logging.info("Message sent successfully")
        return "OK", 200

    except Exception as e:
        logging.exception("send_message_task failed")
        return "ERROR", 500

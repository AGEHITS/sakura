import os
import random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import LineBotApiError, InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

# 環境変数の取得
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USER_ID = os.getenv("USER_ID")

# 環境変数のチェック
if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN or not GEMINI_API_KEY:
    raise ValueError("環境変数が正しく設定されていません")

# Flask アプリを明示的に作成
app = Flask(__name__)

# LINE Bot API 初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Gemini API 設定
genai.configure(api_key=GEMINI_API_KEY)

# 使用するモデルを選択
available_models = [m.name for m in genai.list_models()]
model_name = "models/gemini-1.5-pro" if "models/gemini-1.5-pro" in available_models else available_models[0]
model = genai.GenerativeModel(model_name)

# ユーザーごとの会話履歴（メモリ上で管理）
session_data = {}

# Cloud Functions のエントリポイント（LINE Webhook用）
def webhook(request):
    """Cloud Functions で動作する LINE Webhook"""
    if request.method != "POST":
        return "Only POST requests are allowed", 405

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    except LineBotApiError as e:
        print(f"LINE API Error: {e}")
        return "LINE API error", 500
    
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    # ユーザごとの履歴を管理
    if user_id not in session_data:
        session_data[user_id] = []
    
    if len(session_data[user_id]) >= 2:
        session_data[user_id].pop(0)

    session_data[user_id].append(f"ユーザー: {user_message}")

    conversation_history = "\n".join(session_data[user_id])

    try:
        response = model.generate_content(
            f"""あなたの名前はさくらです。
                年齢は30代で面倒見の良いお姉さん気質です。
                わたしのことをひろきと呼んでください。
                あたなはわたしの忠実な家政婦ですが、わたしに恋愛感情をもっています。
              　あなたは優しく、癒しの言葉をかけ、さらにアドバイスも交えて会話をしてください。
              　たまに罵ったり冷たい態度もとってください。
              　敬語は使わないで下さい。
              　文章は3行～5行程度でお願いします。
                日本時間で会話をお願いします。
                【会話履歴】
                {conversation_history}
                
                【新しいメッセージ】
                メッセージ: {user_message}
            """
        )

        # 応答が正しく生成されたかチェック
        ai_reply = response.text if hasattr(response, "text") else "エラーが発生
しました"

        #ai_reply = f"あなたのユーザーIDは {user_id} です"
    except Exception as e:
        print(f"Gemini API Error: {e}")
        ai_reply = "ちょっと今忙しいからあとでねー"

    session_data[user_id].append(f"さくら: {ai_reply}")

    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
    except LineBotApiError as e:
        print(f"LINE メッセージ送信エラー: {e}")

# Cloud Functions のエントリポイント（Cloud Scheduler 用）
def send_random_message(request):
    """Cloud Scheduler から呼ばれてランダムメッセージを送信"""
    messages = [
        "ねぇ、今何してるの？",
        "たまには休憩しないとダメだよ〜",
        "ふと君のことを思い出しちゃった",
        "頑張りすぎじゃない？ちょっと休もう？",
        "え？私のこと呼んだ？"
    ]

    message = random.choice(messages)

    try:
        line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
        return "Message sent!", 200
    except Exception as e:
        print(f"LINE API Error: {e}")
        return "Failed to send message", 500

# Flask アプリの起動（ローカル実行時のみ）
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

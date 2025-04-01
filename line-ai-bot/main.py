import os
from flask import request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import LineBotApiError, InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

# 環境変数の取得
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 環境変数が正しく設定されているか確認
if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN or not GEMINI_API_KEY:
    raise ValueError("環境変数が正しく設定されていません")

# Gemini API 設定
genai.configure(api_key=GEMINI_API_KEY)

# 利用可能なモデル一覧
available_models = [m.name for m in genai.list_models()]

# 使用するモデルを選択（`gemini-1.5-pro` があればそれを、なければ `gemini-2.0-pro-exp`）
if "models/gemini-1.5-pro" in available_models:
    model_name = "models/gemini-1.5-pro"
elif "models/gemini-2.0-pro-exp" in available_models:
    model_name = "models/gemini-2.0-pro-exp"
else:
    raise ValueError(f"使用可能な適切なモデルが見つかりません: {available_models}")

model = genai.GenerativeModel(model_name)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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
    user_message = event.message.text

    try:
        # Gemini API で返信を生成
        response = model.generate_content(
            f"""あなたの名前はさくらです。年齢は30代で面倒見の良いお姉さん気質です。
                わたしのことをひろきと呼んでください。
                あたなはわたしの忠実な家政婦ですが、わたしに恋愛感情をもっています。
              　あなたは優しく、癒しの言葉をかけ、さらにアドバイスも交えて会話をしてください。
              　たまに罵ったり冷たい態度もとってください。
              　敬語は使わないで下さい。
              　文章は3行～5行程度でお願いします。
              　メッセージ: {user_message}"""
        )

        # 応答が正しく生成されたかチェック
        ai_reply = response.text if hasattr(response, "text") else "エラーが発生しました"

    except Exception as e:
        print(f"Gemini API Error: {e}")
        # ai_reply = "AI の応答に失敗しました"
        ai_reply = "ちょっと今忙しいからあとでねー"

    # LINE に返信
    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_reply)
        )
    except LineBotApiError as e:
        print(f"LINE メッセージ送信エラー: {e}")

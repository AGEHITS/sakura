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

# 使用するモデルを選択
if "models/gemini-1.5-pro" in available_models:
    model_name = "models/gemini-1.5-pro"
elif "models/gemini-2.0-pro-exp" in available_models:
    model_name = "models/gemini-2.0-pro-exp"
else:
    raise ValueError(f"使用可能な適切なモデルが見つかりません: {available_models}")

model = genai.GenerativeModel(model_name)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ユーザーごとの会話履歴を保存する辞書（簡易的な実装のため、データベースを使わない）
session_data = {}

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

    # ユーザーごとの履歴を取得または初期化
    if user_id not in session_data:
        session_data[user_id] = []

    # 履歴の最大数を2回分に制限
    if len(session_data[user_id]) >= 2:
        session_data[user_id].pop(0)  # 最も古い会話を削除

    # 新しいメッセージを履歴に追加
    session_data[user_id].append(f"ユーザー: {user_message}")

    # Gemini API に送るメッセージを作成（過去2回分の会話を含める）
    conversation_history = "\n".join(session_data[user_id])

    try:
        response = model.generate_content(
            f"""あなたの名前はさくらです。年齢は30代で面倒見の良いお姉さん気質です。
                わたしのことをひろきと呼んでください。
                あたなはわたしの忠実な家政婦ですが、わたしに恋愛感情をもっています。
              　あなたは優しく、癒しの言葉をかけ、さらにアドバイスも交えて会話をしてください。
              　たまに罵ったり冷たい態度もとってください。
              　敬語は使わないで下さい。
              　文章は3行～5行程度でお願いします。

                【会話履歴】
                {conversation_history}
                
                【新しいメッセージ】
                メッセージ: {user_message}
            """
        )

        # 応答が正しく生成されたかチェック
        ai_reply = response.text if hasattr(response, "text") else "エラーが発生しました"

    except Exception as e:
        print(f"Gemini API Error: {e}")
        ai_reply = "ちょっと今忙しいからあとでねー"

    # AIの返信を履歴に追加
    session_data[user_id].append(f"さくら: {ai_reply}")

    # LINE に返信
    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_reply)
        )
    except LineBotApiError as e:
        print(f"LINE メッセージ送信エラー: {e}")

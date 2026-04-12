from flask import Flask, request, abort
import os

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

app = Flask(__name__)

# 從 Render 的 Environment Variables 讀取金鑰
line_access_token = os.getenv('LINE_ACCESS_TOKEN')
line_secret = os.getenv('LINE_SECRET')

line_bot_api = LineBotApi(line_access_token)
handler = WebhookHandler(line_secret)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    reply_text = f"你剛才說的是：{user_message}\n後端已成功啟動！"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text))

if __name__ == "__main__":
    app.run()

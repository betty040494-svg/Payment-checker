from flask import Flask, request, abort
import os
import random

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)

# --- 1. 設定區 ---
LINE_ACCESS_TOKEN = os.getenv('LINE_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_SECRET')

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- 2. 模擬資料庫 ---
USER_BANKS = {}  # 收款帳號
DEBTS = {}       # 債務紀錄：{ '債權人ID': {'欠款人名': 金額} }
DEFAULT_BANK = "⚠️ 尚未設定帳號 (點選下方按鈕設定)"

# --- 3. 快速選單工具 ---
def get_main_menu():
    """產生下方的快速按鈕選單"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="誰沒給錢？", text="誰沒給錢")),
        QuickReplyButton(action=MessageAction(label="確認我的帳號", text="確認帳號")),
        QuickReplyButton(action=MessageAction(label="隨機抽人請客", text="抽請客")),
        QuickReplyButton(action=MessageAction(label="幫助說明", text="幫助")),
    ])

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    menu = get_main_menu()

    # --- 功能 1：查債務 (點按鈕即可) ---
    if user_text == "誰沒給錢":
        my_debts = DEBTS.get(user_id, {})
        if not my_debts:
            reply = "✅ 目前大家都還清囉，沒有待收帳款。"
        else:
            res = "📋 待收清單：\n"
            total = 0
            for name, amt in my_debts.items():
                res += f"▫️ {name}：{amt} 元\n"
                total += amt
            res += f"--------------------\n💰 總計：{total} 元"
            reply = res
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 2：銷帳 (收到了/名字) ---
    if user_text.startswith("收到了/"):
        name = user_text.split("/")[-1]
        if user_id in DEBTS and name in DEBTS[user_id]:
            del DEBTS[user_id][name]
            reply = f"👌 OK！已將 {name} 從欠款名單移除。"
        else:
            reply = f"❓ 找不到 {name} 的欠款紀錄。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 3：進階分帳處理 (分帳/項目/人1,人2/總金額) ---
    if user_text.startswith("分帳/"):
        try:
            p = user_text.split("/")
            item, names, total = p[1], p[2].split(","), float(p[3])
            avg = round(total / (len(names) + 1), 1)
            
            # 存入紀錄
            if user_id not in DEBTS: DEBTS[user_id] = {}
            for n in names:
                DEBTS[user_id][n] = DEBTS[user_id].get(n, 0) + avg
            
            bank = USER_BANKS.get(user_id, DEFAULT_BANK)
            reply = (f"📝 {item} 分帳完成！\n每人應付：{avg} 元\n"
                     f"--------------------\n"
                     f"🏦 收款資訊：\n{bank}\n\n"
                     f"👉 點擊下方「誰沒給錢」可隨時追蹤。")
        except:
            reply = "⚠️ 格式錯誤！範例：分帳/晚餐/小明,小華/900"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 4：設定帳號 ---
    if user_text.startswith("設定帳號/"):
        p = user_text.split("/")
        if len(p) >= 3:
            USER_BANKS[user_id] = f"🏦 {p[1]} ({p[2]})"
            reply = "✅ 帳號儲存成功！下次分帳會自動帶入。"
        else:
            reply = "⚠️ 範例：設定帳號/中信/12345"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 5：確認帳號 & 抽請客 & 幫助 ---
    if user_text == "確認帳號":
        bank = USER_BANKS.get(user_id, DEFAULT_BANK)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"您的目前帳號：\n{bank}", quick_reply=menu))
        return

    if user_text == "抽請客":
        reply = "🎲 想玩抽籤請輸入：誰請客/A/B/C"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    if user_text.startswith("誰請客/"):
        names = user_text.split("/")[1:]
        reply = f"🎲 抽獎結果：【{random.choice(names)}】 請客！🏆"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 預設：歡迎訊息與按鈕 ---
    welcome = (f"👋 您好 Liao！我是您的分帳小管家。\n\n"
               f"💡 快速上手：\n"
               f"直接打「分帳/晚餐/小明,小華/900」\n\n"
               f"或是點選下方選單：")
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome, quick_reply=menu))

if __name__ == "__main__":
    app.run()
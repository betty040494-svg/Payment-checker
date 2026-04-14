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
    QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)

# --- 1. 設定區 ---
LINE_ACCESS_TOKEN = os.getenv('LINE_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_SECRET')
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- 2. 模擬校園資料庫 ---
USER_DATA = {
    'bank': {},      
    'expenses': {},  
    'debts': {},     
}

# --- 3. 快速選單 ---
def get_main_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="📋 查看欠款明細", text="查看明細")),
        QuickReplyButton(action=MessageAction(label="💰 本月總支出", text="查詢支出")),
        QuickReplyButton(action=MessageAction(label="🏦 我的收款帳號", text="確認帳號")),
        QuickReplyButton(action=MessageAction(label="❔ 幫助說明", text="幫助")),
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

    # ✨ 新增：獲取使用者的 LINE 個人檔案 (包含名字)
    try:
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
    except:
        user_name = "使用者" # 萬一 API 抓不到時的備案

    # --- 功能 A：單獨記錄墊付 (墊付/名字/品項/金額) ---
    if user_text.startswith("墊付/"):
        try:
            p = user_text.split("/")
            name, item, amount = p[1], p[2], float(p[3])
            if user_id not in USER_DATA['debts']: USER_DATA['debts'][user_id] = {}
            if name not in USER_DATA['debts'][user_id]: USER_DATA['debts'][user_id][name] = []
            USER_DATA['debts'][user_id][name].append({'item': item, 'price': amount})
            reply = f"✅ 已紀錄明細：\n👤 對象：{name}\n📦 項目：{item}\n💰 金額：{amount} 元"
        except:
            reply = "⚠️ 範例：墊付/小明/飲料/50"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 B：團體分帳 ---
    if user_text.startswith("分帳/"):
        try:
            p = user_text.split("/")
            item, names, total = p[1], p[2].split(","), float(p[3])
            fee = float(p[4]) if len(p) > 4 else 0
            avg = round((total * (1 + fee/100)) / (len(names) + 1), 1)
            if user_id not in USER_DATA['debts']: USER_DATA['debts'][user_id] = {}
            for n in names:
                if n not in USER_DATA['debts'][user_id]: USER_DATA['debts'][user_id][n] = []
                USER_DATA['debts'][user_id][n].append({'item': f"分帳-{item}", 'price': avg})
            bank = USER_DATA['bank'].get(user_id, "⚠️ 尚未設定帳號")
            reply = f"📝 {item} 分帳完成！每人 {avg} 元。\n🏦 收款帳號：\n{bank}"
        except:
            reply = "範例：分帳/晚餐/小明,小華/1200/10"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 C：查看明細 ---
    if user_text == "查看明細":
        my_debts = USER_DATA['debts'].get(user_id, {})
        if not my_debts:
            reply = f"✅ {user_name}，目前沒有任何人欠你錢喔！"
        else:
            res = f"📋 【{user_name} 的待收清單】\n"
            grand_total = 0
            for name, items in my_debts.items():
                person_total = sum(d['price'] for d in items)
                res += f"\n👤 {name} (欠 {person_total} 元)：\n"
                for i in items:
                    res += f"  ▫️ {i['item']}：{i['price']} 元\n"
                grand_total += person_total
            res += f"\n--------------------\n💰 總計待收：{round(grand_total, 1)} 元"
            reply = res
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 D：結清 (已收/名字) ---
    if user_text.startswith("已收/"):
        name = user_text.split("/")[-1]
        if user_id in USER_DATA['debts'] and name in USER_DATA['debts'][user_id]:
            del USER_DATA['debts'][user_id][name]
            reply = f"👌 OK！已結清 {name} 的所有紀錄。"
        else:
            reply = f"❓ 找不到 {name} 的紀錄。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 E：個人支出 ---
    if user_text.startswith("支出/"):
        try:
            p = user_text.split("/")
            if user_id not in USER_DATA['expenses']: USER_DATA['expenses'][user_id] = []
            USER_DATA['expenses'][user_id].append(float(p[2]))
            reply = f"💰 {user_name}，已記錄支出：{p[1]} {p[2]} 元。"
        except: reply = "範例：支出/午餐/100"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 帳號與幫助 ---
    if user_text == "查詢支出":
        exps = USER_DATA['expenses'].get(user_id, [])
        reply = f"📊 {user_name} 本月支出：{sum(exps)} 元" if exps else "📭 無支出紀錄。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    if user_text.startswith("設定帳號/"):
        p = user_text.split("/")
        USER_DATA['bank'][user_id] = f"🏦 {p[1]} ({p[2]})"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 帳號儲存成功！", quick_reply=menu))
        return

    if user_text == "幫助":
        h = ("✨ 指令教學 ✨\n\n"
             "1️⃣ 【單筆墊付】(幫朋友順手買)\n墊付/名字/品項/金額\n\n"
             "2️⃣ 【團體分帳】(聚餐)\n分帳/項目/人1,2/金額/%\n\n"
             "3️⃣ 【銷帳】\n已收/名字\n\n"
             "💡 點選按鈕「查看明細」看誰欠什麼！")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=h, quick_reply=menu))

    # 🌟 預設歡迎訊息：現在會說「哈囉 [名字]！」
    welcome_text = f"👋 哈囉 {user_name}！我是您的明細管家。\n\n點選下方按鈕，或輸入「幫助」來查看指令教學吧！"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_text, quick_reply=menu))

if __name__ == "__main__":
    app.run()

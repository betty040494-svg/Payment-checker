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
    'bank': {},      # 收款帳號 (銀行/帳號)
    'expenses': {},  # 個人支出紀錄 [100, 200...]
    'debts': {},     # 分帳待收紀錄 {債權人ID: {欠款人名: 金額}}
}

# --- 3. 快速選單工具 (專注分帳與記帳) ---
def get_main_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="👥 誰還沒給錢？", text="查看待收")),
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

    # --- 功能 A：聚餐分帳 (格式：分帳/項目/人1,人2/總金額/服務費%) ---
    if user_text.startswith("分帳/"):
        try:
            p = user_text.split("/")
            item = p[1]
            names = p[2].split(",")
            total_amount = float(p[3])
            # 若沒填服務費，預設為 0
            fee_percent = float(p[4]) if len(p) > 4 else 0
            
            # 計算含服務費後的總額與平均金額 (含發起人自己)
            real_total = total_amount * (1 + fee_percent / 100)
            avg = round(real_total / (len(names) + 1), 1)
            
            # 記錄債務
            if user_id not in USER_DATA['debts']: USER_DATA['debts'][user_id] = {}
            for n in names:
                USER_DATA['debts'][user_id][n] = USER_DATA['debts'][user_id].get(n, 0) + avg
            
            bank = USER_DATA['bank'].get(user_id, "⚠️ 尚未設定收款帳號")
            reply = (f"📝 【{item}】分帳計算表\n"
                     f"💰 原始金額：{total_amount} 元\n"
                     f"➕ 服務費：{fee_percent}%\n"
                     f"💵 應付總額：{round(real_total, 1)} 元\n"
                     f"--------------------\n"
                     f"👥 每人平分：{avg} 元\n\n"
                     f"🏦 收款資訊：\n{bank}\n\n"
                     f"👉 同學給錢後，請對我說「已收/名字」")
        except:
            reply = "⚠️ 格式錯誤！範例：分帳/聚餐/小明,小華/1200/10"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 B：查看待收帳款報表 ---
    if user_text == "查看待收":
        my_debts = USER_DATA['debts'].get(user_id, {})
        if not my_debts:
            reply = "✅ 目前大家都還清囉！沒有待收帳款。"
        else:
            res = "📋 【待收帳款清單】\n"
            for name, amt in my_debts.items():
                res += f"▫️ {name}：{amt} 元\n"
            res += f"--------------------\n💰 待收總計：{round(sum(my_debts.values()), 1)} 元"
            reply = res
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 C：銷帳 (已收/名字) ---
    if user_text.startswith("已收/"):
        name = user_text.split("/")[-1]
        if user_id in USER_DATA['debts'] and name in USER_DATA['debts'][user_id]:
            del USER_DATA['debts'][user_id][name]
            reply = f"👌 OK！已結清 {name} 的欠款。"
        else:
            reply = f"❓ 找不到 {name} 的欠款紀錄。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 D：個人記帳 (支出/項目/金額) ---
    if user_text.startswith("支出/"):
        try:
            p = user_text.split("/")
            item, amount = p[1], float(p[2])
            if user_id not in USER_DATA['expenses']: USER_DATA['expenses'][user_id] = []
            USER_DATA['expenses'][user_id].append(amount)
            reply = f"💰 記帳成功：{item} 花了 {amount} 元。"
        except:
            reply = "範例：支出/午餐/100"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 E：查詢總支出 ---
    if user_text == "查詢支出":
        exps = USER_DATA['expenses'].get(user_id, [])
        if not exps:
            reply = "📭 目前還沒有支出紀錄。"
        else:
            reply = f"📊 本月個人支出統計：\n累積金額：{sum(exps)} 元\n總筆數：{len(exps)} 筆"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=menu))
        return

    # --- 功能 F：收款帳號設定與幫助 ---
    if user_text.startswith("設定帳號/"):
        p = user_text.split("/")
        USER_DATA['bank'][user_id] = f"🏦 {p[1]} ({p[2]})"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 收款帳號設定成功！", quick_reply=menu))
        return

    if user_text == "確認帳號":
        bank = USER_DATA['bank'].get(user_id, "⚠️ 尚未設定帳號")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"您的收款帳號：\n{bank}", quick_reply=menu))
        return

    if user_text == "幫助":
        help_msg = (
            "✨ 使用指令說明 ✨\n\n"
            "1️⃣ 【分帳】(含服務費%)\n分帳/項目/人1,2/金額/%\n(範例：分帳/晚餐/小明,小華/900/10)\n\n"
            "2️⃣ 【記帳】(個人支出)\n支出/品項/金額\n(範例：支出/雞排/85)\n\n"
            "3️⃣ 【收款設定】\n設定帳號/銀行/帳號\n\n"
            "4️⃣ 【銷帳】\n已收/名字"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg, quick_reply=menu))
        return

     # 🌟 預設歡迎訊息：現在會說「哈囉 [名字]！」
    welcome_text = f"👋 哈囉 {user_name}！我是您的明細管家。\n\n點選下方按鈕，或輸入「幫助」來查看指令教學吧！"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_text, quick_reply=menu))

if __name__ == "__main__":
    app.run()

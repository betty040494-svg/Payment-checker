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

# --- 3. 多層級選單定義 ---

def get_main_menu():
    """第一層：主選單"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="👥 債務管理", text="選單/債務")),
        QuickReplyButton(action=MessageAction(label="💰 個人支出", text="選單/支出")),
        QuickReplyButton(action=MessageAction(label="🏦 帳號/幫助", text="選單/設定")),
    ])

def get_debt_menu():
    """第二層：債務管理子選單"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="✍️ 登記墊付", text="墊付/名字/品項/金額")),
        QuickReplyButton(action=MessageAction(label="🍱 聚餐分帳", text="分帳/項目/人1,人2/金額/10")),
        QuickReplyButton(action=MessageAction(label="📋 查看明細", text="查看明細")),
        QuickReplyButton(action=MessageAction(label="✅ 已收銷帳", text="已收/名字")),
        QuickReplyButton(action=MessageAction(label="⬅️ 回主選單", text="回主選單")),
    ])

def get_expense_menu():
    """第二層：個人支出子選單"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="💸 紀錄支出", text="支出/項目/金額")),
        QuickReplyButton(action=MessageAction(label="📊 查詢總額", text="查詢支出")),
        QuickReplyButton(action=MessageAction(label="⬅️ 回主選單", text="回主選單")),
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
    
    # 取得 LINE 名字
    try:
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
    except:
        user_name = "使用者"

    # ==========================
    #   第一部分：選單導覽邏輯
    # ==========================
    if user_text == "選單/債務":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="💡 【債務管理】\n您可以登記幫朋友墊付的東西，或進行多人平分帳單。", quick_reply=get_debt_menu()))
        return
    
    if user_text == "選單/支出":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="💡 【個人支出】\n記下今天的開銷，隨時統計本月花費。", quick_reply=get_expense_menu()))
        return
    
    if user_text == "選單/設定":
        setting_menu = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="🏦 確認帳號", text="確認帳號")),
            QuickReplyButton(action=MessageAction(label="⚙️ 設定帳號", text="設定帳號/銀行/帳號")),
            QuickReplyButton(action=MessageAction(label="❔ 幫助說明", text="幫助")),
            QuickReplyButton(action=MessageAction(label="⬅️ 回主選單", text="回主選單")),
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="💡 【系統設定】\n請設定您的收款資訊或查看指令說明。", quick_reply=setting_menu))
        return

    if user_text == "回主選單":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"👋 哈囉 {user_name}，已為您回到主選單：", quick_reply=get_main_menu()))
        return

    # ==========================
    #   第二部分：功能執行邏輯
    # ==========================

    # 1. 墊付
    if user_text.startswith("墊付/"):
        try:
            p = user_text.split("/")
            name, item, amount = p[1], p[2], float(p[3])
            if user_id not in USER_DATA['debts']: USER_DATA['debts'][user_id] = {}
            if name not in USER_DATA['debts'][user_id]: USER_DATA['debts'][user_id][name] = []
            USER_DATA['debts'][user_id][name].append({'item': item, 'price': amount})
            reply = f"✅ 已紀錄明細：\n👤 對象：{name}\n📦 項目：{item}\n💰 金額：{amount} 元"
        except: reply = "⚠️ 格式：墊付/名字/品項/金額"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=get_debt_menu()))
        return

    # 2. 分帳
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
            reply = f"📝 {item} 分帳成功！每人 {avg} 元。\n🏦 收款帳號：\n{bank}"
        except: reply = "範例：分帳/晚餐/小明,小華/1200/10"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=get_debt_menu()))
        return

    # 3. 查看明細
    if user_text == "查看明細":
        my_debts = USER_DATA['debts'].get(user_id, {})
        if not my_debts:
            reply = f"✅ {user_name}，目前沒有人欠你錢喔！"
        else:
            res = f"📋 【{user_name} 的待收清單】\n"
            grand_total = 0
            for name, items in my_debts.items():
                person_total = sum(d['price'] for d in items)
                res += f"\n👤 {name} (欠 {person_total} 元)：\n"
                for i in items: res += f"  ▫️ {i['item']}：{i['price']} 元\n"
                grand_total += person_total
            res += f"\n--------------------\n💰 總計待收：{round(grand_total, 1)} 元"
            reply = res
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=get_debt_menu()))
        return

    # 4. 支出
    if user_text.startswith("支出/"):
        try:
            p = user_text.split("/")
            if user_id not in USER_DATA['expenses']: USER_DATA['expenses'][user_id] = []
            USER_DATA['expenses'][user_id].append(float(p[2]))
            reply = f"💰 {user_name}，已記錄支出：{p[1]} {p[2]} 元。"
        except: reply = "範例：支出/午餐/100"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=get_expense_menu()))
        return

    # 5. 銷帳、查詢、設定與幫助
    if user_text.startswith("已收/"):
        name = user_text.split("/")[-1]
        if user_id in USER_DATA['debts'] and name in USER_DATA['debts'][user_id]:
            del USER_DATA['debts'][user_id][name]
            reply = f"👌 OK！已結清 {name} 的紀錄。"
        else: reply = f"❓ 找不到 {name} 的紀錄。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=get_debt_menu()))
        return

    if user_text == "查詢支出":
        exps = USER_DATA['expenses'].get(user_id, [])
        reply = f"📊 {user_name} 本月支出：{sum(exps)} 元" if exps else "📭 無支出紀錄。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=get_expense_menu()))
        return

    if user_text.startswith("設定帳號/"):
        p = user_text.split("/")
        USER_DATA['bank'][user_id] = f"🏦 {p[1]} ({p[2]})"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 帳號儲存成功！", quick_reply=get_main_menu()))
        return

    if user_text == "確認帳號":
        bank = USER_DATA['bank'].get(user_id, "⚠️ 尚未設定帳號")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"您的收款帳號：\n{bank}", quick_reply=get_main_menu()))
        return

    if user_text == "幫助":
        help_msg = (
            f"✨ 【{user_name} 的管家手冊】 ✨\n"
            "━━━━━━━━━━━━━━━\n\n"
            "🔹 1. 多人分帳\n「分帳/項目/人/金額/%」\n\n"
            "🔹 2. 單筆墊付\n「墊付/名字/品項/金額」\n\n"
            "🔹 3. 個人記帳\n「支出/項目/金額」\n\n"
            "🔹 4. 結清帳款\n「已收/名字」\n\n"
            "💡 提示：點擊下方按鈕即可快速操作！"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg, quick_reply=get_main_menu()))
        return

    # ==========================
    #   第三部分：預設歡迎訊息
    # ==========================
    welcome_text = f"👋 哈囉 {user_name}！我是您的財務管家。\n\n請點擊下方按鈕開始使用："
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_text, quick_reply=get_main_menu()))

if __name__ == "__main__":
    app.run()

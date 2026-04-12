from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

import os  # 如果最上面沒有這行，請記得加上

LINE_ACCESS_TOKEN = os.getenv('LINE_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_SECRET')

# 模擬資料庫：紀錄 VIP 狀態與每個人的銀行帳號
VIP_USERS = set() 
USER_BANKS = {} # 格式: { 'user_id': '銀行帳號資訊' }
DEFAULT_BANK = "⚠️ 尚未設定帳號 (輸入「設定帳號/...」)"
VIP_PRICE = "10"

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN.strip().replace('\n', '').replace(' ', ''))
handler = WebhookHandler(LINE_SECRET.strip())

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
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
    
    try:
        # 1. 設定銀行帳號 (新功能)
        # 格式: 設定帳號/銀行代碼/帳號
        if user_text.startswith('設定帳號/'):
            p = user_text.split('/')
            if len(p) >= 3:
                bank_info = f"🏦 銀行代碼：{p[1]}\n🔢 帳號：{p[2]}"
                USER_BANKS[user_id] = bank_info
                reply = f"✅ 帳號設定成功！\n今後您發起的分帳將自動顯示：\n{bank_info}"
            else:
                reply = "⚠️ 格式錯誤！範例：設定帳號/822/12345678"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 2. 訂閱解鎖
        if user_text == "我要訂閱":
            VIP_USERS.add(user_id)
            reply = f"🎉 感謝支持！已解鎖 VIP 權限。\n現在可使用：\n✅ 個人化點餐分攤\n✅ 匯率換算功能"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 取得該用戶的銀行資訊
        current_bank = USER_BANKS.get(user_id, DEFAULT_BANK)

        # 3. VIP 專屬：個人化分攤
        # 格式: 個人/服務費/金額1/金額2...
        if user_text.startswith('個人/'):
            if user_id not in VIP_USERS:
                reply = f"❌ 此為 VIP 專屬功能。\n請輸入「我要訂閱」支付 ${VIP_PRICE} 元解鎖。"
            else:
                p = user_text.split('/')
                if len(p) < 3:
                    reply = "⚠️ 格式錯誤！範例：個人/10/378/300/450"
                else:
                    tax_rate = float(p[1])
                    prices = [float(x) for x in p[2:]]
                    detail = ""
                    total_sum = 0
                    for i, price in enumerate(prices):
                        final_p = price * (1 + tax_rate/100)
                        total_sum += final_p
                        detail += f"👤 成員 {i+1}：${final_p:,.1f}\n"
                    
                    reply = (
                        f"🍽️ 【VIP 個人化分攤清單】\n"
                        f"────────────────\n"
                        f"⚡ 服務費率：{tax_rate}%\n"
                        f"{detail}"
                        f"────────────────\n"
                        f"💰 總計收款：${total_sum:,.0f}\n"
                        f"{current_bank}"
                    )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

        # 4. 基礎功能：詳細分帳
        # 格式: 金額/人數/服務費/分類/品項
        elif '/' in user_text:
            p = user_text.split('/')
            if len(p) >= 2:
                amount = float(p[0])
                num = int(p[1])
                service = float(p[2]) if len(p) >= 3 else 0
                category = p[3] if len(p) >= 4 else "一般"
                item_name = p[4] if len(p) >= 5 else "未命名品項"
                
                total = amount * (1 + service / 100)
                each = total / num
                
                icons = {"吃飯": "🍴", "購物": "🛍️", "旅遊": "✈️", "交通": "🚗", "娛樂": "🎮", "住宿": "🏨"}
                icon = icons.get(category, "📝")
                
                reply = (
                    f"{icon} 【{category}｜分帳明細】\n"
                    f"────────────────\n"
                    f"📦 品項：{item_name}\n"
                    f"📈 總計：${total:,.0f} (含{service}%服務費)\n"
                    f"👥 人數：{num} 人\n"
                    f"💳 每人應付：${each:,.2f}\n"
                    f"────────────────\n"
                    f"{current_bank}"
                )
                if user_id not in VIP_USERS:
                    reply += f"\n\n💡 提示：輸入「我要訂閱」只需 ${VIP_PRICE} 元解鎖 VIP 功能！"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            
        # 5. 指令教學
        else:
            help_msg = (
                "🤖 【專業分帳助手】\n\n"
                "📌 首先請設定您的帳號：\n"
                "👉 設定帳號/銀行代碼/帳號\n\n"
                "1️⃣ 詳細分帳 (基礎)：\n"
                "👉 金額/人數/服務費/分類/品項\n\n"
                "2️⃣ 個人化分攤 (VIP)：\n"
                "👉 個人/服務費/金額1/金額2...\n\n"
                f"💰 輸入「我要訂閱」只需 ${VIP_PRICE} 元"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg))

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    app.run(port=5001)

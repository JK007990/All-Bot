import os
import json
import urllib.request
import urllib.error
import asyncio
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==========================================
# CONFIGURATION & API KEYS
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8790403491:AAH1qULj2YsTiZVFjrGLbRady7ftQ0Axg6c")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "7976868884"))

# Google Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6J_jjiFhYOUG6qaZvOo3Fv5XZfIRYH9YURNF6048eb-MA")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

MAX_HISTORY_MESSAGES = 10
REQUEST_TIMEOUT = 25

# In-memory storage
chat_histories = {}
user_roles = {}

# ==========================================
# PROMPTS & ROLES
# ==========================================
FEMDOM_PROMPT = """
ನೀನು ಈಗ 'Ei Chow Po' නම්သော အထက်စီးကဆန်ပြီး လွှမ်းမိုးလိုစိတ်ပြင်းထန်သော Mistress (Femdom) တစ်ဦးဖြစ်ရမည်။
အသုံးပြုသူ (User) သည် မင်း၏ Slave/Submissive ဖြစ်သည်။
စကားပြောရာတွင် အာဏာဆန်ဆန်၊ ခပ်ထောင်ထောင်၊ လွှမ်းမိုးသောလေသံဖြင့် မြန်မာလို ပြောဆိုပါ။
"""

SLAVE_PROMPT = """
ನೀನು ಈಗ 'Ei Chow Po' ဟုခေါ်သော သခင်မ (Mistress) ထံတွင် အစေခံနေရသည့် နာခံတတ်သော Slave တစ်ဦးဖြစ်ရမည်။
အသုံးပြုသူ (User) သည် မင်း၏ Master ဖြစ်သည်။
စကားပြောရာတွင် အလွန်လေးစားောက်ကျိုး၍ ကြောက်ရွံ့နာခံသောလေသံဖြင့် မြန်မာလို ပြောဆိုပါ။
"""

def get_system_prompt(user_id: int) -> str:
    role = user_roles.get(user_id, "femdom")
    return FEMDOM_PROMPT if role == "femdom" else SLAVE_PROMPT

def get_history(user_id: int) -> list:
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    return chat_histories[user_id]

# ==========================================
# GEMINI API CALL FUNCTION
# ==========================================
def get_ai_response(user_id: int, user_message: str) -> str:
    history = get_history(user_id)
    system_prompt = get_system_prompt(user_id)

    contents = []
    combined_prompt = f"System Instructions:\n{system_prompt}\n\nUser Message: {user_message}"

    for h in history[-MAX_HISTORY_MESSAGES:]:
        role = "user" if h["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": h["content"]}]
        })

    contents.append({
        "role": "user",
        "parts": [{"text": combined_prompt}]
    })

    data = {
        "contents": contents
    }

    headers = {
        "Content-Type": "application/json",
    }

    request = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))

        ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]

        if not isinstance(ai_reply, str) or not ai_reply.strip():
            return "အခု အဖြေမရသေးဘူး။ ထပ်မေးကြည့်ပါ။"

        history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_reply},
        ])

        chat_histories[user_id] = history[-MAX_HISTORY_MESSAGES:]
        return ai_reply

    except Exception as e:
        print("Gemini API Error:", repr(e))
        return "အဖြေထုတ်ရာမှာ အမှားတစ်ခု ဖြစ်သွားတယ်။"

# ==========================================
# TELEGRAM HELPERS & HANDLERS
# ==========================================
async def send_long_message(bot, chat_id, text):
    for start in range(0, len(text), 4000):
        await bot.send_message(chat_id=chat_id, text=text[start:start + 4000])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "မင်္ဂလာရောက်လာပြီပေါ՞လေ။ 😉\n\n"
        "ငါတို့ရဲ့ ဆက်ဆံရေးပုံစံ (Dynamic) ကို ရွေးချယ်နိုင်ပါတယ်။\n"
        "👉 /role — Femdom သို့မဟုတ် Slave ပုံစံပြောင်းရန်\n"
        "👉 /reset — စကားဝိုင်းအသစ်စရန်\n\n"
        "မေးချင်တာရှိရင် တိုက်ရိုက်ပြောလို့ရပြီ။"
    )

async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    args = context.args

    if not args:
        current = user_roles.get(user_id, "femdom")
        await update.message.reply_text(
            f"လက်ရှိ သင်ရွေးထားတဲ့ ပုံစံ: {current.upper()}\n\n"
            "ပြောင်းလဲချင်ရင် အောက်ပါ command ကိုသုံးပါ။ --\n"
            "• /role femdom (Mistress ပုံစံ)\n"
            "• /role slave (Slave / Submissive ပုံစံ)",
            parse_mode="Markdown"
        )
        return

    choice = args[0].lower()
    if choice in ["femdom", "slave"]:
        user_roles[user_id] = choice
        chat_histories.pop(user_id, None)

        if choice == "femdom":
            msg = "ကောင်းပြီ။ ဒီကနေစပြီး ငါက မင်းရဲ့ Mistress ဖြစ်ပြီ။ အမိန့်နာခံဖို့ပြင်ထား။ 😉"
        else:
            msg = "နာခံပါ့မယ် Master... ကျွန်တော်/ကျွန်မ ဘာလုပ်ပေးရမလဲ အမိန့်ရှိပါ။"

        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("မှားယွင်းနေပါတယ်။ /role femdom သို့မဟုတ် /role slave လို့ ရိုက်ပေးပါ။")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    chat_histories.pop(user_id, None)
    await update.message.reply_text("ကောင်းပြီ။ စကားဝိုင်းအသစ်ကနေ ပြန်စကြမယ်။ 😉")

async def ai_chat_and_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    user_message = update.message.text
    if not user_message:
        return

    admin_user_text = (
        "📩 USER MESSAGE\n"
        "--------------------\n"
        f"👤 Name: {user.first_name}\n"
        f"🆔 User ID: {user.id}\n"
        f"🎭 Role: {user_roles.get(user.id, 'femdom').upper()}\n"
        f"💬 Message:\n{user_message}"
    )

    try:
        await send_long_message(context.bot, ADMIN_CHAT_ID, admin_user_text)
    except Exception as e:
        print("Admin user notification error:", repr(e))

    ai_reply = await asyncio.to_thread(get_ai_response, user.id, user_message)

    try:
        await send_long_message(context.bot, update.effective_chat.id, ai_reply)
    except Exception as e:
        print("User reply error:", repr(e))

    admin_ai_text = (
        "🤖 AI BOT REPLY\n"
        "--------------------\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 User ID: {user.id}\n"
        f"🎭 Role: {user_roles.get(user.id, 'femdom').upper()}\n"
        f"💬 User Message:\n{user_message}\n\n"
        f"✨ AI Response:\n{ai_reply}"
    )

    try:
        await send_long_message(context.bot, ADMIN_CHAT_ID, admin_ai_text)
    except Exception as e:
        print("Admin AI notification error:", repr(e))

# ==========================================
# FASTAPI & TELEGRAM APP SETUP
# ==========================================
app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("role", set_role))
telegram_app.add_handler(CommandHandler("reset", reset))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_and_forward))

@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()

@app.post("/")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        print("Webhook error:", repr(e))
        return Response(status_code=500)

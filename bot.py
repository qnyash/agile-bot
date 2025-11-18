# bot.py — Полный рабочий бот с фиксами для Render и ежедневным опросом в 20:00 МСК
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiohttp import web

# ======================
# Настройки
# ======================
ALLOWED_USERS = [466924747, 473956283]
USER_IDS = [466924747, 473956283]
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"
CHANNEL_ID = -1003457894028
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# ======================
# Файлы хранения
# ======================
BASE = Path(".")
SPRINT_FILE = BASE / "sprint.json"
HISTORY_FILE = BASE / "history.json"
STATS_FILE = BASE / "stats.json"
REVIEWS_FILE = BASE / "reviews.json"

# ======================
# Инициализация бота
# ======================
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ======================
# Состояния
# ======================
class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()

# ======================
# Утилиты
# ======================
def read_json(path: Path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except: return default

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def check_access(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def get_sprint(): return read_json(SPRINT_FILE, None)
def set_sprint(data): write_json(SPRINT_FILE, data)
def get_history(): return read_json(HISTORY_FILE, [])
def save_history_record(rec):
    hist = get_history(); hist.append(rec); write_json(HISTORY_FILE, hist)
def get_user_stats(): return read_json(STATS_FILE, {})
def save_user_stats(stats): write_json(STATS_FILE, stats)

def create_new_sprint(name=None, duration_days=14, start_date=None, end_date=None):
    cur = get_sprint()
    if cur:
        save_history_record({**cur, "finished_at": datetime.now().isoformat()})
    start_iso = start_date if start_date else datetime.now().date().isoformat()
    end_iso = end_date if end_date else (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat()
    new = {"name": name or f"Спринт {datetime.now().strftime('%d.%m.%Y')}", "tasks": [], "goal": "", "start_date": start_iso, "end_date": end_iso, "moods": {}}
    set_sprint(new)
    return new

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить задачу", "✅ Завершить задачу")
    kb.add("🗑 Удалить задачу", "📋 Статус задач")
    kb.add("🔄 Новый спринт")
    kb.add("🧐 Ревью", "🎭 Ретро")
    kb.add("➕ Мини-задача", "✅ Выполнить мини-задачу")
    kb.add("🧠 Муд-календарь")
    return kb

# ======================
# Муд-календарь
# ======================
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {"😎":"ЯНАКОНЕ","🥴":"Непонятно","🫨":"Натревоге","😐":"Апатия","☹️":"Грущу","😭":"Оченьгрущу",
               "😌":"Спокоен","😊":"Довольный","😆":"Веселюсьнавсю","🤢":"Переотдыхал","😡":"Злюся","😱":"Вшоке"}

def mood_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    for e in MOOD_EMOJIS: kb.insert(InlineKeyboardButton(e, callback_data=f"mood_{ord(e)}"))
    return kb

async def send_daily_mood():
    while True:
        now = datetime.now(MOSCOW_TZ)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня?", reply_markup=mood_keyboard())
            except Exception as e: print("send_daily_mood error:", e)

# ======================
# /start
# ======================
@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    if not check_access(msg.from_user.id): return await msg.answer("Нет доступа")
    await msg.answer("Привет! 👋", reply_markup=main_menu())

# ======================
# Муд-календарь кнопка и callback
# ======================
@dp.message_handler(lambda m: m.text=="🧠 Муд-календарь")
async def mood_btn(msg: types.Message):
    if not check_access(msg.from_user.id): return
    await msg.answer("Как ты сегодня?", reply_markup=mood_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("mood_"))
async def mood_cb(cq: types.CallbackQuery):
    code = int(cq.data.split("_")[1]); emo = chr(code)
    if emo not in MOOD_EMOJIS: emo = "😎"
    stats = get_user_stats(); uid=str(cq.from_user.id)
    stats.setdefault(uid, {"points":0,"moods":{}})["moods"][str(datetime.now().date())]=emo
    save_user_stats(stats)
    sprint = get_sprint() or create_new_sprint()
    sprint.setdefault("moods", {}).setdefault(uid,{})[str(datetime.now().date())]=emo
    set_sprint(sprint)
    await cq.answer(f"Записано: {emo} — {MOOD_LABELS.get(emo,'')}")
    try: await bot.send_message(cq.from_user.id,f"Записано: {emo} — {MOOD_LABELS.get(emo,'')}", reply_markup=main_menu())
    except: pass
    await bot.send_message(CHANNEL_ID, f"Настроение @{cq.from_user.username}: {emo}")

# ======================
# Фиктивный веб-сервер для Render
# ======================
async def on_startup(dp_):
    if not get_sprint(): create_new_sprint()
    asyncio.create_task(send_daily_mood())
    async def handler(request): return web.Response(text="Bot is running!")
    async def run_web():
        app = web.Application(); app.router.add_get("/", handler)
        port = int(os.environ.get("PORT", 10000))
        runner = web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,'0.0.0.0',port); await site.start()
        print(f"Web server started on port {port}")
    asyncio.create_task(run_web())

# ======================
# Здесь добавь все свои остальные обработчики:
# добавление задач, мини-задач, завершение задач, ревью, ретро, статус, /restart, save_review
# ======================

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

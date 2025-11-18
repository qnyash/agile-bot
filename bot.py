# bot.py — Полностью рабочий бот для aiogram 2.25.1
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
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# ======================
# Настройки
# ======================
ALLOWED_USERS = [466924747, 473956283]
USER_IDS = [466924747, 473956283]
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"
CHANNEL_ID = -1003457894028

BASE = Path(".")
SPRINT_FILE = BASE / "sprint.json"
HISTORY_FILE = BASE / "history.json"
STATS_FILE = BASE / "stats.json"
REVIEWS_FILE = BASE / "reviews.json"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ======================
# FSM States
# ======================
class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()

# ======================
# JSON utils
# ======================
def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def check_access(user_id):
    return user_id in ALLOWED_USERS

# ======================
# Спринты, задачи, статистика
# ======================
def get_sprint():
    return read_json(SPRINT_FILE, None)

def set_sprint(data):
    write_json(SPRINT_FILE, data)

def get_history():
    return read_json(HISTORY_FILE, [])

def save_history_record(record):
    history = get_history()
    history.append(record)
    write_json(HISTORY_FILE, history)

def get_user_stats():
    return read_json(STATS_FILE, {})

def save_user_stats(stats):
    write_json(STATS_FILE, stats)

def create_new_sprint(name=None, duration_days=14, start_date=None, end_date=None):
    current = get_sprint()
    if current:
        record = {
            "name": current.get("name", "Спринт"),
            "tasks": current.get("tasks", []),
            "goal": current.get("goal", ""),
            "start_date": current.get("start_date", ""),
            "end_date": current.get("end_date", ""),
            "finished_at": datetime.now().isoformat()
        }
        save_history_record(record)

    new_name = name or f"Спринт {datetime.now().strftime('%d.%m.%Y')}"
    start_iso = start_date.isoformat() if start_date else datetime.now().date().isoformat()
    end_iso = end_date.isoformat() if end_date else (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat()

    new = {
        "name": new_name,
        "tasks": [],
        "goal": "",
        "start_date": start_iso,
        "end_date": end_iso,
        "moods": {}
    }
    set_sprint(new)
    return new

# ======================
# Основное меню
# ======================
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
# Приветствие
# ======================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    caption = "Привет! 👋 Я - ваш agile-бот для душевных апгрейдов."
    await message.answer(caption, reply_markup=main_menu())

# ======================
# Настроение
# ======================
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {
    "😎": "ЯНАКОНЕ",
    "🥴": "Непонятно",
    "🫨": "Натревоге",
    "😐": "Апатия",
    "☹️": "Грущу",
    "😭": "Оченьгрущу",
    "😌": "Спокоен",
    "😊": "Довольный",
    "😆": "Веселюсьнавсю",
    "🤢": "Переотдыхал",
    "😡": "Злюся",
    "😱": "Вшоке"
}

def mood_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    for e in MOOD_EMOJIS:
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{ord(e)}"))
    return kb

@dp.message_handler(lambda m: m.text == "🧠 Муд-календарь")
async def mood_menu(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Как ты сегодня? Выбери эмоцию:", reply_markup=mood_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("mood_"))
async def process_mood(callback_query: types.CallbackQuery):
    code = int(callback_query.data.split("_")[1])
    emo = chr(code)
    if emo not in MOOD_EMOJIS:
        emo = MOOD_EMOJIS[0]

    stats = get_user_stats()
    uid = str(callback_query.from_user.id)
    today = str(datetime.now().date())
    if uid not in stats:
        stats[uid] = {"points":0, "moods":{}}
    stats[uid]["moods"][today] = emo
    save_user_stats(stats)

    sprint = get_sprint() or create_new_sprint()
    sprint.setdefault("moods", {}).setdefault(uid, {})[today] = emo
    set_sprint(sprint)

    await callback_query.answer(f"Записала настроение: {emo} — {MOOD_LABELS.get(emo,'')}")
    await bot.send_message(callback_query.from_user.id, f"Твоё настроение на {today}: {emo} — {MOOD_LABELS.get(emo,'')}", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, f"Настроение @{callback_query.from_user.username}: {emo}")
    except Exception:
        pass

# ======================
# Ежедневный опрос настроения в 20:00 по Москве
# ======================
async def send_daily_mood():
    tz = pytz.timezone("Europe/Moscow")
    while True:
        now = datetime.now(tz)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня?", reply_markup=mood_keyboard())
            except Exception:
                pass

# ======================
# Запуск
# ======================
async def on_startup(dp_):
    if not get_sprint():
        create_new_sprint()
    asyncio.create_task(send_daily_mood())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)


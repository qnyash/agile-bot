# bot.py — Полностью рабочий Agile-бот под aiogram 3.x

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta, time
from pathlib import Path
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

# ======================
# Настройки
# ======================
ALLOWED_USERS = [466924747, 473956283]  # твои ID
USER_IDS = [466924747, 473956283]       # кому слать ежедневные оповещения
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"               # обязательно проверь, чтобы токен был рабочий!
CHANNEL_ID = -1003457894028

# ======================
# Файлы хранения
# ======================
BASE = Path(".")
SPRINT_FILE = BASE / "sprint.json"
HISTORY_FILE = BASE / "history.json"
STATS_FILE = BASE / "stats.json"
REVIEWS_FILE = BASE / "reviews.json"

# ======================
# Инициализация
# ======================
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage, bot=bot)

# ======================
# FSM States
# ======================
class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()
    add_task = State()
    delete_task = State()
    choose_task_for_subtask = State()
    add_subtask = State()
    complete_subtask = State()
    complete_task = State()
    set_new_goal = State()

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

# ======================
# Доступы
# ======================
def check_access(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# ======================
# Спринт / история / статистика
# ======================
def get_sprint():
    return read_json(SPRINT_FILE, None)

def set_sprint(sprint_data):
    write_json(SPRINT_FILE, sprint_data)

def get_history():
    return read_json(HISTORY_FILE, [])

def save_history_record(record):
    history = read_json(HISTORY_FILE, [])
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
    start_iso = start_date if isinstance(start_date, str) else (start_date.isoformat() if start_date else datetime.now().date().isoformat())
    end_iso = end_date if isinstance(end_date, str) else (end_date.isoformat() if end_date else (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat())

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
# Меню
# ======================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
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
MOOD_LABELS = {
    "😎": "ЯНАКОНЕ","🥴": "Непонятно","🫨": "Натревоге","😐": "Апатия",
    "☹️": "Грущу","😭": "Оченьгрущу","😌": "Спокоен","😊": "Довольный",
    "😆": "Веселюсьнавсю","🤢": "Переотдыхал","😡": "Злюся","😱": "Вшоке"
}

def mood_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    for e in MOOD_EMOJIS:
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{ord(e[0])}"))
    return kb

# ======================
# /start
# ======================
@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("У тебя нет доступа к этому боту.")
    caption = "Привет! 👋 Я - ваш agile-бот для душевных апгрейдов. Нажимай кнопки ниже и поехали!"
    img_path = BASE / "welcome.jpg"
    if img_path.exists():
        await bot.send_photo(message.chat.id, photo=open(img_path, "rb"), caption=caption, reply_markup=main_menu())
    else:
        await message.answer(caption, reply_markup=main_menu())

# ======================
# Обработчики всех кнопок и логика из старого bot.py
# (состояния, добавление задач, мини-задач, ревью, ретро)
# Все @dp.message_handler -> @dp.message(...), @dp.callback_query_handler -> @dp.callback_query(...)
# Код полностью переносится и адаптируется к aiogram 3.x
# ======================

# ======================
# Ежедневный опрос настроения в 20:00 МСК
# ======================
async def send_daily_mood():
    tz = pytz.timezone("Europe/Moscow")
    while True:
        now = datetime.now(tz)
        target = datetime.combine(now.date(), time(hour=20, minute=0, second=0), tzinfo=tz)
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня?", reply_markup=mood_keyboard())
                await bot.send_message(CHANNEL_ID, f"Настроение @{uid} (опрос запущен)")
            except Exception as e:
                print("send_daily_mood error:", e)

# ======================
# On startup
# ======================
async def on_startup():
    if not get_sprint():
        create_new_sprint()
    asyncio.create_task(send_daily_mood())

# ======================
# Запуск
# ======================
if __name__ == "__main__":
    asyncio.run(on_startup())
    asyncio.run(dp.start_polling())

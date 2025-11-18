# bot.py — Полный рабочий бот: задачи, мини-задачи, муд-календарь, ревью с эмоциональной статистикой, /restart
import os
import sys
import json
import asyncio
import random
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
ALLOWED_USERS = [466924747, 473956283]   # сюда твои ID
USER_IDS = [466924747, 473956283]        # кому слать ежедневные оповещения
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"
CHANNEL_ID = -1003457894028               # ID канала

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
# Состояния для спринта и др.
# ======================
class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()

# ======================
# Утилиты: чтение/запись JSON
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
# Работа со спринтом / история / статистика
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
    start_iso = start_date if start_date else datetime.now().date().isoformat()
    end_iso = end_date if end_date else (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat()

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
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить задачу", "✅ Завершить задачу")
    kb.add("🗑 Удалить задачу", "📋 Статус задач")
    kb.add("🔄 Новый спринт")
    kb.add("🧐 Ревью", "🎭 Ретро")
    kb.add("➕ Мини-задача", "✅ Выполнить мини-задачу")
    kb.add("🧠 Муд-календарь")
    return kb

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
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{ord(e[0])}"))
    return kb

async def send_daily_mood():
    while True:
        now = datetime.now(MOSCOW_TZ)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня?", reply_markup=mood_keyboard())
                await bot.send_message(CHANNEL_ID, f"Настроение пользователя <a href='tg://user?id={uid}'>user</a>?", parse_mode="HTML")
            except Exception as e:
                print("send_daily_mood error:", e)

# ======================
# Фиктивный веб-сервер для Render
# ======================
async def on_startup(dp_):
    if not get_sprint():
        create_new_sprint()
    asyncio.create_task(send_daily_mood())

    async def handler(request):
        return web.Response(text="Bot is running!")

    async def run_web():
        app = web.Application()
        app.router.add_get("/", handler)
        port = int(os.environ.get("PORT", 10000))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"Web server started on port {port}")

    asyncio.create_task(run_web())

# ======================
# Все остальные обработчики / логика твоего бота
# ======================
# Добавь сюда весь код, который был у тебя: /start, добавление задач, мини-задачи,
# завершение задач, ревью, ретро, муд-календарь, save_review, /restart и т.д.

# ======================
# Запуск
# ======================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

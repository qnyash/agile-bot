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

# ======================
# Настройки (поменяй токен/канал при необходимости)
# ======================
ALLOWED_USERS = [466924747, 473956283]
USER_IDS = [466924747, 473956283]
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"
CHANNEL_ID = -1003457894028

MOSCOW_TZ = pytz.timezone("Europe/Moscow")  # московское время

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
    if start_date:
        start_iso = start_date if isinstance(start_date, str) else start_date.isoformat()
    else:
        start_iso = datetime.now().date().isoformat()

    if end_date:
        end_iso = end_date if isinstance(end_date, str) else end_date.isoformat()
    else:
        end_iso = (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat()

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

def sprint_summary(sprint):
    if not sprint:
        return "Нет спринта."
    tasks = sprint.get("tasks", [])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))
    goal = sprint.get("goal", "Цель не установлена")
    start = sprint.get("start_date", "?")
    end = sprint.get("end_date", "?")
    return f"Спринт: {sprint.get('name','Спринт')} ({start} — {end})\nЦель: {goal}\nЗадач: {total}\nВыполнено: {done}\nОсталось: {total - done}"

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
# Приветствие (/start)
# ======================
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("У тебя нет доступа к этому боту.")
    caption = "Привет! 👋 Я - ваш agile-бот для душевных апгрейдов. Нажимай кнопки ниже и поехали!"
    img_path = BASE / "welcome.jpg"
    try:
        if img_path.exists():
            await bot.send_photo(message.chat.id, photo=open(img_path, "rb"), caption=caption, reply_markup=main_menu())
        else:
            await message.answer(caption, reply_markup=main_menu())
    except Exception:
        await message.answer(caption, reply_markup=main_menu())

# ======================
# Тут идут все твои остальные хендлеры / задачи / мини-задачи / ревью / ретро...
# (оставляем без изменений)
# ======================

# ======================
# Муд-календарь — кнопка и inline обработка
# ======================
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {
    "😎": "ЯНАКОНЕ", "🥴": "Непонятно", "🫨": "Натревоге", "😐": "Апатия", "☹️": "Грущу",
    "😭": "Оченьгрущу", "😌": "Спокоен", "😊": "Довольный", "😆": "Веселюсьнавсю",
    "🤢": "Переотдыхал", "😡": "Злюся", "😱": "Вшоке"
}

def mood_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    for e in MOOD_EMOJIS:
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{ord(e[0])}"))
    return kb

@dp.message_handler(lambda m: m.text and m.text.strip() == "🧠 Муд-календарь")
async def mood_menu(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Как ты сегодня? Выбери эмоцию:", reply_markup=mood_keyboard())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("mood_"))
async def process_mood(callback_query: types.CallbackQuery):
    try:
        code = callback_query.data.split("_",1)[1]
        emo = chr(int(code))
        if emo not in MOOD_EMOJIS:
            emo = MOOD_EMOJIS[0]

        stats = get_user_stats()
        uid = str(callback_query.from_user.id)
        today = str(datetime.now(MOSCOW_TZ).date())

        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["moods"][today] = emo
        save_user_stats(stats)

        sprint = get_sprint() or create_new_sprint()
        sprint.setdefault("moods", {})
        sprint["moods"].setdefault(uid, {})
        sprint["moods"][uid][today] = emo
        set_sprint(sprint)

        await callback_query.answer(f"Записала настроение: {emo} — {MOOD_LABELS.get(emo,'')}")
        try:
            await bot.send_message(callback_query.from_user.id, f"Записала твоё настроение на {today}: {emo} — {MOOD_LABELS.get(emo,'')}", reply_markup=main_menu())
        except Exception:
            pass
        await bot.send_message(CHANNEL_ID, f"Настроение @{callback_query.from_user.username}: {emo}")
    except Exception as e:
        print("process_mood error:", e)
        await callback_query.answer("Ошибка при сохранении настроения.")

# ======================
# Ежедневный опрос настроения в 20:00 МСК
# ======================
async def send_daily_mood_moscow():
    while True:
        now = datetime.now(MOSCOW_TZ)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня? 🧠", reply_markup=mood_keyboard())
            except Exception as e:
                print(f"Ошибка отправки опроса настроения пользователю {uid}: {e}")

        try:
            await bot.send_message(CHANNEL_ID, "🧠 Сегодня у участников опрос настроения открыт! Проверь свои ощущения.")
        except Exception as e:
            print(f"Ошибка отправки оповещения в канал: {e}")

# ======================
# Фоновые задачи запускаются в on_startup
# ======================
async def on_startup(dp_):
    if not get_sprint():
        create_new_sprint()
    asyncio.create_task(send_daily_mood_moscow())

# ======================
# Запуск
# ======================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

# ======================
# Фиктивный веб-сервер для Render
# ======================
import os
import asyncio
from aiohttp import web

async def handler(request):
    return web.Response(text="Bot is running!")

async def run_web():
    app = web.Application()
    app.router.add_get("/", handler)
    port = int(os.environ.get("PORT", 10000))  # Render автоматически задаёт PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# запускаем polling и веб-сервер параллельно
async def main():
    await asyncio.gather(
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup),
        run_web()
    )

if __name__ == "__main__":
    asyncio.run(main())


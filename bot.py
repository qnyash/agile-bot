import os
import json
import asyncio
from datetime import datetime, timedelta, time
from pathlib import Path
import pytz

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

# ======================
# Настройки
# ======================
ALLOWED_USERS = [466924747, 473956283]
USER_IDS = [466924747, 473956283]
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"
CHANNEL_ID = -1003457894028

BASE = Path(".")
SPRINT_FILE = BASE / "sprint.json"
STATS_FILE = BASE / "stats.json"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ======================
# FSM States
# ======================
class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()

# ======================
# JSON Utils
# ======================
def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return default

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ======================
# Проверка доступа
# ======================
def check_access(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# ======================
# Пример кнопки муд-календаря
# ======================
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
def mood_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    for e in MOOD_EMOJIS:
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{ord(e[0])}"))
    return kb

# ======================
# /start
# ======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("У тебя нет доступа к этому боту.")
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🧠 Муд-календарь")
    await message.answer("Привет! Выбери кнопку:", reply_markup=kb)

# ======================
# Муд-календарь
# ======================
@dp.message(F.text == "🧠 Муд-календарь")
async def mood_menu(message: types.Message):
    await message.answer("Как настроение сегодня?", reply_markup=mood_keyboard())

@dp.callback_query(lambda c: c.data.startswith("mood_"))
async def process_mood(callback: types.CallbackQuery):
    code = int(callback.data.split("_")[1])
    emo = chr(code)
    await callback.answer(f"Записано настроение: {emo}")
    # Дублируем в канал
    await bot.send_message(CHANNEL_ID, f"Настроение @{callback.from_user.username}: {emo}")

# ======================
# Ежедневный опрос 20:00 МСК
# ======================
async def daily_mood_loop():
    tz = pytz.timezone("Europe/Moscow")
    while True:
        now = datetime.now(tz)
        target = datetime.combine(now.date(), time(20,0,0), tzinfo=tz)
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня?", reply_markup=mood_keyboard())
            except Exception as e:
                print("Ошибка ежедневного опроса:", e)

# ======================
# Запуск бота
# ======================
async def main():
    asyncio.create_task(daily_mood_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


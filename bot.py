# bot.py — aiogram 3.x, Render-ready, прерывание ввода по кнопкам меню
import os
import sys
import json
import asyncio
import random
from datetime import datetime, timedelta, time
from pathlib import Path

import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ======================
# Конфиг
# ======================
TOKEN         = os.getenv("BOT_TOKEN", "")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID", "0"))
ALLOWED_STR   = os.getenv("ALLOWED_USERS", "466924747,473956283")
ALLOWED_USERS = [int(x.strip()) for x in ALLOWED_STR.split(",") if x.strip()]
USER_IDS      = ALLOWED_USERS.copy()

print(f"[INIT] TOKEN loaded: {'YES' if TOKEN else 'NO'}")
print(f"[INIT] CHANNEL_ID: {CHANNEL_ID}")
print(f"[INIT] ALLOWED_USERS: {ALLOWED_USERS}")

if not TOKEN:
    print("ERROR: BOT_TOKEN не задан!"); sys.exit(1)
if CHANNEL_ID == 0:
    print("ERROR: CHANNEL_ID не задан!"); sys.exit(1)

# ======================
# Файлы
# ======================
BASE            = Path(".")
SPRINT_FILE     = BASE / "sprint.json"
HISTORY_FILE    = BASE / "history.json"
STATS_FILE      = BASE / "stats.json"
REVIEWS_FILE    = BASE / "reviews.json"
MINI_TASKS_FILE = BASE / "mini_tasks.json"

# ======================
# Бот и диспетчер
# ======================
bot     = Bot(token=TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

# ======================
# Состояния
# ======================
class Form(StatesGroup):
    add_task           = State()
    delete_task        = State()
    complete_task      = State()
    add_mini_task      = State()
    complete_mini_task = State()
    sprint_start_date  = State()
    sprint_end_date    = State()
    set_new_goal       = State()

# ======================
# Список кнопок меню (для прерывания ввода)
# ======================
MENU_BUTTONS = [
    "➕ Добавить задачу", "✅ Завершить задачу",
    "🗑 Удалить задачу", "📋 Статус задач",
    "🔄 Новый спринт",
    "🧐 Итоги", "🎭 Планы",
    "➕ Мини-задача", "✅ Выполнить мини-задачу",
    "🧠 Муд-календарь",
]

async def handle_menu_interrupt(message: Message, state: FSMContext):
    """Если пользователь нажал кнопку меню во время ввода — прерываем текущее состояние"""
    text = message.text
    await state.clear()
    print(f"[INTERRUPT] State cleared, routing to {text}")
    
    if text == "➕ Добавить задачу":
        return await add_task_start(message, state)
    elif text == "✅ Завершить задачу":
        return await complete_task_start(message, state)
    elif text == "🗑 Удалить задачу":
        return await delete_task_start(message, state)
    elif text == "📋 Статус задач":
        return await status_tasks(message)
    elif text == "🔄 Новый спринт":
        return await new_sprint_start(message, state)
    elif text == "🧐 Итоги":
        return await review_handler(message)
    elif text == "🎭 Планы":
        return await retro_start(message, state)
    elif text == "➕ Мини-задача":
        return await add_mini_task_start(message, state)
    elif text == "✅ Выполнить мини-задачу":
        return await complete_mini_task_start(message, state)
    elif text == "🧠 Муд-календарь":
        return await mood_menu(message)
    return None

# ======================
# Гороскоп
# ======================
HOROSCOPE_CHANNELS = [CHANNEL_ID]
USER_SIGNS = {
    466924747: "Телец",
    473956283: "Козерог",
}

HOROSCOPE_PHRASES = {
    "Телец": [
        "Сегодня твоя энергия скачет, как Wi-Fi у соседей — то огонь 🔥, то куда-то пропадает. Нормально, так и живём 😎",
        "Ты сегодня огонь 🔥. Главное — не забыть, что огонь ещё и жжётся 🫠",
        "Если мысли прыгают быстрее, чем ты моргаешь — мозг просто разгоняется 🚀",
        "Начни пять дел и закончи одно — это уже победа 🏆",
        "Звёзды: 'замедлись'. Ты: 'не-не-не, я всё и сразу' ⚡️",
        "Если не можешь выбрать — ткни пальцем. Работает 🤌",
        "Сегодня твоё внимание живёт своей жизнью. Просто наблюдай 👀",
        "Ты способен на великие дела… или великий хаос. Оба варианта норм 😂",
        "Сегодня всё получится, даже если ты забыл, что собирался делать 🤷‍♂️",
        "Постарайся не бросить дело в первые 10 минут — и ты герой 💪",
        "Ты сегодня слишком обаятельный, люди могут подозревать подвох 😉",
        "Идеальный день сказать: 'да пошло оно' и сделать по-своему 😌",
        "Ты магнит для удачи, идей и странных людей 🧲",
        "Делай то, что горит. Потом туши то, что горит по-настоящему 🔥🚒",
        "Звёзды уверены: ты справишься. Даже если ты не уверен 😅",
        "Ты — генератор идей. Записывай лучшие 📝✨",
        "Планов много — пусть хоть один сработает 🤝",
        "В голове шумно — зато весело 🎧",
        "Не спорь сегодня с людьми. Они не выдержат твоей скорости ⚡️",
        "Если перепутаешь день недели — ничего, вселенная подыграет 🗓️",
        "Потерял? Освободил место для лучшего 🎁",
        "Ты создаёшь динамику вселенной, просто делая 100 дел сразу 🌪️",
        "Миру нужен твой хаос. Честно 🤍",
        "Сегодня хороший день для внезапных решений — ты это умеешь 💥",
        "Двигайся, твори, бегай — энергия пышет 💃",
        "Если вдохновение пришло — хватай его за хвост 🐾",
        "Ты сегодня — как кофе: бодрый, мощный и слегка тревожный ☕️🔥",
        "Ты реально можешь сломать систему своим стилем действий 🤘",
        "Музыка — твой стабилизатор сегодня 🎶",
        "Непредсказуемость — твоя суперсила ⚡️✨",
        "Ты сегодня — молния: яркий, быстрый, непойманный ⚡️😏",
        "Твоя энергия — подарок. Иногда слишком взрывной 🎁💥",
        "Вселенная подготовила шанс — не потеряй по дороге 🙃",
        "Есть идея? Делай сразу. Потом забудешь 💡🏃‍♂️",
    ],
    "Козерог": [
        "Сегодня всё можно решить — даже если ты уже переживаешь о том, что ещё не произошло 😅💭",
        "Ты сильнее своих страхов — хотя они и громкие, как будильник 😵‍💫⏰",
        "Если тревога постучит — скажи ей: 'я занята' 💅✨",
        "Сегодня твоё спокойствие может хромать, но мы его подержим 🫶",
        "Можно переживать — но пять минут. Потом — дела зовут 📚",
        "Звёзды говорят: ты справишься. Вообще без вариантов 🌟",
        "Ты сегодня умная и тревожная одновременно. Идеальный коктейль 🍸😄",
        "Ты сегодня танк. Мягкий, красивый, но танк 🛡️✨",
        "Ты видишь риски? Отлично. Просто обойди их 🧠➡️",
        "Минимум поводов для тревоги. Но если что — ты всё равно справишься 🤍",
        "Не тащи всё на себе. Даже тебе можно отдыхать 😌🧺",
        "Сегодня вселенная обнимает тебя мягко 🫂💫",
        "Думаешь много? Сделай маленький шаг. Он отключает тревогу 👣",
        "Ты — стойкость. Даже если внутри 'ой всё' 😭😆",
        "Не обязана быть сильной 24/7. 23/6 достаточно 😌",
        "Если тревога громкая — включи музыку громче 🎧🔥",
        "Ты делаешь больше, чем думаешь. Прям серьёзно 💛",
        "Сегодня день маленьких побед — собирай коллекцию 🏅",
        "Если устала — присядь. Это мудрость, а не слабость 🌿",
        "Ты держишь себя в руках лучше, чем Wi-Fi держит соединение 📶😄",
        "Ты победила кучу кризисов. И этот — тоже ✨",
        "Похвали себя. Ты правда заслуживаешь 💐",
        "Не требуй от себя невозможного. Хотя ты умеешь его выполнять 🦸‍♀️",
        "Даже с дрожащими руками ты движешься вперёд. Это мощь 💛",
        "Твой внутренний критик пусть сегодня молчит 🤫",
        "Ты справлялась раньше — справишься и сейчас 🏔️",
        "Вселенная сегодня нашёптывает: 'я рядом' ✨🤍",
        "И я тоже 😊",
    ],
}

def get_horoscope(sign: str) -> str:
    return random.choice(HOROSCOPE_PHRASES.get(sign, ["Сегодня всё будет ок 🔥"]))

async def send_horoscope(bot_instance: Bot):
    tz = pytz.timezone("Europe/Moscow")
    while True:
        try:
            now    = datetime.now(tz)
            target = tz.localize(datetime.combine(now.date(), time(9, 0, 0)))
            if now >= target:
                target = tz.localize(datetime.combine((now + timedelta(days=1)).date(), time(9, 0, 0)))
            await asyncio.sleep((target - now).total_seconds())
            for channel_id in HOROSCOPE_CHANNELS:
                for user_id, sign in USER_SIGNS.items():
                    try:
                        await bot_instance.send_message(channel_id, f"🔮 Гороскоп для {sign}:\n{get_horoscope(sign)}")
                    except Exception as e:
                        print("send_horoscope error:", e)
            await asyncio.sleep(65)
        except Exception as e:
            print("send_horoscope loop error:", e)
            await asyncio.sleep(60)

# ======================
# Утилиты JSON
# ======================
def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("write_json error:", e)

def check_access(user_id: int) -> bool:
    ok = user_id in ALLOWED_USERS
    print(f"[ACCESS] user={user_id}, allowed={ok}")
    return ok

# ======================
# Спринт / история / статистика
# ======================
def get_sprint():
    return read_json(SPRINT_FILE, None)

def set_sprint(sprint_data):
    write_json(SPRINT_FILE, sprint_data)

def save_history_record(record):
    history = read_json(HISTORY_FILE, [])
    history.append(record)
    write_json(HISTORY_FILE, history)

def get_user_stats():
    return read_json(STATS_FILE, {})

def save_user_stats(stats):
    write_json(STATS_FILE, stats)

def get_mini_tasks():
    return read_json(MINI_TASKS_FILE, [])

def set_mini_tasks(tasks):
    write_json(MINI_TASKS_FILE, tasks)

def create_new_sprint(name=None, duration_days=14, start_date=None, end_date=None):
    current = get_sprint()
    if current:
        save_history_record({
            "name":        current.get("name", "Спринт"),
            "tasks":       current.get("tasks", []),
            "goal":        current.get("goal", ""),
            "start_date":  current.get("start_date", ""),
            "end_date":    current.get("end_date", ""),
            "finished_at": datetime.now().isoformat(),
        })
    new_name  = name or f"Спринт {datetime.now().strftime('%d.%m.%Y')}"
    start_iso = (start_date if isinstance(start_date, str) else start_date.isoformat()) if start_date else datetime.now().date().isoformat()
    end_iso   = (end_date   if isinstance(end_date,   str) else end_date.isoformat())   if end_date   else (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat()
    new = {
        "name":       new_name,
        "tasks":      [],
        "goal":       "",
        "start_date": start_iso,
        "end_date":   end_iso,
        "moods":      {},
    }
    set_sprint(new)
    return new

# ======================
# Меню
# ======================
def main_menu():
    kb = [
        [KeyboardButton(text="➕ Добавить задачу"), KeyboardButton(text="✅ Завершить задачу")],
        [KeyboardButton(text="🗑 Удалить задачу"), KeyboardButton(text="📋 Статус задач")],
        [KeyboardButton(text="🔄 Новый спринт")],
        [KeyboardButton(text="🧐 Итоги"), KeyboardButton(text="🎭 Планы")],
        [KeyboardButton(text="➕ Мини-задача"), KeyboardButton(text="✅ Выполнить мини-задачу")],
        [KeyboardButton(text="🧠 Муд-календарь")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ======================
# Муд-календарь
# ======================
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {
    "😎": "Я на коне",
    "🥴": "Непонятно",
    "🫨": "На тревоге",
    "😐": "Апатия",
    "☹️": "Грущу",
    "😭": "Очень грущу",
    "😌": "Спокойна",
    "😊": "Довольна",
    "😆": "Веселюсь",
    "🤢": "Переотдыхала",
    "😡": "Злюсь",
    "😱": "В шоке",
}

def mood_keyboard():
    rows = []
    row = []
    for idx, e in enumerate(MOOD_EMOJIS):
        row.append(InlineKeyboardButton(text=e, callback_data=f"mood_{idx}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ======================
# Хендлеры
# ======================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    print(f"[START] Called by user_id={message.from_user.id}")
    if not check_access(message.from_user.id):
        print("[START] Access denied")
        return await message.answer("У тебя нет доступа к этому боту.")
    await state.clear()
    print("[START] Access granted, state cleared")
    caption  = "Привет! 👋 Я — ваш agile-бот для душевных апгрейдов. Нажимай кнопки ниже и поехали!"
    img_path = BASE / "welcome.jpg"
    try:
        if img_path.exists():
            await bot.send_photo(message.chat.id, photo=FSInputFile(img_path), caption=caption, reply_markup=main_menu())
        else:
            await message.answer(caption, reply_markup=main_menu())
    except Exception:
        await message.answer(caption, reply_markup=main_menu())

# ----- Добавить задачу -----
@dp.message(F.text == "➕ Добавить задачу")
async def add_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Введи текст большой задачи:")
    await state.set_state(Form.add_task)

@dp.message(Form.add_task)
async def add_task_finish(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    sprint = get_sprint() or create_new_sprint()
    sprint.setdefault("tasks", [])
    sprint["tasks"].append({
        "text":       message.text.strip(),
        "done":       False,
        "created_at": datetime.now().isoformat(),
        "subtasks":   [],
    })
    set_sprint(sprint)
    await message.answer(f"Большая задача добавлена:\n👉 {message.text}", reply_markup=main_menu())
    await state.clear()

# ----- Удалить задачу -----
@dp.message(F.text == "🗑 Удалить задачу")
async def delete_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        return await message.answer("Нечего удалять.", reply_markup=main_menu())
    text = "Выберите номер задачи для удаления:\n"
    for i, t in enumerate(sprint["tasks"]):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state(Form.delete_task)

@dp.message(Form.delete_task)
async def delete_task_finish(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    sprint = get_sprint() or {}
    try:
        idx     = int(message.text.strip()) - 1
        removed = sprint["tasks"].pop(idx)
        set_sprint(sprint)
        await message.answer(f"Удалено: ❌ {removed['text']}", reply_markup=main_menu())
    except Exception:
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    await state.clear()

# ----- Новый спринт -----
@dp.message(F.text == "🔄 Новый спринт")
async def new_sprint_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Введите дату начала спринта в формате ДД.ММ.ГГГГ (или напиши 'сейчас'):")
    await state.set_state(Form.sprint_start_date)

@dp.message(Form.sprint_start_date)
async def new_sprint_start_date(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    date_str = message.text.strip()
    try:
        start = datetime.now().date() if date_str.lower() in ("сейчас", "now", "today", "") else datetime.strptime(date_str, "%d.%m.%Y").date()
        await state.update_data(start_date=start.isoformat())
        await message.answer("Введите дату окончания спринта в формате ДД.ММ.ГГГГ (или оставьте пустым для +3 недели):")
        await state.set_state(Form.sprint_end_date)
    except ValueError:
        await message.answer("Некорректный формат даты. Попробуйте ДД.ММ.ГГГГ")

@dp.message(Form.sprint_end_date)
async def new_sprint_end_date(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    data       = await state.get_data()
    start_date = datetime.fromisoformat(data["start_date"]).date()
    end_text   = message.text.strip()
    try:
        end_date = start_date + timedelta(weeks=3) if end_text.lower() in ("", "по умолчанию") else datetime.strptime(end_text, "%d.%m.%Y").date()
    except Exception:
        await message.answer("Некорректный формат даты. Попробуйте ДД.ММ.ГГГГ", reply_markup=main_menu())
        await state.clear()
        return
    if end_date < start_date:
        await message.answer("Дата окончания не может быть раньше начала.", reply_markup=main_menu())
        await state.clear()
        return
    create_new_sprint(
        name=f"Спринт {start_date.strftime('%d.%m.%Y')}",
        duration_days=(end_date - start_date).days,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    await message.answer(f"Спринт создан с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} ✅", reply_markup=main_menu())
    await state.clear()

# ----- Мини-задача: добавить -----
@dp.message(F.text == "➕ Мини-задача")
async def add_mini_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Введи текст мини-задачи на сегодня:")
    await state.set_state(Form.add_mini_task)

@dp.message(Form.add_mini_task)
async def add_mini_task_finish(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    try:
        text = message.text.strip()
        if not text:
            await message.answer("Текст не может быть пустым 😅")
            return
        mini_tasks = get_mini_tasks()
        mini_tasks.append({
            "text":       text,
            "done":       False,
            "created_at": datetime.now().isoformat(),
            "deadline":   (datetime.now() + timedelta(hours=12)).isoformat(),
        })
        set_mini_tasks(mini_tasks)
        await message.answer(f"Мини-задача добавлена:\n👉 {text}\n⏰ Дедлайн через 12 часов", reply_markup=main_menu())
    except Exception as e:
        print("Ошибка добавления мини-задачи:", e)
        await message.answer("Произошла ошибка 😅", reply_markup=main_menu())
    finally:
        await state.clear()

# ----- Мини-задача: выполнить -----
@dp.message(F.text == "✅ Выполнить мини-задачу")
async def complete_mini_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    mini_tasks = get_mini_tasks()
    choices    = [(i, t["text"]) for i, t in enumerate(mini_tasks) if not t["done"]]
    if not choices:
        return await message.answer("Нет мини-задач для выполнения.", reply_markup=main_menu())
    text = "Выберите мини-задачу для выполнения:\n"
    for idx, (_, t_text) in enumerate(choices):
        text += f"{idx + 1}. {t_text}\n"
    await state.update_data(choices=choices)
    await message.answer(text)
    await state.set_state(Form.complete_mini_task)

@dp.message(Form.complete_mini_task)
async def complete_mini_task_finish(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    data    = await state.get_data()
    choices = data.get("choices", [])
    try:
        index = int(message.text.strip()) - 1
        if index < 0 or index >= len(choices):
            raise ValueError("out of range")
        i, task_text = choices[index]
        mini_tasks   = get_mini_tasks()
        mini_tasks[i]["done"] = True
        set_mini_tasks(mini_tasks)

        stats = get_user_stats()
        uid   = str(message.from_user.id)
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["points"] += 1
        save_user_stats(stats)

        try:
            chat      = await bot.get_chat(message.from_user.id)
            username  = chat.username or chat.first_name or uid
            safe_text = task_text.replace(" ", "_").replace("\n", "_")[:40]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👍 Похвалить", callback_data=f"praise_{uid}_{safe_text}")]
            ])
            await bot.send_message(
                CHANNEL_ID,
                f"@{username} завершил мини-задачу: {task_text} ✅\n🏅 Баллы: {stats[uid]['points']}",
                reply_markup=kb,
            )
        except Exception as e:
            print("notify_mini_task_done error:", e)

        await message.answer(
            f"Мини-задача «{task_text}» выполнена! ✅\n🏅 Баллы: {stats[uid]['points']}",
            reply_markup=main_menu(),
        )
    except Exception as e:
        print("Ошибка при завершении мини-задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    finally:
        await state.clear()

# ----- Завершить задачу (большую) -----
@dp.message(F.text == "✅ Завершить задачу")
async def complete_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        return await message.answer("Нет задач для завершения 😅", reply_markup=main_menu())
    undone = [t for t in sprint["tasks"] if not t.get("done")]
    if not undone:
        return await message.answer("Все задачи уже завершены 🎉", reply_markup=main_menu())
    text = "Выберите номер незавершённой задачи:\n"
    for i, t in enumerate(undone):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state(Form.complete_task)

@dp.message(Form.complete_task)
async def complete_task_finish(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    sprint = get_sprint()
    undone = [t for t in sprint["tasks"] if not t.get("done")]
    try:
        index = int(message.text.strip()) - 1
        task  = undone[index]
        for original in sprint["tasks"]:
            if original["text"] == task["text"]:
                original["done"] = True
                break
        set_sprint(sprint)

        stats = get_user_stats()
        uid   = str(message.from_user.id)
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["points"] += 10
        save_user_stats(stats)

        try:
            chat      = await bot.get_chat(message.from_user.id)
            username  = chat.username or chat.first_name or uid
            safe_text = task["text"].replace(" ", "_").replace("\n", "_")[:40]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👍 Похвалить", callback_data=f"praise_{uid}_{safe_text}")]
            ])
            await bot.send_message(
                CHANNEL_ID,
                f"@{username} завершил задачу: {task['text']} ✅\n🏅 Баллы: {stats[uid]['points']}",
                reply_markup=kb,
            )
        except Exception as e:
            print("notify_task_done error:", e)

        await message.answer(
            f"Задача «{task['text']}» завершена! 🎉\n🏅 Очки: {stats[uid]['points']}",
            reply_markup=main_menu(),
        )
    except Exception as e:
        print("Ошибка при завершении задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    await state.clear()

# ----- Callback: похвала -----
@dp.callback_query(F.data.startswith("praise_"))
async def handle_praise(callback_query: CallbackQuery):
    try:
        parts     = callback_query.data.split("_", 2)
        user_id   = int(parts[1])
        task_text = parts[2].replace("_", " ") if len(parts) > 2 else "задачу"
        await callback_query.answer(f"Похвалено за «{task_text}»! 🎉")
        stats = get_user_stats()
        uid   = str(user_id)
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["points"] += 2
        save_user_stats(stats)
    except Exception as e:
        print("handle_praise error:", e)
        await callback_query.answer("Ошибка обработки похвалы.")

# ----- Итоги -----
@dp.message(F.text == "🧐 Итоги")
async def review_handler(message: Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint:
        return await message.answer("Нет данных для итогов 😅", reply_markup=main_menu())

    tasks        = sprint.get("tasks", [])
    total        = len(tasks)
    done         = sum(1 for t in tasks if t.get("done"))
    not_done     = total - done
    stats        = get_user_stats()
    points_total = sum(info.get("points", 0) for info in stats.values())

    moods_block = sprint.get("moods", {})
    mood_counts = {}
    for _uid, days in moods_block.items():
        for _d, emo in days.items():
            mood_counts[emo] = mood_counts.get(emo, 0) + 1

    start = sprint.get("start_date", "?")
    end   = sprint.get("end_date",   "?")
    text  = (
        f"🔍 *Итоги*\n"
        f"Спринт: {sprint.get('name', 'Спринт')}\n"
        f"Сроки: {start} — {end}\n\n"
        f"📌 Задач: {total}\nВыполнено: {done}\nОсталось: {not_done}\n\n"
        f"🏅 Баллы (всего): {points_total}\n\n"
        f"🧠 Настроение за спринт:\n"
    )
    if mood_counts:
        for emo, cnt in mood_counts.items():
            text += f"{emo} {MOOD_LABELS.get(emo, '')} — {cnt} дней\n"
    else:
        text += "Нет записей настроения.\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="Markdown")
    except Exception as e:
        print("Ошибка отправки итогов в канал:", e)

# ----- Планы -----
@dp.message(F.text == "🎭 Планы")
async def retro_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Напиши цель для следующего спринта:")
    await state.set_state(Form.set_new_goal)

@dp.message(Form.set_new_goal)
async def set_new_goal(message: Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        return await handle_menu_interrupt(message, state)
    sprint = get_sprint() or create_new_sprint()
    sprint["goal"] = message.text.strip()
    set_sprint(sprint)
    await message.answer(f"Цель сохранена: {sprint['goal']}", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, f"🎯 Новая цель спринта «{sprint.get('name', 'Спринт')}»:\n{sprint['goal']}")
    except Exception:
        pass
    await state.clear()

# ----- Статус задач -----
@dp.message(F.text == "📋 Статус задач")
async def status_tasks(message: Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint:
        return await message.answer("Спринт ещё не создан.", reply_markup=main_menu())
    tasks = sprint.get("tasks", [])
    if not tasks:
        return await message.answer("Задач пока нет!", reply_markup=main_menu())

    start       = sprint.get("start_date", "?")
    end         = sprint.get("end_date",   "?")
    status_text = f"📅 *Текущий спринт*\n{start} — {end}\n\n"
    for i, t in enumerate(tasks):
        mark         = "✅" if t.get("done") else "⏳"
        status_text += f"{i + 1}. {mark} {t.get('text')}\n"
        for j, sub in enumerate(t.get("subtasks", [])):
            s_mark       = "✅" if sub.get("done") else "⬜️"
            status_text += f"    {i + 1}.{j + 1} {s_mark} {sub.get('text')}\n"
        status_text += "\n"

    await message.answer(status_text, parse_mode="Markdown", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, status_text, parse_mode="Markdown")
    except Exception as e:
        print("Ошибка отправки статуса в канал:", e)

# ----- Муд-календарь -----
@dp.message(F.text == "🧠 Муд-календарь")
async def mood_menu(message: Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Как ты сегодня? Выбери эмоцию:", reply_markup=mood_keyboard())

@dp.callback_query(F.data.startswith("mood_"))
async def process_mood(callback_query: CallbackQuery):
    try:
        idx = int(callback_query.data.split("_", 1)[1])
        emo = MOOD_EMOJIS[idx] if 0 <= idx < len(MOOD_EMOJIS) else MOOD_EMOJIS[0]

        uid   = str(callback_query.from_user.id)
        today = str(datetime.now().date())

        stats = get_user_stats()
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["moods"][today] = emo
        save_user_stats(stats)

        sprint = get_sprint() or create_new_sprint()
        sprint.setdefault("moods", {})
        sprint["moods"].setdefault(uid, {})
        sprint["moods"][uid][today] = emo
        set_sprint(sprint)

        label = MOOD_LABELS.get(emo, "")
        await callback_query.answer(f"Записала настроение: {emo} — {label}")
        try:
            await bot.send_message(
                callback_query.from_user.id,
                f"Записала твоё настроение на {today}:\n{emo} — {label}",
                reply_markup=main_menu(),
            )
        except Exception:
            pass
        username = callback_query.from_user.username or callback_query.from_user.first_name or uid
        try:
            await bot.send_message(CHANNEL_ID, f"Настроение @{username}: {emo} — {label}")
        except Exception:
            pass
    except Exception as e:
        print("process_mood error:", e)
        await callback_query.answer("Ошибка при сохранении настроения.")

# ----- Отзывы (#отзыв) -----
@dp.message(F.text.contains("#отзыв"))
async def save_review(message: Message):
    try:
        reviews = read_json(REVIEWS_FILE, [])
        reviews.append({
            "user": message.from_user.username or message.from_user.first_name,
            "text": message.text,
            "date": datetime.now().isoformat(),
        })
        write_json(REVIEWS_FILE, reviews)
        if message.chat.type == "private":
            await message.answer("Спасибо! Отзыв сохранён. 🌟", reply_markup=main_menu())
    except Exception:
        pass

# ----- /restart -----
@dp.message(Command("restart"))
async def cmd_restart(message: Message):
    if not check_access(message.from_user.id):
        return await message.answer("У тебя нет прав на перезапуск.")
    await message.answer("🔄 Перезапуск бота...")
    await asyncio.sleep(1)
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await message.answer(f"Ошибка при restart: {e}")

# ======================
# Фоновые задачи
# ======================
async def send_daily_mood_msk():
    tz = pytz.timezone("Europe/Moscow")
    while True:
        try:
            now    = datetime.now(tz)
            target = tz.localize(datetime.combine(now.date(), time(21, 0, 0)))
            if now >= target:
                target = tz.localize(datetime.combine((now + timedelta(days=1)).date(), time(21, 0, 0)))
            while True:
                now          = datetime.now(tz)
                seconds_left = (target - now).total_seconds()
                if seconds_left <= 0:
                    break
                await asyncio.sleep(min(30, seconds_left))
            for uid in USER_IDS:
                try:
                    await bot.send_message(uid, "Как настроение сегодня?", reply_markup=mood_keyboard())
                except Exception as e:
                    print(f"send_daily_mood_msk error ({uid}):", e)
            await asyncio.sleep(65)
        except Exception as e:
            print("send_daily_mood_msk loop error:", e)
            await asyncio.sleep(60)

async def auto_press_invisible_button():
    while True:
        try:
            print("[auto_press] tick")
            await asyncio.sleep(1800)
        except Exception as e:
            print("auto_press error:", e)
            await asyncio.sleep(60)

# ======================
# AIOHTTP сервер + запуск бота
# ======================
async def health(request):
    return web.Response(text="Bot OK")

async def bot_background():
    """Фоновая задача: запускает бота после старта сервера"""
    try:
        print("[BOT] Cleaning webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("[BOT] Webhook deleted successfully")
        
        if not get_sprint():
            create_new_sprint()
        
        asyncio.create_task(auto_press_invisible_button())
        asyncio.create_task(send_horoscope(bot))
        asyncio.create_task(send_daily_mood_msk())
        
        print("[BOT] Starting polling...")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"[BOT] Polling error: {e}")
        await asyncio.sleep(60)

async def on_startup(app):
    """Хук aiohttp: вызывается ПОСЛЕ старта сервера"""
    print("[SERVER] on_startup called")
    asyncio.create_task(bot_background())

app = web.Application()
app.router.add_get('/', health)
app.router.add_get('/health', health)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[MAIN] Starting web server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)

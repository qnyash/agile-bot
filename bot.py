import os
import sys
import json
import asyncio
import random
from datetime import datetime, timedelta, time
from pathlib import Path

import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ======================
# КОНФИГУРАЦИЯ
# ======================
BASE_DIR = Path(__file__).parent
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003457894028"))
PORT = int(os.getenv("PORT", 8080))
ALLOWED_USERS = [466924747, 473956283]
USER_IDS = [466924747, 473956283]

# Файлы хранения
SPRINT_FILE = BASE_DIR / "sprint.json"
HISTORY_FILE = BASE_DIR / "history.json"
STATS_FILE = BASE_DIR / "stats.json"
MINI_TASKS_FILE = BASE_DIR / "mini_tasks.json"

# ======================
# ИНИЦИАЛИЗАЦИЯ
# ======================
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()

# ======================
# УТИЛИТЫ JSON
# ======================
def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[JSON ERROR] {path.name}: {e}")

def check_access(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# ======================
# СПРИНТ / СТАТИСТИКА / МИНИ-ЗАДАЧИ
# ======================
def get_sprint(): return load_json(SPRINT_FILE, None)
def set_sprint(data): save_json(SPRINT_FILE, data)

def get_stats(): return load_json(STATS_FILE, {})
def save_stats(data): save_json(STATS_FILE, data)

def get_mini_tasks(): return load_json(MINI_TASKS_FILE, [])
def save_mini_tasks(data): save_json(MINI_TASKS_FILE, data)

def create_sprint(name=None, start=None, end=None):
    old = get_sprint()
    if old:
        hist = load_json(HISTORY_FILE, [])
        hist.append({**old, "finished_at": datetime.now().isoformat()})
        save_json(HISTORY_FILE, hist)

    s_date = start or datetime.now().date().isoformat()
    e_date = end or (datetime.fromisoformat(s_date) + timedelta(weeks=3)).date().isoformat()
    new_sprint = {
        "name": name or f"Спринт {datetime.now().strftime('%d.%m.%Y')}",
        "tasks": [],
        "goal": "",
        "start_date": s_date,
        "end_date": e_date,
        "moods": {}
    }
    set_sprint(new_sprint)
    return new_sprint

# ======================
# КЛАВИАТУРЫ
# ======================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить задачу", "✅ Завершить задачу")
    kb.add("🗑 Удалить задачу", "📋 Статус задач")
    kb.add("🔄 Новый спринт")
    kb.add("🧐 Итоги", "🎭 Планы")
    kb.add("➕ Мини-задача", "✅ Выполнить мини-задачу")
    kb.add("🧠 Муд-календарь")
    return kb

MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {
    "😎":"Я на коне","🥴":"Непонятно","🫨":"На тревоге","😐":"Апатия",
    "☹️":"Грущу","😭":"Очень грущу","😌":"Спокойна","😊":"Довольна",
    "😆":"Веселюсь","🤢":"Переотдыхала","😡":"Злюсь","😱":"В шоке"
}

def mood_kb():
    kb = InlineKeyboardMarkup(row_width=4)
    for i, e in enumerate(MOOD_EMOJIS):
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{i}"))
    return kb

# ======================
# ГОРОСКОП (без ИИ, только списки)
# ======================
USER_SIGNS = {466924747: "Телец", 473956283: "Козерог"}
HOROSCOPE_PHRASES = {
    "Телец": [
        "Энергия скачет как Wi-Fi: то огонь, то пропадает. Нормально 😎",
        "Ты сегодня огонь. Главное не обжечься 🫠",
        "Мысли прыгают? Мозг просто разгоняется 🚀",
        "Начни 5 дел, закончи одно. Победа 🏆",
        "Звёзды: замедлись. Ты: не-а ⚡️",
        "Не можешь выбрать? Ткни пальцем. Работает 🤌",
        "Внимание живёт своей жизнью. Наблюдай 👀",
        "Великие дела или великий хаос. Оба норм 😂",
        "Всё получится, даже если забыл план 🤷‍♂️",
        "Не бросай в первые 10 мин. Ты герой 💪"
    ],
    "Козерог": [
        "Всё решаемо, даже если тревожишься заранее 😅💭",
        "Ты сильнее страхов. Они просто громкие 😵‍💫⏰",
        "Тревога стучит? Скажи: я занята 💅✨",
        "Спокойствие хромает? Мы подержим 🫶",
        "Попереживай 5 минут. Потом дела 📚",
        "Звёзды: ты справишься. Без вариантов 🌟",
        "Умная и тревожная. Идеальный микс 🍸😄",
        "Ты танк. Мягкий, но танк 🛡️✨",
        "Видишь риски? Обойди их 🧠➡️",
        "Минимум поводов для паники. Ты вывезешь 🤍"
    ]
}

def get_horoscope(sign: str) -> str:
    return random.choice(HOROSCOPE_PHRASES.get(sign, ["Всё будет ок 🔥"]))

# ======================
# ХЕНДЛЕРЫ
# ======================
@dp.message_handler(commands=["start"])
async def cmd_start(m: types.Message):
    if not check_access(m.from_user.id):
        return await m.answer("Нет доступа к боту.")
    await m.answer("Привет! 👋 Agile-бот для душевных апгрейдов готов. Жми кнопки!", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "➕ Добавить задачу")
async def add_task_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    await m.answer("Введи текст большой задачи:")
    await state.set_state("wait_task_text")

@dp.message_handler(state="wait_task_text")
async def add_task_finish(m: types.Message, state: FSMContext):
    sp = get_sprint() or create_sprint()
    sp["tasks"].append({"text": m.text.strip(), "done": False, "created_at": datetime.now().isoformat(), "subtasks": []})
    set_sprint(sp)
    await m.answer(f"✅ Задача добавлена:\n👉 {m.text}", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "🗑 Удалить задачу")
async def del_task_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    sp = get_sprint()
    if not sp or not sp["tasks"]:
        return await m.answer("Задач нет.", reply_markup=main_menu())
    txt = "Номер задачи для удаления:\n" + "\n".join(f"{i+1}. {t['text']}" for i,t in enumerate(sp["tasks"]))
    await m.answer(txt)
    await state.set_state("wait_del_idx")

@dp.message_handler(state="wait_del_idx")
async def del_task_finish(m: types.Message, state: FSMContext):
    sp = get_sprint() or {}
    try:
        idx = int(m.text.strip()) - 1
        removed = sp["tasks"].pop(idx)
        set_sprint(sp)
        await m.answer(f"❌ Удалено: {removed['text']}", reply_markup=main_menu())
    except Exception:
        await m.answer("Неверный номер 😅", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "✅ Завершить задачу")
async def comp_task_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    sp = get_sprint()
    if not sp or not sp["tasks"]:
        return await m.answer("Задач нет 😅", reply_markup=main_menu())
    undone = [t for t in sp["tasks"] if not t["done"]]
    if not undone:
        return await m.answer("Все задачи выполнены 🎉", reply_markup=main_menu())
    await m.answer("Номер задачи для завершения:\n" + "\n".join(f"{i+1}. {t['text']}" for i,t in enumerate(undone)))
    await state.set_state("wait_comp_idx")

@dp.message_handler(state="wait_comp_idx")
async def comp_task_finish(m: types.Message, state: FSMContext):
    sp = get_sprint()
    undone = [t for t in sp["tasks"] if not t["done"]]
    try:
        idx = int(m.text.strip()) - 1
        task = undone[idx]
        for t in sp["tasks"]:
            if t["text"] == task["text"]:
                t["done"] = True
                break
        set_sprint(sp)
        st = get_stats()
        uid = str(m.from_user.id)
        st.setdefault(uid, {"points": 0, "moods": {}})
        st[uid]["points"] += 10
        save_stats(st)
        await m.answer(f"🎉 Задача «{task['text']}» завершена!\n🏅 Очки: {st[uid]['points']}", reply_markup=main_menu())
    except Exception:
        await m.answer("Неверный номер 😅", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "📋 Статус задач")
async def status_tasks(m: types.Message):
    if not check_access(m.from_user.id): return
    sp = get_sprint()
    if not sp or not sp["tasks"]:
        return await m.answer("Спринт пуст.", reply_markup=main_menu())
    txt = f"📅 *{sp['name']}*\n{sp['start_date']} — {sp['end_date']}\n\n"
    for i, t in enumerate(sp["tasks"]):
        mark = "✅" if t["done"] else "⏳"
        txt += f"{i+1}. {mark} {t['text']}\n"
    await m.answer(txt, parse_mode="Markdown", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "🔄 Новый спринт")
async def new_sprint_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    await m.answer("Дата начала (ДД.ММ.ГГГГ или 'сейчас'):")
    await state.set_state(SprintStates.start_date)

@dp.message_handler(state=SprintStates.start_date)
async def new_sprint_date1(m: types.Message, state: FSMContext):
    txt = m.text.strip().lower()
    try:
        start = datetime.now().date() if txt in ("сейчас","now","") else datetime.strptime(m.text.strip(), "%d.%m.%Y").date()
        await state.update_data(start=start.isoformat())
        await m.answer("Дата окончания (ДД.ММ.ГГГГ или пусто для +3 недель):")
        await state.set_state(SprintStates.end_date)
    except ValueError:
        await m.answer("Формат: ДД.ММ.ГГГГ")

@dp.message_handler(state=SprintStates.end_date)
async def new_sprint_date2(m: types.Message, state: FSMContext):
    data = await state.get_data()
    start = datetime.fromisoformat(data["start"]).date()
    txt = m.text.strip()
    try:
        end = start + timedelta(weeks=3) if txt == "" else datetime.strptime(txt, "%d.%m.%Y").date()
        if end < start:
            return await m.answer("Конец раньше начала ❌", reply_markup=main_menu())
        create_sprint(start=start.isoformat(), end=end.isoformat())
        await m.answer(f"✅ Спринт создан: {start.strftime('%d.%m')} — {end.strftime('%d.%m')}", reply_markup=main_menu())
    except ValueError:
        await m.answer("Формат: ДД.ММ.ГГГГ", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "➕ Мини-задача")
async def add_mini_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    await m.answer("Текст мини-задачи на сегодня:")
    await state.set_state("wait_mini_text")

@dp.message_handler(state="wait_mini_text")
async def add_mini_finish(m: types.Message, state: FSMContext):
    mt = get_mini_tasks()
    mt.append({"text": m.text.strip(), "done": False, "created_at": datetime.now().isoformat()})
    save_mini_tasks(mt)
    await m.answer(f"⏱ Мини-задача добавлена: {m.text}", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "✅ Выполнить мини-задачу")
async def comp_mini_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    mt = get_mini_tasks()
    active = [(i, t["text"]) for i, t in enumerate(mt) if not t["done"]]
    if not active:
        return await m.answer("Нет активных мини-задач.", reply_markup=main_menu())
    await state.update_data(active=active)
    await m.answer("Номер мини-задачи:\n" + "\n".join(f"{i+1}. {t}" for i,(_,t) in enumerate(active)))
    await state.set_state("wait_mini_comp")

@dp.message_handler(state="wait_mini_comp")
async def comp_mini_finish(m: types.Message, state: FSMContext):
    data = await state.get_data()
    active = data.get("active", [])
    try:
        idx = int(m.text.strip()) - 1
        orig_idx, txt = active[idx]
        mt = get_mini_tasks()
        mt[orig_idx]["done"] = True
        save_mini_tasks(mt)
        st = get_stats()
        uid = str(m.from_user.id)
        st.setdefault(uid, {"points": 0, "moods": {}})
        st[uid]["points"] += 1
        save_stats(st)
        await m.answer(f"✅ Мини-задача «{txt}» выполнена!\n🏅 Баллы: {st[uid]['points']}", reply_markup=main_menu())
    except Exception:
        await m.answer("Неверный номер 😅", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "🧐 Итоги")
async def show_results(m: types.Message):
    if not check_access(m.from_user.id): return
    sp = get_sprint()
    if not sp:
        return await m.answer("Нет данных.", reply_markup=main_menu())
    tasks = sp.get("tasks", [])
    done = sum(1 for t in tasks if t["done"])
    st = get_stats()
    pts = sum(v.get("points", 0) for v in st.values())
    moods = sp.get("moods", {})
    mc = {}
    for u_days in moods.values():
        for emo in u_days.values():
            mc[emo] = mc.get(emo, 0) + 1
    txt = f"🔍 *Итоги*\n{sp['name']}\n{sp['start_date']} — {sp['end_date']}\n\n"
    txt += f"📌 Задач: {len(tasks)}\n✅ Выполнено: {done}\n⏳ Осталось: {len(tasks)-done}\n"
    txt += f"🏅 Баллы: {pts}\n\n🧠 Настроение:\n"
    txt += "\n".join(f"{e} {MOOD_LABELS.get(e,'')} — {c} дн." for e,c in mc.items()) if mc else "Нет записей"
    await m.answer(txt, parse_mode="Markdown", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "🎭 Планы")
async def plans_start(m: types.Message, state: FSMContext):
    if not check_access(m.from_user.id): return
    await m.answer("Цель на следующий спринт:")
    await state.set_state("wait_goal")

@dp.message_handler(state="wait_goal")
async def plans_finish(m: types.Message, state: FSMContext):
    sp = get_sprint() or create_sprint()
    sp["goal"] = m.text.strip()
    set_sprint(sp)
    await m.answer(f"🎯 Цель сохранена: {sp['goal']}", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "🧠 Муд-календарь")
async def mood_menu(m: types.Message):
    if not check_access(m.from_user.id): return
    await m.answer("Как ты сегодня?", reply_markup=mood_kb())

@dp.callback_query_handler(lambda c: c.data.startswith("mood_"))
async def process_mood(cq: types.CallbackQuery):
    idx = int(cq.data.split("_")[1])
    emo = MOOD_EMOJIS[idx] if 0 <= idx < len(MOOD_EMOJIS) else MOOD_EMOJIS[0]
    uid = str(cq.from_user.id)
    today = datetime.now().date().isoformat()
    
    st = get_stats()
    st.setdefault(uid, {"points": 0, "moods": {}})
    st[uid]["moods"][today] = emo
    save_stats(st)
    
    sp = get_sprint() or create_sprint()
    sp.setdefault("moods", {})
    sp["moods"].setdefault(uid, {})
    sp["moods"][uid][today] = emo
    set_sprint(sp)
    
    await cq.answer(f"Записано: {emo} {MOOD_LABELS.get(emo,'')}")
    await bot.send_message(cq.from_user.id, f"📅 Настроение на {today}: {emo}", reply_markup=main_menu())

@dp.message_handler(commands=["restart"])
async def cmd_restart(m: types.Message):
    if not check_access(m.from_user.id): return
    await m.answer("🔄 Перезапуск...")
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ======================
# ФОНОВЫЕ ЗАДАЧИ
# ======================
async def daily_horoscope():
    tz = pytz.timezone("Europe/Moscow")
    while True:
        try:
            now = datetime.now(tz)
            target = tz.localize(datetime.combine(now.date(), time(9, 0)))
            if now >= target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            for uid, sign in USER_SIGNS.items():
                try:
                    await bot.send_message(CHANNEL_ID, f"🔮 Гороскоп для {sign}:\n{get_horoscope(sign)}")
                except Exception as e:
                    print(f"[HOROSCOPE] {e}")
            await asyncio.sleep(70)
        except Exception as e:
            print(f"[HOROSCOPE LOOP] {e}")
            await asyncio.sleep(60)

async def daily_mood_prompt():
    tz = pytz.timezone("Europe/Moscow")
    while True:
        try:
            now = datetime.now(tz)
            target = tz.localize(datetime.combine(now.date(), time(21, 0)))
            if now >= target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            for uid in USER_IDS:
                try:
                    await bot.send_message(uid, "🌙 Как настроение сегодня?", reply_markup=mood_kb())
                except Exception as e:
                    print(f"[MOOD PROMPT] {e}")
            await asyncio.sleep(70)
        except Exception as e:
            print(f"[MOOD LOOP] {e}")
            await asyncio.sleep(60)

# ======================
# WEB-SERVER ДЛЯ RENDER
# ======================
async def healthcheck(request):
    return web.Response(text="OK", status=200)

async def run_web():
    app = web.Application()
    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"✅ Healthcheck server running on port {PORT}")

# ======================
# ЗАПУСК
# ======================
async def on_startup(dp_):
    if not get_sprint():
        create_sprint()
    asyncio.create_task(run_web())
    asyncio.create_task(daily_horoscope())
    asyncio.create_task(daily_mood_prompt())
    print("🚀 Bot started successfully")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        sys.exit(1)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

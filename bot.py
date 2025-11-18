# bot.py — aiogram 3.x version (ready for Render)
import os
import sys
import json
import asyncio
import random
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.filters import Text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery

# ----------------------
# Config
# ----------------------
ALLOWED_USERS = [466924747, 473956283]   # изменить при необходимости
USER_IDS = [466924747, 473956283]        # кому рассылать ежедневный опрос (id в int)
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003457894028"))

# Token: предпочтительно задавать в ENV var TOKEN
import os
TOKEN = os.environ.get("TOKEN")

BASE = Path(".")
SPRINT_FILE = BASE / "sprint.json"
HISTORY_FILE = BASE / "history.json"
STATS_FILE = BASE / "stats.json"
REVIEWS_FILE = BASE / "reviews.json"

# ----------------------
# Init bot & dispatcher
# ----------------------
bot: Bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ----------------------
# States
# ----------------------
class SprintStates(StatesGroup):
    start_date = State()
    end_date = State()

# ----------------------
# Utils: read/write json
# ----------------------
def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ----------------------
# Sprint / stats helpers
# ----------------------
def check_access(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

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

def praise_message(task_text):
    options = [
        f"🔥 Работа сделана! '{task_text}' закрыта.",
        f"💪 Жёстко! '{task_text}' больше не висит.",
        f"✨ Красиво. '{task_text}' — готово.",
        f"🎯 В цель! '{task_text}' улетела в выполненные.",
        f"🌱 +1 шаг вперёд. '{task_text}' завершена.",
    ]
    return random.choice(options)

# ----------------------
# Keyboards
# ----------------------
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("➕ Добавить задачу"), KeyboardButton("✅ Завершить задачу"))
    kb.add(KeyboardButton("🗑 Удалить задачу"), KeyboardButton("📋 Статус задач"))
    kb.add(KeyboardButton("🔄 Новый спринт"))
    kb.add(KeyboardButton("🧐 Ревью"), KeyboardButton("🎭 Ретро"))
    kb.add(KeyboardButton("➕ Мини-задача"), KeyboardButton("✅ Выполнить мини-задачу"))
    kb.add(KeyboardButton("🧠 Муд-календарь"))
    return kb

def mood_keyboard():
    emojis = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
    kb = InlineKeyboardMarkup(row_width=3)
    for e in emojis:
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{ord(e)}"))
    return kb

# ----------------------
# Handlers
# ----------------------
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    if not check_access(message.from_user.id):
        await message.answer("У тебя нет доступа к этому боту.")
        return
    caption = "Привет! 👋 Я - ваш agile-бот для душевных апгрейдов. Нажимай кнопки ниже и поехали!"
    await message.answer(caption, reply_markup=main_menu())

# Add task
@dp.message(Text(text="➕ Добавить задачу"))
async def add_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Введи текст большой задачи:")
    await state.set_state("add_task")

@dp.message(F.state == "add_task")
async def add_task_finish(message: Message, state: FSMContext):
    sprint = get_sprint() or create_new_sprint()
    sprint.setdefault("tasks", [])
    sprint["tasks"].append({
        "text": message.text.strip(),
        "done": False,
        "created_at": datetime.now().isoformat(),
        "subtasks": []
    })
    set_sprint(sprint)
    await message.answer(f"Большая задача добавлена:\n👉 {message.text}", reply_markup=main_menu())
    await state.clear()

# Delete task
@dp.message(Text(text="🗑 Удалить задачу"))
async def delete_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        await message.answer("Нечего удалять.", reply_markup=main_menu())
        return
    text = "Выберите номер задачи для удаления:\n"
    for i, t in enumerate(sprint["tasks"]):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state("delete_task")

@dp.message(F.state == "delete_task")
async def delete_task_finish(message: Message, state: FSMContext):
    sprint = get_sprint() or {}
    try:
        idx = int(message.text.strip()) - 1
        removed = sprint["tasks"].pop(idx)
        set_sprint(sprint)
        await message.answer(f"Удалено: ❌ {removed['text']}", reply_markup=main_menu())
    except Exception:
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    await state.clear()

# New sprint dates
@dp.message(Text(text="🔄 Новый спринт"))
async def new_sprint_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Введите дату начала спринта в формате ДД.MM.YYYY (или 'сейчас'):")
    await state.set_state(SprintStates.start_date)

@dp.message(F.state == SprintStates.start_date)
async def new_sprint_start_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    try:
        if date_str.lower() in ("сейчас", "now", "today", ""):
            start = datetime.now().date()
        else:
            start = datetime.strptime(date_str, "%d.%m.%Y").date()
        await state.update_data(start_date=start.isoformat())
        await message.answer("Введите дату окончания спринта в формате ДД.MM.YYYY (или оставьте пустым для +3 недели):")
        await state.set_state(SprintStates.end_date)
    except ValueError:
        await message.answer("Некорректный формат даты. Попробуйте ДД.MM.YYYY")

@dp.message(F.state == SprintStates.end_date)
async def new_sprint_end_date(message: Message, state: FSMContext):
    data = await state.get_data()
    start_str = data.get("start_date")
    end_text = message.text.strip()
    try:
        start_date = datetime.fromisoformat(start_str).date()
        if end_text == "" or end_text.lower() in ("", "по умолчанию"):
            end_date = start_date + timedelta(weeks=3)
        else:
            end_date = datetime.strptime(end_text, "%d.%m.%Y").date()
    except Exception:
        await message.answer("Некорректный формат даты. Попробуйте ДД.MM.YYYY", reply_markup=main_menu())
        await state.clear()
        return

    if end_date < start_date:
        await message.answer("Дата окончания не может быть раньше начала. Попробуйте снова.", reply_markup=main_menu())
        await state.clear()
        return

    create_new_sprint(name=f"Спринт {start_date.strftime('%d.%m.%Y')}",
                      duration_days=(end_date - start_date).days,
                      start_date=start_date.isoformat(),
                      end_date=end_date.isoformat())

    await message.answer(f"Спринт создан с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} ✅", reply_markup=main_menu())
    await state.clear()

# Add subtask
@dp.message(Text(text="➕ Мини-задача"))
async def add_subtask_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        await message.answer("Сначала добавь большую задачу.", reply_markup=main_menu())
        return

    text = "Выберите номер большой задачи для добавления мини-задачи:\n"
    for i, t in enumerate(sprint["tasks"]):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state("choose_task_for_subtask")

@dp.message(F.state == "choose_task_for_subtask")
async def add_subtask_choose_task(message: Message, state: FSMContext):
    try:
        index = int(message.text.strip()) - 1
        sprint = get_sprint()
        if index < 0 or index >= len(sprint.get("tasks", [])):
            raise ValueError("Номер вне диапазона")
        await state.update_data(task_index=index)
        await message.answer("Введи текст мини-задачи:")
        await state.set_state("add_subtask")
    except Exception as e:
        print("Ошибка выбора большой задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
        await state.clear()

@dp.message(F.state == "add_subtask")
async def add_subtask_finish(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        index = data.get("task_index")
        sprint = get_sprint() or create_new_sprint()

        if index is None or index < 0 or index >= len(sprint.get("tasks", [])):
            raise ValueError("Задача не найдена")

        sprint["tasks"][index].setdefault("subtasks", [])

        subtask_text = message.text.strip()
        deadline = (datetime.now() + timedelta(hours=12)).isoformat()

        sprint["tasks"][index]["subtasks"].append({
            "text": subtask_text,
            "done": False,
            "points": 1,
            "created_at": datetime.now().isoformat(),
            "deadline": deadline
        })
        set_sprint(sprint)

        await message.answer(
            f"Мини-задача добавлена под '{sprint['tasks'][index]['text']}':\n👉 {subtask_text}\n⏰ Дедлайн через 12 часов",
            reply_markup=main_menu()
        )
    except Exception as e:
        print("Ошибка при добавлении мини-задачи:", e)
        await message.answer("Произошла ошибка при добавлении мини-задачи 😅", reply_markup=main_menu())
    finally:
        await state.clear()

# Complete subtask
@dp.message(Text(text="✅ Выполнить мини-задачу"))
async def complete_subtask_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    sprint = get_sprint()
    choices = []
    if sprint:
        for i, task in enumerate(sprint.get("tasks", [])):
            for j, sub in enumerate(task.get("subtasks", [])):
                if not sub.get("done"):
                    choices.append((i, j, sub.get("text"), task.get("text")))
    if not choices:
        await message.answer("Нет мини-задач для выполнения.", reply_markup=main_menu())
        return

    text = "Выберите мини-задачу для выполнения:\n"
    for idx, (i, j, sub_text, task_text) in enumerate(choices):
        text += f"{idx + 1}. [{task_text}] {sub_text}\n"
    await state.update_data(choices=choices)
    await message.answer(text)
    await state.set_state("complete_subtask")

@dp.message(F.state == "complete_subtask")
async def complete_subtask_finish(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        choices = data.get("choices", [])
        index = int(message.text.strip()) - 1
        i, j, sub_text, task_text = choices[index]
        sprint = get_sprint()
        sprint["tasks"][i]["subtasks"][j]["done"] = True
        set_sprint(sprint)

        stats = get_user_stats()
        uid = str(message.from_user.id)
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["points"] += 1
        save_user_stats(stats)

        await message.answer(f"Мини-задача '{sub_text}' выполнена! ✅\n🏅 Баллы: {stats[uid]['points']}", reply_markup=main_menu())
    except Exception as e:
        print("Ошибка при завершении мини-задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    finally:
        await state.clear()

# Complete big task
@dp.message(Text(text="✅ Завершить задачу"))
async def complete_task_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        await message.answer("Нет задач для завершения 😅", reply_markup=main_menu())
        return

    undone = [t for t in sprint.get("tasks", []) if not t.get("done")]
    if not undone:
        await message.answer("Все задачи уже завершены 🎉", reply_markup=main_menu())
        return

    text = "Выберите номер незавершённой задачи:\n"
    for i, t in enumerate(undone):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state("complete_task")

@dp.message(F.state == "complete_task")
async def complete_task_finish(message: Message, state: FSMContext):
    sprint = get_sprint()
    undone = [t for t in sprint.get("tasks", []) if not t.get("done")]
    try:
        index = int(message.text.strip()) - 1
        task = undone[index]
        for original in sprint["tasks"]:
            if original["text"] == task["text"]:
                original["done"] = True
                break
        set_sprint(sprint)

        stats = get_user_stats()
        uid = str(message.from_user.id)
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["points"] += 10
        save_user_stats(stats)

        await notify_task_done(message.from_user.id, task["text"], stats[uid]["points"])
        await message.answer(f"Задача '{task['text']}' завершена! 🎉\n🏅 Очки: {stats[uid]['points']}", reply_markup=main_menu())
    except Exception as e:
        print("Ошибка при завершении большой задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    await state.clear()

# Notify channel + praise callback
async def notify_task_done(user_id: int, task_text: str, points: int):
    try:
        chat = await bot.get_chat(user_id)
        username = chat.username or chat.first_name or str(user_id)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("👍 Похвалить", callback_data=f"praise_{user_id}_{task_text}"))
        await bot.send_message(CHANNEL_ID, f"Пользователь @{username} завершил задачу: {task_text} ✅\n🏅 Баллы: {points}", reply_markup=kb)
    except Exception as e:
        print("notify_task_done error:", e)

@dp.callback_query(F.data and F.data.startswith("praise_"))
async def handle_praise(callback: CallbackQuery):
    try:
        parts = callback.data.split("_", 2)
        user_id = int(parts[1])
        task_text = parts[2]
        await callback.answer(f"Похвалено за '{task_text}'! 🎉")
        stats = get_user_stats()
        uid = str(user_id)
        if uid not in stats:
            stats[uid] = {"points": 0, "moods": {}}
        stats[uid]["points"] += 2
        save_user_stats(stats)
    except Exception:
        await callback.answer("Ошибка обработки похвалы.")

# Review
@dp.message(Text(contains="статус") | Text(text="🧐 Ревью") | Text(contains="ревью"))
async def review_handler(message: Message):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    sprint = get_sprint()
    if not sprint:
        await message.answer("Нет данных для ревью 😅", reply_markup=main_menu())
        return

    tasks = sprint.get("tasks", [])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))
    not_done = total - done

    stats = get_user_stats()
    points_total = sum(info.get("points", 0) for info in stats.values())

    moods_block = sprint.get("moods", {})
    mood_counts = {}
    for uid, days in moods_block.items():
        for d, emo in days.items():
            mood_counts[emo] = mood_counts.get(emo, 0) + 1

    start = sprint.get("start_date", "?")
    end = sprint.get("end_date", "?")
    text_user = f"🔍 *Ревью*\nСпринт: {sprint.get('name','Спринт')}\nСроки: {start} — {end}\n\n"
    text_user += f"📌 Задач: {total}\nВыполнено: {done}\nОсталось: {not_done}\n\n"
    text_user += f"🏅 Баллы (всего): {points_total}\n\n"
    text_user += "🧠 Настроение за спринт:\n"
    if mood_counts:
        for emo, cnt in mood_counts.items():
            text_user += f"{emo} — {cnt} дней\n"
    else:
        text_user += "Нет записей настроения.\n"

    await message.answer(text_user, parse_mode="Markdown", reply_markup=main_menu())

    try:
        await bot.send_message(CHANNEL_ID, text_user, parse_mode="Markdown")
    except Exception as e:
        print("Ошибка отправки ревью в канал:", e)

# Retro (set new goal)
@dp.message(Text(text="🎭 Ретро"))
async def retro_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Напиши цель для следующего спринта:")
    await state.set_state("set_new_goal")

@dp.message(F.state == "set_new_goal")
async def set_new_goal(message: Message, state: FSMContext):
    sprint = get_sprint() or create_new_sprint()
    sprint["goal"] = message.text.strip()
    set_sprint(sprint)
    await message.answer(f"Цель сохранена: {sprint['goal']}", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, f"🎯 Новая цель спринта '{sprint.get('name','Спринт')}':\n{ sprint['goal'] }")
    except Exception:
        pass
    await state.clear()

# Status tasks
@dp.message(Text(contains="Статус") | Text(contains="статус") | Text(text="📋 Статус задач"))
async def status_tasks(message: Message):
    sprint = get_sprint()
    if not sprint:
        await message.answer("Спринт ещё не создан.", reply_markup=main_menu())
        return

    tasks = sprint.get("tasks", [])
    if not tasks:
        await message.answer("Задач пока нет!", reply_markup=main_menu())
        return

    start = sprint.get("start_date")
    end = sprint.get("end_date")
    status_text = f"📅 *Текущий спринт*\n{start} — {end}\n\n"
    for i, t in enumerate(tasks):
        mark = "✅" if t.get("done") else "⏳"
        status_text += f"{i+1}. {mark} {t.get('text')}\n"
        for j, sub in enumerate(t.get("subtasks", [])):
            s_mark = "✅" if sub.get("done") else "⬜️"
            status_text += f"    {i+1}.{j+1} {s_mark} {sub.get('text')}\n"
        status_text += "\n"

    await message.answer(status_text, parse_mode="Markdown", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, status_text, parse_mode="Markdown")
    except Exception as e:
        print("Ошибка отправки статуса в канал:", e)

# Mood calendar
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {
    "😎":"Я на коне","🥴":"Непонятно","🫨":"На тревоге","😐":"Апатия","☹️":"Грущу","😭":"Очень грущу",
    "😌":"Спокоен","😊":"Довольный","😆":"Веселюсь","🤢":"Переотдыхал","😡":"Злюсь","😱":"В шоке"
}

@dp.message(Text(text="🧠 Муд-календарь"))
async def mood_menu(message: Message):
    if not check_access(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Как ты сегодня? Выбери эмоцию:", reply_markup=mood_keyboard())

@dp.callback_query(F.data and F.data.startswith("mood_"))
async def process_mood(callback: CallbackQuery):
    try:
        code = callback.data.split("_",1)[1]
        try:
            emo = chr(int(code))
        except Exception:
            emo = "🙂"
        if emo not in MOOD_EMOJIS:
            emo = MOOD_EMOJIS[0]

        stats = get_user_stats()
        uid = str(callback.from_user.id)
        today = str(datetime.now().date())
        stats.setdefault(uid, {"points":0, "moods":{}})
        stats[uid]["moods"][today] = emo
        save_user_stats(stats)

        sprint = get_sprint() or create_new_sprint()
        sprint.setdefault("moods", {})
        sprint["moods"].setdefault(uid, {})
        sprint["moods"][uid][today] = emo
        set_sprint(sprint)

        await callback.answer(f"Записала настроение: {emo} — {MOOD_LABELS.get(emo,'')}")
        try:
            await bot.send_message(callback.from_user.id, f"Записала твоё настроение на {today}: {emo} — {MOOD_LABELS.get(emo,'')}", reply_markup=main_menu())
        except Exception:
            pass
        # Post to channel
        try:
            await bot.send_message(CHANNEL_ID, f"Настроение @{callback.from_user.username}: {emo}")
        except Exception:
            pass
    except Exception as e:
        print("process_mood error:", e)
        await callback.answer("Ошибка при сохранении настроения.")

# Reviews from channel #отзыв
@dp.message(F.text and F.text.lower().contains("#отзыв"))
async def save_review(message: Message):
    try:
        reviews = read_json(REVIEWS_FILE, [])
        reviews.append({
            "user": message.from_user.username or message.from_user.first_name,
            "text": message.text,
            "date": datetime.now().isoformat()
        })
        write_json(REVIEWS_FILE, reviews)
        if message.chat.type == "private":
            await message.answer("Спасибо! Отзыв сохранён. 🌟", reply_markup=main_menu())
    except Exception:
        pass

# Restart (soft) - re-create bot session and replace global bot reference
@dp.message(Text(text="/restart"))
async def cmd_restart(message: Message):
    if not check_access(message.from_user.id):
        await message.answer("У тебя нет прав на перезапуск.")
        return
    await message.answer("🔄 Перезапуск бота (мягкий)...")
    await asyncio.sleep(1)
    try:
        # close old session
        try:
            await bot.session.close()
        except Exception:
            pass
        # re-create bot object
        new_token = os.environ.get("TOKEN") or TOKEN
        globals()['bot'] = Bot(token=new_token)  # update global
        await message.answer("✅ Бот переподключён.", reply_markup=main_menu())
    except Exception as e:
        await message.answer(f"Ошибка при restart: {e}")

# Daily mood sender (20:00 Moscow)
async def send_daily_mood_loop():
    tz = ZoneInfo("Europe/Moscow")
    while True:
        now = datetime.now(tz)
        target_time = datetime.combine(now.date(), time(hour=20, minute=0, second=0), tz)
        if now >= target_time:
            target_time = target_time + timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        for uid in USER_IDS:
            try:
                await bot.send_message(uid, "Как настроение сегодня? Выбери эмоцию:", reply_markup=mood_keyboard())
            except Exception:
                pass
        # small sleep to avoid double-run in same minute
        await asyncio.sleep(5)

# Background tasks (start on startup)
async def on_startup():
    if not get_sprint():
        create_new_sprint()
    # start background loop
    asyncio.create_task(send_daily_mood_loop())

# ----------------------
# Start polling
# ----------------------
async def main():
    await on_startup()
    print("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")

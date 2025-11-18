# bot.py — Полный рабочий бот: задачи, мини-задачи, муд-календарь, ревью с эмоциональной статистикой, /restart
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# timezone helper (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # fallback will use fixed offset

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

# ======================
# Настройки (поменяй токен/канал при необходимости)
# ======================
ALLOWED_USERS = [466924747, 473956283]   # сюда твои ID
USER_IDS = [466924747, 473956283]        # кому слать ежедневные оповещения (можно оставить тех же)
TOKEN = "8155844970:AAHS8dWJmDeFVfOgPscCEQdHqFrbGSG3Mss"
CHANNEL_ID = -1003457894028               # ID канала

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
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        # на случай проблем с правами/FS
        print("write_json error:", e)

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
    """
    Создаёт новый спринт. Если есть текущий — сохраняет в историю.
    Можно передать start_date (date object or iso str) и end_date.
    """
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
        if isinstance(start_date, str):
            start_iso = start_date
        else:
            start_iso = start_date.isoformat()
    else:
        start_iso = datetime.now().date().isoformat()

    if end_date:
        if isinstance(end_date, str):
            end_iso = end_date
        else:
            end_iso = end_date.isoformat()
    else:
        end_iso = (datetime.fromisoformat(start_iso) + timedelta(days=duration_days)).date().isoformat()

    new = {
        "name": new_name,
        "tasks": [],
        "goal": "",
        "start_date": start_iso,
        "end_date": end_iso,
        "moods": {}  # структура: { "user_id": { "YYYY-MM-DD": "😡", ... }, ... }
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
# Добавление большой задачи
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "➕ Добавить задачу")
async def add_task_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Введи текст большой задачи:")
    await state.set_state("add_task")

@dp.message_handler(state="add_task")
async def add_task_finish(message: types.Message, state: FSMContext):
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
    await state.finish()

# ======================
# Удаление большой задачи
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "🗑 Удалить задачу")
async def delete_task_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        return await message.answer("Нечего удалять.", reply_markup=main_menu())

    text = "Выберите номер задачи для удаления:\n"
    for i, t in enumerate(sprint["tasks"]):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state("delete_task")

@dp.message_handler(state="delete_task")
async def delete_task_finish(message: types.Message, state: FSMContext):
    sprint = get_sprint() or {}
    try:
        idx = int(message.text.strip()) - 1
        removed = sprint["tasks"].pop(idx)
        set_sprint(sprint)
        await message.answer(f"Удалено: ❌ {removed['text']}", reply_markup=main_menu())
    except Exception:
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    await state.finish()

# ======================
# Новый спринт (с ручным вводом дат)
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "🔄 Новый спринт")
async def new_sprint_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Введите дату начала спринта в формате ДД.ММ.ГГГГ (или напиши 'сейчас'):")
    await state.set_state(SprintStates.start_date)

@dp.message_handler(state=SprintStates.start_date)
async def new_sprint_start_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    try:
        if date_str.lower() in ("сейчас", "now", "today", ""):
            start = datetime.now().date()
        else:
            start = datetime.strptime(date_str, "%d.%m.%Y").date()
        await state.update_data(start_date=start.isoformat())
        await message.answer("Введите дату окончания спринта в формате ДД.ММ.ГГГГ (или оставьте пустым для +3 недели):")
        await state.set_state(SprintStates.end_date)
    except ValueError:
        await message.answer("Некорректный формат даты. Попробуйте ДД.ММ.ГГГГ")

@dp.message_handler(state=SprintStates.end_date)
async def new_sprint_end_date(message: types.Message, state: FSMContext):
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
        await message.answer("Некорректный формат даты. Попробуйте ДД.ММ.ГГГГ", reply_markup=main_menu())
        await state.finish()
        return

    if end_date < start_date:
        await message.answer("Дата окончания не может быть раньше начала. Попробуйте снова.", reply_markup=main_menu())
        await state.finish()
        return

    create_new_sprint(name=f"Спринт {start_date.strftime('%d.%m.%Y')}",
                      duration_days=(end_date - start_date).days,
                      start_date=start_date.isoformat(),
                      end_date=end_date.isoformat())

    await message.answer(f"Спринт создан с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} ✅", reply_markup=main_menu())
    await state.finish()

# ======================
# Добавление мини-задачи (подзадачи)
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "➕ Мини-задача")
async def add_subtask_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        return await message.answer("Сначала добавь большую задачу.", reply_markup=main_menu())

    text = "Выберите номер большой задачи для добавления мини-задачи:\n"
    for i, t in enumerate(sprint["tasks"]):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state("choose_task_for_subtask")

@dp.message_handler(state="choose_task_for_subtask")
async def add_subtask_choose_task(message: types.Message, state: FSMContext):
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
        await state.finish()

@dp.message_handler(state="add_subtask")
async def add_subtask_finish(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        index = data.get("task_index")
        sprint = get_sprint() or create_new_sprint()

        if index is None or index < 0 or index >= len(sprint.get("tasks", [])):
            raise ValueError("Задача не найдена")

        # Создаём список подзадач, если его нет
        if "subtasks" not in sprint["tasks"][index]:
            sprint["tasks"][index]["subtasks"] = []

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
        await state.finish()

# ======================
# Выполнение мини-задачи
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "✅ Выполнить мини-задачу")
async def complete_subtask_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    choices = []
    if sprint:
        for i, task in enumerate(sprint.get("tasks", [])):
            for j, sub in enumerate(task.get("subtasks", [])):
                if not sub.get("done"):
                    choices.append((i, j, sub.get("text"), task.get("text")))
    if not choices:
        return await message.answer("Нет мини-задач для выполнения.", reply_markup=main_menu())

    text = "Выберите мини-задачу для выполнения:\n"
    for idx, (i, j, sub_text, task_text) in enumerate(choices):
        text += f"{idx + 1}. [{task_text}] {sub_text}\n"

    await state.update_data(choices=choices)
    await message.answer(text)
    await state.set_state("complete_subtask")

@dp.message_handler(state="complete_subtask")
async def complete_subtask_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    choices = data.get("choices", [])
    try:
        index = int(message.text.strip()) - 1
        if index < 0 or index >= len(choices):
            raise ValueError("Номер вне диапазона")
        i, j, sub_text, task_text = choices[index]
        sprint = get_sprint()
        sprint["tasks"][i]["subtasks"][j]["done"] = True
        set_sprint(sprint)

        stats = get_user_stats()
        uid = str(message.from_user.id)
        stats.setdefault(uid, {"points": 0, "moods": {}})
        stats[uid]["points"] += 1
        save_user_stats(stats)

        await message.answer(
            f"Мини-задача '{sub_text}' выполнена! ✅\n🏅 Баллы: {stats[uid]['points']}",
            reply_markup=main_menu()
        )
    except Exception as e:
        print("Ошибка при завершении мини-задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    finally:
        await state.finish()

# ======================
# Завершение большой задачи (с уведомлением в канал)
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "✅ Завершить задачу")
async def complete_task_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint or not sprint.get("tasks"):
        return await message.answer("Нет задач для завершения 😅", reply_markup=main_menu())

    undone = [t for t in sprint.get("tasks", []) if not t.get("done")]
    if not undone:
        return await message.answer("Все задачи уже завершены 🎉", reply_markup=main_menu())

    text = "Выберите номер незавершённой задачи:\n"
    for i, t in enumerate(undone):
        text += f"{i + 1}. {t['text']}\n"
    await message.answer(text)
    await state.set_state("complete_task")

@dp.message_handler(state="complete_task")
async def complete_task_finish(message: types.Message, state: FSMContext):
    sprint = get_sprint()
    undone = [t for t in sprint.get("tasks", []) if not t.get("done")]
    try:
        index = int(message.text.strip()) - 1
        task = undone[index]
        # найти оригинальный объект в sprint["tasks"]
        for original in sprint["tasks"]:
            if original["text"] == task["text"]:
                original["done"] = True
                break
        set_sprint(sprint)

        stats = get_user_stats()
        uid = str(message.from_user.id)
        if uid not in stats:
            stats[uid] = {"points": 0, "moods": {}}
        stats[uid]["points"] += 10
        save_user_stats(stats)

        # уведомление в канал
        await notify_task_done(message.from_user.id, task["text"], stats[uid]["points"])

        await message.answer(f"Задача '{task['text']}' завершена! 🎉\n🏅 Очки: {stats[uid]['points']}", reply_markup=main_menu())
    except Exception as e:
        print("Ошибка при завершении большой задачи:", e)
        await message.answer("Некорректный номер 😅", reply_markup=main_menu())
    await state.finish()

# ======================
# Уведомление в канал + callback praise
# ======================
async def notify_task_done(user_id, task_text, points):
    try:
        chat = await bot.get_chat(user_id)
        username = chat.username or chat.first_name or str(user_id)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("👍 Похвалить", callback_data=f"praise_{user_id}_{task_text}"))
        await bot.send_message(CHANNEL_ID, f"Пользователь @{username} завершил задачу: {task_text} ✅\n🏅 Баллы: {points}", reply_markup=kb)
    except Exception as e:
        print("notify_task_done error:", e)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("praise_"))
async def handle_praise(callback_query: types.CallbackQuery):
    try:
        parts = callback_query.data.split("_", 2)
        user_id = int(parts[1])
        task_text = parts[2]
        await callback_query.answer(f"Похвалено за '{task_text}'! 🎉")
        stats = get_user_stats()
        uid = str(user_id)
        if uid not in stats:
            stats[uid] = {"points": 0, "moods": {}}
        stats[uid]["points"] += 2
        save_user_stats(stats)
    except Exception:
        await callback_query.answer("Ошибка обработки похвалы.")

# ======================
# Ревью — публикует в канал и показывает пользователю (расширенное: считает эмоции и баллы)
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip().lower().startswith("🧐") or (m.text and "ревью" in m.text.lower()))
async def review_handler(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    sprint = get_sprint()
    if not sprint:
        return await message.answer("Нет данных для ревью 😅", reply_markup=main_menu())

    # --- задачи и баллы ---
    tasks = sprint.get("tasks", [])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))
    not_done = total - done

    stats = get_user_stats()
    # суммируем очки участников, относим к текущему спринту
    points_total = 0
    for uid, info in stats.items():
        points_total += info.get("points", 0)

    # --- эмоции ---
    moods_block = sprint.get("moods", {})  # {user_id: {date: emoji}}
    mood_counts = {}
    for uid, days in moods_block.items():
        for d, emo in days.items():
            mood_counts[emo] = mood_counts.get(emo, 0) + 1

    # Формируем текст ревью
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

    # публикуем в канал
    try:
        await bot.send_message(CHANNEL_ID, f"{text_user}", parse_mode="Markdown")
    except Exception as e:
        print("Ошибка отправки ревью в канал:", e)

# ======================
# Ретро — постановка цели и публикация
# ======================
@dp.message_handler(lambda m: m.text and m.text.strip() == "🎭 Ретро")
async def retro_start(message: types.Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Напиши цель для следующего спринта:")
    await state.set_state("set_new_goal")

@dp.message_handler(state="set_new_goal")
async def set_new_goal(message: types.Message, state: FSMContext):
    sprint = get_sprint() or create_new_sprint()
    sprint["goal"] = message.text.strip()
    set_sprint(sprint)
    await message.answer(f"Цель сохранена: {sprint['goal']}", reply_markup=main_menu())
    try:
        await bot.send_message(CHANNEL_ID, f"🎯 Новая цель спринта '{sprint.get('name','Спринт')}':\n{ sprint['goal'] }")
    except Exception:
        pass
    await state.finish()

# ======================
# Статус задач (дублируется в канал)
# ======================
@dp.message_handler(lambda m: m.text and "статус" in m.text.lower())
async def status_tasks(message: types.Message):
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

# ======================
# Муд-календарь — кнопка и inline обработка
# ======================
# выбранные эмоции: 1. 😎 2. 🥴 3. 🫨 4. 😐 5. ☹️ 6. 😭 7. 😌 8. 😊 9. 😆 10. 🤢 11. 😡 12. 😱
MOOD_EMOJIS = ["😎","🥴","🫨","😐","☹️","😭","😌","😊","😆","🤢","😡","😱"]
MOOD_LABELS = {
    "😎": "Янаконе",
    "🥴": "Непонятно",
    "🫨": "На тревоге",
    "😐": "Апатия",
    "☹️": "Грущу",
    "😭": "Очень грущу",
    "😌": "Спокоен",
    "😊": "Довольный",
    "😆": "Веселюсь",
    "🤢": "Переотдыхал",
    "😡": "Злюсь",
    "😱": "В шоке"
}

def mood_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    for idx, e in enumerate(MOOD_EMOJIS):
        kb.insert(InlineKeyboardButton(text=e, callback_data=f"mood_{idx}"))
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
        try:
            idx = int(code)
            emo = MOOD_EMOJIS[idx]
        except Exception:
            emo = MOOD_EMOJIS[0]

        stats = get_user_stats()
        uid = str(callback_query.from_user.id)
        today = str(datetime.now().date())

        if uid not in stats:
            stats[uid] = {"points": 0, "moods": {}}
        stats[uid]["moods"][today] = emo
        # optionally give small points for logging mood
        save_user_stats(stats)

        # save also into sprint (aggregate moods per sprint)
        sprint = get_sprint() or create_new_sprint()
        sprint.setdefault("moods", {})
        sprint["moods"].setdefault(uid, {})
        sprint["moods"][uid][today] = emo
        set_sprint(sprint)

        await callback_query.answer(f"Записала настроение: {emo} — {MOOD_LABELS.get(emo,'')}")
        # подтверждение в личку
        try:
            await bot.send_message(callback_query.from_user.id, f"Записала твоё настроение на {today}: {emo} — {MOOD_LABELS.get(emo,'')}", reply_markup=main_menu())
        except Exception:
            pass

        # дублируем в канал (кратко)
        try:
            await bot.send_message(CHANNEL_ID, f"Настроение @{callback_query.from_user.username}: {emo}")
        except Exception:
            pass

    except Exception as e:
        print("process_mood error:", e)
        await callback_query.answer("Ошибка при сохранении настроения.")

# ======================
# Отзывы из канала (#отзыв)
# ======================
@dp.message_handler(lambda m: isinstance(m.text, str) and "#отзыв" in m.text.lower(), content_types=types.ContentTypes.TEXT)
async def save_review(message: types.Message):
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

# ======================
# Команда /restart
# ======================
@dp.message_handler(commands=["restart"])
async def cmd_restart(message: types.Message):
    if not check_access(message.from_user.id):
        return await message.answer("У тебя нет прав на перезапуск.")
    await message.answer("🔄 Перезапуск бота...")
    await asyncio.sleep(1)
    try:
        python = sys.executable
        os.execv(python, [python] + sys.argv)
    except Exception as e:
        await message.answer(f"Ошибка при restart: {e}")

# ======================
# Ежедневный опрос настроения — в 20:00 по Москве (MSK)
# ======================
async def send_daily_mood_msk():
    """
    Пишет каждому в USER_IDS опрос в 20:00 по Москве.
    Использует zoneinfo если доступен, иначе фиксированный +3 offset.
    """
    # определим зону Москвы
    if ZoneInfo:
        tz = ZoneInfo("Europe/Moscow")
    else:
        class FixedTZ:
            def utcoffset(self, dt): return timedelta(hours=3)
        tz = None  # fallback handled below

    while True:
        try:
            if ZoneInfo:
                now = datetime.now(tz)
                target = now.replace(hour=20, minute=0, second=0, microsecond=0)
                if now >= target:
                    target = target + timedelta(days=1)
                wait_seconds = (target - now).total_seconds()
            else:
                # fallback: use system local time but shift to MSK by +3
                now_utc = datetime.utcnow()
                msk_now = now_utc + timedelta(hours=3)
                target = msk_now.replace(hour=20, minute=0, second=0, microsecond=0)
                if msk_now >= target:
                    target = target + timedelta(days=1)
                wait_seconds = (target - msk_now).total_seconds()

            # wait until target
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            # at target time: send mood keyboard to users
            for uid in USER_IDS:
                try:
                    await bot.send_message(uid, "Как настроение сегодня? (опрос в 20:00 MSK)", reply_markup=mood_keyboard())
                except Exception:
                    pass

            # short sleep to avoid double-send in the same minute
            await asyncio.sleep(60)

        except Exception as e:
            print("send_daily_mood_msk error:", e)
            # если падение — подожди минуту и попробуй снова
            await asyncio.sleep(60)

# ======================
# Фоновые задачи запускаются в on_startup
# ======================
async def on_startup(dp_):
    if not get_sprint():
        create_new_sprint()
    # запустить опрос в 20:00 MSK
    asyncio.create_task(send_daily_mood_msk())

# ======================
# Запуск
# ======================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

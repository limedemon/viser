import os
import sys
import subprocess
import asyncio
import logging
import random
import sqlite3
import time

# === АВТОМАТИЧЕСКАЯ УСТАНОВКА БИБЛИОТЕК ===
def install_requirements():
    try:
        import aiogram
    except ImportError:
        print("Библиотека aiogram не найдена. Начинаю автоматическую установку...")
        try:
            # Запускаем pip install через системный вызов
            subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram==3.4.1"])
            print("Установка успешно завершена! Загружаю бота...")
        except Exception as e:
            print(f"Критическая ошибка при установке библиотеки: {e}")
            sys.exit(1)

# Вызываем проверку до того, как пытаемся импортировать aiogram
install_requirements()

# Теперь безопасно импортируем aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, 
    KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# === КОНФИГУРАЦИЯ ===
TOKEN = "8770327861:AAEPgHBTjpoqhLsl8f8KMoyzo1xrtWjeyrM"
MAIN_ADMIN_ID = 1018561747
COOLDOWN_SECONDS = 600  # 10 минут (600 секунд)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# === НАСТРОЙКА ПУТЕЙ И ПАПОК ДЛЯ СОХРАНЕНИЯ ===
# Получаем абсолютный путь к папке, где находится этот скрипт
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Создаем путь к папке с данными бота
DATA_DIR = os.path.join(BASE_DIR, 'bot_data')
# Путь к самому файлу базы данных внутри папки bot_data
DB_PATH = os.path.join(DATA_DIR, 'cards_bot.db')

# === БАЗА ДАННЫХ ===
def init_db():
    # Проверяем, существует ли папка для данных, и создаем её, если нет
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Папка для сохранения прогресса создана по пути: {DATA_DIR}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица пользователей (храним баланс и время последнего открытия)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_getcard INTEGER DEFAULT 0
        )
    ''')
    # Таблица карт
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT NOT NULL,
            name TEXT NOT NULL,
            weight INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    # Всегда подключаемся по строгому пути, чтобы избежать создания дубликатов баз данных
    return sqlite3.connect(DB_PATH)

# === СОСТОЯНИЯ FSM ===
class AddCardState(StatesGroup):
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_weight = State()

# === КЛАВИАТУРЫ ===
def get_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Добавить карту"), KeyboardButton(text="Удалить карту")]
        ],
        resize_keyboard=True
    )

def get_cards_delete_kb(cards_list):
    # cards_list = [(card_id, name), ...]
    keyboard = []
    for card_id, name in cards_list:
        # Создаем кнопку для каждой карты
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"delcard_{card_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# === ХЭНДЛЕРЫ ===

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Регистрируем пользователя, если его еще нет в базе
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance, last_getcard) VALUES (?, 0, 0)", (user_id,))
    conn.commit()
    conn.close()

    if user_id == MAIN_ADMIN_ID:
        await message.answer(
            "Добро пожаловать, Создатель! Админ-панель активирована.", 
            reply_markup=get_admin_kb()
        )
    else:
        await message.answer(
            "Привет! Я карточный бот.\n"
            "Используй команду /getcard, чтобы выбить новую карту и заработать деньги!"
        )

# --- ЛОГИКА ДОБАВЛЕНИЯ КАРТЫ ---

@dp.message(F.text == "Добавить карту")
async def start_add_card(message: Message, state: FSMContext):
    if message.from_user.id != MAIN_ADMIN_ID:
        return
    await message.answer("Отправь фото новой карты:")
    await state.set_state(AddCardState.waiting_for_photo)

@dp.message(AddCardState.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    # Берем фото в лучшем качестве (последний элемент массива)
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Отлично! Теперь введи название карты:")
    await state.set_state(AddCardState.waiting_for_name)

@dp.message(AddCardState.waiting_for_photo)
async def process_photo_invalid(message: Message):
    await message.answer("Ошибка! Пожалуйста, отправь именно фото, а не текст или документ.")

@dp.message(AddCardState.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Принято. Введи вес (шанс выпадения) карты целым числом.\nЧем больше вес, тем чаще она падает:")
    await state.set_state(AddCardState.waiting_for_weight)

@dp.message(AddCardState.waiting_for_weight, F.text)
async def process_weight(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Вес должен быть положительным числом! Попробуй еще раз:")
        return
    
    weight = int(message.text)
    data = await state.get_data()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cards (photo_id, name, weight) VALUES (?, ?, ?)", 
        (data['photo_id'], data['name'], weight)
    )
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Карта «{data['name']}» успешно создана и добавлена в базу!")
    await state.clear()

# --- ЛОГИКА УДАЛЕНИЯ КАРТЫ ---

@dp.message(F.text == "Удалить карту")
async def start_delete_card(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT card_id, name FROM cards")
    cards = cursor.fetchall()
    conn.close()
    
    if not cards:
        await message.answer("В базе пока нет добавленных карт.")
        return
    
    await message.answer("Нажми на карту, чтобы удалить её навсегда:", reply_markup=get_cards_delete_kb(cards))

@dp.callback_query(F.data.startswith("delcard_"))
async def process_delete_card(callback: CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
    
    card_id = int(callback.data.split("_")[1])
    
    # Удаляем из БД
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
    conn.commit()
    conn.close()
    
    # Всплывающее уведомление
    await callback.answer("Карта удалена!", show_alert=True)
    
    # Плавное обновление клавиатуры (удаление нажатой кнопки)
    current_keyboard = callback.message.reply_markup.inline_keyboard
    new_keyboard = []
    
    for row in current_keyboard:
        # Оставляем только те кнопки, дата которых не совпадает с нажатой
        new_row = [btn for btn in row if btn.callback_data != callback.data]
        if new_row:
            new_keyboard.append(new_row)
            
    if new_keyboard:
        try:
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard))
        except TelegramBadRequest:
            pass # Если не удалось обновить (например, двойной клик)
    else:
        # Если кнопок больше не осталось
        await callback.message.edit_text("✅ Все карты из этого списка были удалены.")

# --- ВЫБИВАНИЕ КАРТЫ (/getcard) ---

@dp.message(Command("getcard"))
async def cmd_getcard(message: Message):
    user_id = message.from_user.id
    current_time = int(time.time())
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверка пользователя и его кулдауна
    cursor.execute("SELECT balance, last_getcard FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        cursor.execute("INSERT INTO users (user_id, balance, last_getcard) VALUES (?, 0, 0)", (user_id,))
        balance, last_getcard = 0, 0
    else:
        balance, last_getcard = user_data
        
    time_passed = current_time - last_getcard
    if time_passed < COOLDOWN_SECONDS:
        remaining = COOLDOWN_SECONDS - time_passed
        minutes = remaining // 60
        seconds = remaining % 60
        await message.answer(f"⏳ Карты перезаряжаются.\nПодожди еще <b>{minutes} мин {seconds} сек</b>.", parse_mode="HTML")
        conn.close()
        return
        
    # Достаем все карты для генерации дропа
    cursor.execute("SELECT card_id, photo_id, name, weight FROM cards")
    cards = cursor.fetchall()
    
    if not cards:
        await message.answer("Бот пока пуст. Администратор еще не добавил карты!")
        conn.close()
        return
        
    # Реализация взвешенного рандома (с учетом веса карты)
    weights = [c[3] for c in cards]
    chosen_card = random.choices(cards, weights=weights, k=1)[0]
    
    card_photo = chosen_card[1]
    card_name = chosen_card[2]
    
    # Даем случайную награду
    reward = random.randint(100, 500)
    new_balance = balance + reward
    
    # Обновляем профиль (сбрасываем таймер и начисляем баланс)
    cursor.execute(
        "UPDATE users SET balance = ?, last_getcard = ? WHERE user_id = ?", 
        (new_balance, current_time, user_id)
    )
    conn.commit()
    conn.close()
    
    # Отправляем фото и результат
    await message.answer_photo(
        photo=card_photo,
        caption=(
            f"🎉 <b>Ты выбил карту: {card_name}!</b>\n\n"
            f"💸 Награда за находку: <b>{reward} монет</b>\n"
            f"💰 Твой текущий баланс: <b>{new_balance} монет</b>"
        ),
        parse_mode="HTML"
    )

# === ЗАПУСК ===
async def main():
    init_db()
    # Пропускаем старые апдейты, чтобы бот не реагировал на старые команды при перезапуске
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

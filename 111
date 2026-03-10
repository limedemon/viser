import asyncio
import logging
import json
import os
import random
import re
import sys
import subprocess
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, LabeledPrice, PreCheckoutQuery
from aiogram.exceptions import TelegramRetryAfter

# --- АРХИТЕКТУРА ХОСТИНГА (MAIN / CHILD) ---
IS_CHILD = "--child" in sys.argv
MAIN_BOT_USERNAME = ""

if IS_CHILD:
    idx = sys.argv.index("--child")
    TOKEN = sys.argv[idx + 1]
    SUPER_ADMIN_ID = int(sys.argv[idx + 2])
    BOT_ID = sys.argv[idx + 3]
    if len(sys.argv) > idx + 4:
        MAIN_BOT_USERNAME = sys.argv[idx + 4]
    BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "botgroup", "hosted_bots", str(BOT_ID))
else:
    TOKEN = "8770327861:AAGGtIwkeXSZD1p3EBAzhFVG70MVgIcdOCY"
    SUPER_ADMIN_ID = 1018561747
    BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "botgroup")

DATA_FILE = os.path.join(BASE_DIR, "cards.json")
DB_FILE = os.path.join(BASE_DIR, "users.db")
EVENTS_FILE = os.path.join(BASE_DIR, "events.json")
ENCHANTS_FILE = os.path.join(BASE_DIR, "enchants.json")
HOSTED_BOTS_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "botgroup", "hosted_bots.json")

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
ADMINS = set()

# --- СОСТОЯНИЯ FSM ---
class AddCardStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_weight = State()
    waiting_for_category = State()

class DeleteCardStates(StatesGroup):
    waiting_for_id = State()

class ChangeIconStates(StatesGroup):
    waiting_for_photo = State()

# --- ГЛОБАЛЬНЫЕ ДАННЫЕ ЭВЕНТОВ И АУКЦИОНОВ ---
reset_state = {"count": 0, "timer": None}
resetcards_state = {"count": 0, "timer": None}

events = {
    "luck": {"end_time": None, "next_announce": None, "name": "🍀 Удача", "mult": 1.0},
    "cooldown": {"end_time": None, "next_announce": None, "name": "⚡ Ускоренная перезарядка", "mult": 1.0},
    "shiny": {"end_time": None, "next_announce": None, "name": "✨ Shiny Удача", "mult": 1.0},
    "wipe": {"end_time": None, "next_announce": None, "name": "🔄 Вайп сезона", "mult": 1.0}
}

auc_state = {
    "active": False, 
    "card": None, 
    "is_shiny": 0, 
    "enchant_id": 0, 
    "start_price": 0, 
    "current_bid": 0,
    "min_step": 0, 
    "highest_bidder": None, 
    "highest_bidder_name": "",
    "end_time": None, 
    "messages": [] 
}

# --- БАЗОВЫЕ ФУНКЦИИ ФАЙЛОВ ---
def load_cards():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_cards(cards):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=4)

def load_enchants():
    if not os.path.exists(ENCHANTS_FILE):
        return []
    try:
        with open(ENCHANTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_enchants(enchants):
    total_weight = sum(e["weight"] for e in enchants)
    for e in enchants:
        if total_weight > 0:
            e["percent"] = round((e["weight"] / total_weight) * 100, 6)
        else:
            e["percent"] = 0.0
    with open(ENCHANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(enchants, f, ensure_ascii=False, indent=4)

def load_events():
    global events
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if k in events:
                        if v.get("end_time"):
                            events[k]["end_time"] = datetime.fromisoformat(v["end_time"])
                        else:
                            events[k]["end_time"] = None
                            
                        if v.get("next_announce"):
                            events[k]["next_announce"] = datetime.fromisoformat(v["next_announce"])
                        else:
                            events[k]["next_announce"] = None
                            
                        events[k]["mult"] = v.get("mult", 1.0)
                        if "name" in v:
                            events[k]["name"] = v["name"]
        except Exception:
            save_events()
    else:
        save_events()

def save_events():
    data = {}
    for k, v in events.items():
        data[k] = {
            "name": v["name"],
            "end_time": v["end_time"].isoformat() if v["end_time"] else None,
            "next_announce": v["next_announce"].isoformat() if v["next_announce"] else None,
            "mult": v["mult"]
        }
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ФУНКЦИИ ФОРМАТИРОВАНИЯ ---
def fmt_percent(val):
    s = f"{val:.6f}".rstrip('0')
    if s.endswith('.'):
        s += '00'
    elif len(s.split('.')[1]) == 1:
        s += '0'
    return s

def get_rarity(weight):
    if weight >= 70:
        return "⬜Обычная⬜"
    elif weight >= 50:
        return "🟩Необычная🟩"
    elif weight >= 25:
        return "🟦Редкая🟦"
    elif weight >= 10:
        return "🟪Эпическая🟪"
    elif weight >= 1:
        return "🟨Легендарная🟨"
    elif weight >= 0.1:
        return "🟥Мифическая🟥"
    elif weight >= 0.01:
        return "🔵Божественная🔵"
    else:
        return "🌌Галактическая🌌"

def get_points_for_rarity(rarity):
    m = {
        "⬜Обычная⬜": (1, 3), 
        "🟩Необычная🟩": (4, 8), 
        "🟦Редкая🟦": (9, 13), 
        "🟪Эпическая🟪": (14, 20), 
        "🟨Легендарная🟨": (21, 35), 
        "🟥Мифическая🟥": (36, 50), 
        "🔵Божественная🔵": (51, 100), 
        "🌌Галактическая🌌": (101, 500)
    }
    if rarity in m:
        return random.randint(m[rarity][0], m[rarity][1])
    return 1

def get_money_for_rarity(rarity):
    m = {
        "⬜Обычная⬜": (1, 10), 
        "🟩Необычная🟩": (5, 25), 
        "🟦Редкая🟦": (20, 50), 
        "🟪Эпическая🟪": (30, 80), 
        "🟨Легендарная🟨": (80, 120), 
        "🟥Мифическая🟥": (100, 200), 
        "🔵Божественная🔵": (350, 600), 
        "🌌Галактическая🌌": (800, 1200)
    }
    if rarity in m:
        return random.randint(m[rarity][0], m[rarity][1])
    return 0

def get_author_bonus(rarity):
    m = {
        "⬜Обычная⬜": 0.1, 
        "🟩Необычная🟩": 0.1, 
        "🟦Редкая🟦": 0.2, 
        "🟪Эпическая🟪": 0.3, 
        "🟨Легендарная🟨": 0.4, 
        "🟥Мифическая🟥": 1.0, 
        "🔵Божественная🔵": 1.0, 
        "🌌Галактическая🌌": 1.0
    }
    return m.get(rarity, 0.0)

# --- ЛОГИКА БД ---
async def init_db():
    global ADMINS
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, cards_count INTEGER DEFAULT 0, 
            rarest_card_name TEXT DEFAULT "Нет", rarest_card_chance REAL DEFAULT 100.0, 
            last_get TIMESTAMP, full_name TEXT DEFAULT "Игрок"
        )''')
        
        for col in ['is_premium', 'money', 'has_shield', 'has_thief', 'has_respirator', 'auc_opt_out', 'max_ambitions']:
            try:
                await db.execute(f'ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0')
                await db.commit()
            except Exception:
                pass
            
        for col in ['username', 'season_money', 'last_stolen_from']:
            try:
                if col != 'season_money':
                    await db.execute(f'ALTER TABLE users ADD COLUMN {col} TEXT')
                else:
                    await db.execute(f'ALTER TABLE users ADD COLUMN {col} REAL DEFAULT 0.0')
                await db.commit()
            except Exception:
                pass
            
        await db.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
        await db.execute('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY)')
        
        async with db.execute("PRAGMA table_info(user_inventory)") as cursor:
            cols = [col[1] for col in await cursor.fetchall()]
            
        await db.execute('''CREATE TABLE IF NOT EXISTS user_inventory_new (
            user_id INTEGER, card_id INTEGER, is_shiny INTEGER DEFAULT 0, enchant_id INTEGER DEFAULT 0, count INTEGER DEFAULT 1, 
            PRIMARY KEY (user_id, card_id, is_shiny, enchant_id)
        )''')
        
        if cols:
            if "enchant_id" not in cols:
                shiny_col = "is_shiny" if "is_shiny" in cols else "0"
                await db.execute(f"INSERT OR IGNORE INTO user_inventory_new (user_id, card_id, is_shiny, enchant_id, count) SELECT user_id, card_id, {shiny_col}, 0, SUM(count) FROM user_inventory GROUP BY user_id, card_id, {shiny_col}")
                await db.execute("DROP TABLE user_inventory")
                await db.execute("ALTER TABLE user_inventory_new RENAME TO user_inventory")
            else:
                await db.execute("INSERT OR IGNORE INTO user_inventory_new SELECT * FROM user_inventory")
                await db.execute("DROP TABLE user_inventory")
                await db.execute("ALTER TABLE user_inventory_new RENAME TO user_inventory")
        else:
            await db.execute("ALTER TABLE user_inventory_new RENAME TO user_inventory")
            
        await db.execute('''CREATE TABLE IF NOT EXISTS categories (
            cat_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, exp_mult REAL DEFAULT 1.0, money_mult REAL DEFAULT 1.0, max_inv INTEGER
        )''')
        
        await db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (SUPER_ADMIN_ID,))
        await db.commit()
        
        async with db.execute('SELECT user_id FROM admins') as cursor:
            rows = await cursor.fetchall()
            ADMINS = {row[0] for row in rows}

async def update_max_ambitions(user_id: int, db: aiosqlite.Connection):
    async with db.execute("SELECT points, money, max_ambitions FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return
        points, money, max_ambitions = row
        
    async with db.execute("SELECT SUM(count) FROM user_inventory WHERE user_id = ?", (user_id,)) as cursor:
        tc_row = await cursor.fetchone()
        total_cards = tc_row[0] if tc_row and tc_row[0] else 0
        
    curr_ambitions = int((points / 100) + (money / 1000) + total_cards)
    if curr_ambitions > max_ambitions:
        await db.execute("UPDATE users SET max_ambitions = ? WHERE user_id = ?", (curr_ambitions, user_id))
        await db.commit()

async def register_chat(chat_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR IGNORE INTO chats (chat_id) VALUES (?)', (chat_id,))
        await db.commit()

async def get_auction_chats():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT c.chat_id, IFNULL(u.auc_opt_out, 0) FROM chats c LEFT JOIN users u ON c.chat_id = u.user_id') as cursor:
            return [chat_id for chat_id, opt_out in await cursor.fetchall() if chat_id < 0 or opt_out == 0]

# --- МИДЛВАРЬ ---
class ChatRegistrationMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            if hasattr(event, "chat") and event.chat:
                await register_chat(event.chat.id)
            if hasattr(event, "from_user") and event.from_user:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('''
                        INSERT INTO users (user_id, full_name, username) 
                        VALUES (?, ?, ?) 
                        ON CONFLICT(user_id) DO UPDATE SET 
                            full_name = EXCLUDED.full_name, 
                            username = EXCLUDED.username
                    ''', (event.from_user.id, event.from_user.full_name, event.from_user.username))
                    await db.commit()
        except Exception as e:
            logging.error(f"Middleware Error: {e}")
        return await handler(event, data)

dp.message.middleware(ChatRegistrationMiddleware())

# --- УТИЛИТЫ ---
async def broadcast(text: str, target: str = "all") -> int:
    async with aiosqlite.connect(DB_FILE) as db:
        if target == "groups":
            query = "SELECT chat_id FROM chats WHERE chat_id < 0"
        elif target == "private":
            query = "SELECT user_id FROM users"
        else:
            query = "SELECT chat_id FROM chats"
            
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            
    success_count = 0
    for (cid,) in rows:
        try:
            await bot.send_message(cid, text, parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
            success_count += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(cid, text, parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
            except Exception:
                pass
        except Exception:
            pass
    return success_count

async def perform_wipe():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT user_id, IFNULL(points, 0), IFNULL(money, 0), IFNULL(max_ambitions, 0) FROM users") as cursor:
            users_data = await cursor.fetchall()
            
        for user_id, points, money, max_ambitions in users_data:
            async with db.execute("SELECT SUM(count) FROM user_inventory WHERE user_id = ?", (user_id,)) as cursor:
                tc_row = await cursor.fetchone()
                total_cards = tc_row[0] if tc_row and tc_row[0] else 0
                
            curr_ambitions = int((points / 100) + (money / 1000) + total_cards)
            final_ambitions = max(curr_ambitions, max_ambitions)
            
            if final_ambitions == 0:
                continue
                
            season_earned = round(final_ambitions / 10.0, 1)
            await db.execute('''UPDATE users SET points = 0, money = 0, cards_count = 0, 
                                season_money = IFNULL(season_money, 0.0) + ?, 
                                has_shield = 0, has_thief = 0, has_respirator = 0, max_ambitions = 0 
                                WHERE user_id = ?''', (season_earned, user_id))
            try:
                await bot.send_message(user_id, f"🔄 <b>Сезон завершен!</b>\nАмбиции: <b>{final_ambitions}</b> 🔥\nПолучено: <b>{season_earned} СМ</b> 🍂!\nИнвентарь и баланс сброшены.", parse_mode="HTML")
            except Exception:
                pass
                
        await db.execute("DELETE FROM user_inventory")
        await db.commit()
    await broadcast("⚠️ <b>Внимание!</b> Сезон завершен! Инвентари сброшены.", "all")

# --- ФОНОВЫЕ ЗАДАЧИ И ТАЙМЕРЫ ---
def get_auc_text(time_left):
    card_name = auc_state["card"]["name"]
    if auc_state.get("is_shiny"):
        card_name += " ⭐️Shiny⭐️"
        
    if auc_state.get("enchant_id"):
        enchants = load_enchants()
        ename = next((e["name"] for e in enchants if e["id"] == auc_state["enchant_id"]), f"ID {auc_state['enchant_id']}")
        card_name += f"\n🔮 Энчант: {ename}"
        
    rarity = auc_state["card"].get("rarity", "")
    bidder = auc_state["highest_bidder_name"]
    if not bidder:
        bidder = "---"
        
    if auc_state["highest_bidder"]:
        next_bid = auc_state["current_bid"] + auc_state["min_step"]
    else:
        next_bid = auc_state["start_price"]
        
    return (f"📢 <b>АУКЦИОН НАЧАЛСЯ!</b> 📢\n\n"
            f"🃏 <b>{card_name}</b> | {rarity}\n\n"
            f"💰 Текущая ставка: <b>{auc_state['current_bid']} 💰</b>\n"
            f"👤 Лидер: {bidder}\n"
            f"⏱ Осталось: <b>{time_left} сек.</b>\n\n"
            f"Жми кнопку ниже или пиши /stavka (мин. {next_bid} 💰)")

def get_auc_kb(next_bid):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Сделать ставку: {next_bid} 💰", callback_data="auc_bid")
    return builder.as_markup()

async def force_update_auction_messages():
    if not auc_state["active"] or not auc_state["end_time"]:
        return
        
    now = datetime.now()
    if now >= auc_state["end_time"]:
        return
        
    time_left = int((auc_state["end_time"] - now).total_seconds())
    
    if auc_state["highest_bidder"]:
        next_bid = auc_state["current_bid"] + auc_state["min_step"]
    else:
        next_bid = auc_state["start_price"]
        
    text = get_auc_text(time_left)
    kb = get_auc_kb(next_bid)
    
    for chat_id, msg_id in auc_state["messages"]:
        try:
            await bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=text, reply_markup=kb, parse_mode="HTML")
        except TelegramRetryAfter: 
            pass 
        except Exception: 
            pass

async def auction_manager_task():
    while True:
        await asyncio.sleep(2)
        try:
            if auc_state["active"] and auc_state["end_time"] and datetime.now() >= auc_state["end_time"]:
                auc_state["active"] = False
                winner_id = auc_state["highest_bidder"]
                card = auc_state["card"]
                is_shiny_auc = auc_state.get("is_shiny", 0)
                enchant_id_auc = auc_state.get("enchant_id", 0)
                
                if winner_id:
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute('''INSERT INTO user_inventory (user_id, card_id, is_shiny, enchant_id, count) 
                                            VALUES (?, ?, ?, ?, 1) 
                                            ON CONFLICT(user_id, card_id, is_shiny, enchant_id) DO UPDATE SET count=count+1''', 
                                         (winner_id, card['id'], is_shiny_auc, enchant_id_auc))
                        await db.commit()
                        
                    for chat_id, msg_id in auc_state["messages"]:
                        try: 
                            await bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=f"🎉 <b>Аукцион завершен!</b>\nПобедитель: {auc_state['highest_bidder_name']}\nПобедная ставка: {auc_state['current_bid']} 💰", parse_mode="HTML")
                        except Exception: 
                            pass
                    
                    enchants = load_enchants()
                    ench_dict = {e['id']: e['name'] for e in enchants}
                    ench_txt = ""
                    if enchant_id_auc > 0:
                        ench_txt = f"\n🔮 Энчант: {ench_dict.get(enchant_id_auc, f'ID {enchant_id_auc}')}"
                        
                    shiny_txt = ""
                    if is_shiny_auc:
                        shiny_txt = " ⭐️Shiny⭐️"
                        
                    try: 
                        await bot.send_message(winner_id, f"🎉 Поздравляем! Вы выиграли аукцион и получили карту <b>{card['name']}</b>{shiny_txt}{ench_txt} за {auc_state['current_bid']} 💰!", parse_mode="HTML")
                    except Exception: 
                        pass
                else:
                    for chat_id, msg_id in auc_state["messages"]:
                        try: 
                            await bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption="😔 <b>Аукцион завершен!</b>\nСтавок не было.", parse_mode="HTML")
                        except Exception: 
                            pass
                            
                auc_state["messages"] = []
        except Exception as e:
            logging.error(f"Auction Task Error: {e}")

async def event_manager():
    while True:
        now = datetime.now()
        for key, ev in events.items():
            if ev["end_time"]:
                if key == "wipe":
                    if now >= ev["end_time"]:
                        await perform_wipe()
                        ev["end_time"] = None
                        ev["next_announce"] = None
                        save_events()
                    elif ev["next_announce"] and now >= ev["next_announce"]:
                        time_left = ev["end_time"] - now
                        hours_left = int(time_left.total_seconds() // 3600)
                        mins_left = int((time_left.total_seconds() % 3600) // 60)
                        
                        if hours_left > 0:
                            time_str = f"{hours_left} ч. {mins_left} мин."
                        else:
                            time_str = f"{mins_left} мин."
                            
                        if time_left.total_seconds() > 0:
                            await broadcast(f"⚠️ <b>Напоминание!</b>\nСброс сезона (Вайп) состоится примерно через {time_str}.", "all")
                            
                        ev["next_announce"] += timedelta(seconds=random.randint(3600, 7200))
                        save_events()
                else:
                    if now >= ev["end_time"]:
                        await broadcast(f"🔴 <b>Эвент завершен!</b>\nВремя действия <b>{ev['name']}</b> подошло к концу.", "all")
                        ev["end_time"] = None
                        ev["next_announce"] = None
                        save_events()
                    elif ev["next_announce"] and now >= ev["next_announce"]:
                        time_left = ev["end_time"] - now
                        hours_left = int(time_left.total_seconds() // 3600)
                        mins_left = int((time_left.total_seconds() % 3600) // 60)
                        
                        if hours_left > 0:
                            time_str = f"{hours_left} ч. {mins_left} мин."
                        else:
                            time_str = f"{mins_left} мин."
                            
                        if time_left.total_seconds() > 0:
                            await broadcast(f"⏳ <b>Напоминание!</b>\nЭвент <b>{ev['name']}</b> закончится примерно через {time_str}.", "all")
                            
                        ev["next_announce"] += timedelta(seconds=random.randint(3600, 7200))
                        save_events()
        await asyncio.sleep(20)

async def shop_group_reminder_task():
    while True:
        await asyncio.sleep(random.randint(3600, 7200))
        text = (
            "🛍 <b>Загляните в Премиум Магазин!</b>\n\n"
            "В личных сообщениях бота по команде /premiumshop вы можете приобрести крутые бонусы за Звёзды (⭐️) или Опыт (✨):\n\n"
            "💎 <b>Premium</b> — больше удачи и очков\n"
            "🛡 <b>Щит</b> — защита от краж на весь сезон\n"
            "🥷 <b>Вор в законе</b> — бесплатные кражи\n"
            "😷 <b>Респиратор</b> — без обычных карт!"
        )
        await broadcast(text, "groups")

async def info_group_reminder_task():
    tips = [
        "🍂 <b>Сезоны и Амбиции</b>\nКопите очки, монеты и карты для повышения Амбиций! В конце сезона инвентари сбрасываются в обмен на 🍂.",
        "🥷 <b>Кражи карт</b>\nОтветьте на сообщение другого игрока командой <code>/steal</code>, чтобы украсть карту! Стоит 1 🍂.",
        "🤖 <b>Свой бот</b>\nНапишите главному боту в ЛС команду <code>/addbot ВАШ_ТОКЕН</code> (от @BotFather), и вы получите точно такого же бота для своей группы абсолютно бесплатно!"
    ]
    idx = 0
    while True:
        await asyncio.sleep(random.randint(3600, 7200))
        await broadcast(tips[idx % len(tips)], "groups")
        idx += 1

async def channel_promo_task():
    while True:
        await asyncio.sleep(random.randint(3600, 7200))
        text = (
            "📰 <b>Следи за обновлениями бота!</b>\n\n"
            "Хочешь первым узнавать о добавлении новых карт, запуске глобальных эвентов с шансом <b>x2</b> и других крутых фишках?\n\n"
            "Обязательно подписывайся на официальный канал проекта:\n"
            "👉 <b><a href='https://t.me/L1meYT'>L1meYT — Подписаться</a></b>\n\n"
            "<i>✨ Играй, собирай редкие карты и будь в курсе всех новостей!</i>"
        )
        await broadcast(text, "private")

async def host_promo_task():
    while True:
        await asyncio.sleep(random.randint(3600, 7200))
        text = (
            "🤖 <b>Создай своего собственного бота-коллекционера!</b>\n\n"
            "Понравилась игра? Ты можешь абсолютно бесплатно запустить <b>свою личную версию</b> этого бота со своими уникальными картами, шансами и экономикой!\n\n"
            "<b>Как подключить своего бота:</b>\n"
            "1️⃣ Зайди в официального бота @BotFather и нажми <code>/newbot</code>.\n"
            "2️⃣ Следуй инструкциям и скопируй полученный HTTP API Токен.\n"
            "3️⃣ Напиши <b>мне в личные сообщения</b> команду в формате:\n"
            "👉 <code>/addbot ВАШ_ТОКЕН</code> (Стоимость: 5 ⭐️)\n\n"
            "⚙️ Ваш бот запустится мгновенно и начнет работать 24/7. Вы автоматически станете его Главным Администратором (👑). База данных будет полностью чистой — добавляй карты через меню и приглашай друзей!\n\n"
            "<i>🚀 Построй свою коллекционную империю!</i>"
        )
        await broadcast(text, "all")

# --- МЕНЮ КОМАНД И ОБНОВЛЕНИЯ ---
def get_main_keyboard(user_id):
    if user_id in ADMINS:
        builder = ReplyKeyboardBuilder()
        builder.button(text="➕ Добавить карточку")
        builder.button(text="🗑 Удалить карточку")
        builder.adjust(2)
        return builder.as_markup(resize_keyboard=True)
    return types.ReplyKeyboardRemove()

async def set_commands(bot: Bot):
    group_commands = [
        BotCommand(command="profile", description="Профиль 👤"),
        BotCommand(command="index", description="Индекс карт 📚"),
        BotCommand(command="shinyindex", description="Shiny Индекс ✨"),
        BotCommand(command="enchants", description="Энчанты 🔮"),
        BotCommand(command="getcard", description="Тянуть карту 🃏"),
        BotCommand(command="cards", description="Инвентарь 🎴"),
        BotCommand(command="stavka", description="Ставка 💰"),
        BotCommand(command="gift", description="Подарить 🎁"),
        BotCommand(command="steal", description="Украсть 🥷"),
        BotCommand(command="premiumshop", description="Магазин ⭐️"),
        BotCommand(command="topcard", description="Топ карт 🏆"),
        BotCommand(command="topmoney", description="Топ по монетам 💰"),
        BotCommand(command="toppoint", description="Топ по очкам ✨"),
        BotCommand(command="topseason", description="Топ сезонов 🍂"),
        BotCommand(command="help", description="Помощь ❓")
    ]
    
    if IS_CHILD:
        private_commands = group_commands
    else:
        private_commands = [
            BotCommand(command="addbot", description="Создать бота 🤖")
        ] + group_commands
    
    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

async def update_chances_and_points(cards):
    total_weight = sum(c["weight"] for c in cards)
    if total_weight == 0: 
        return
    for c in cards:
        c["name"] = re.sub(r'(?i)shiny\s*', '', c.get("name", "")).strip()
        c["percent"] = round((c["weight"] / total_weight) * 100, 6)
        r = get_rarity(c["weight"])
        if c.get("rarity") != r or "money" not in c:
            c["rarity"] = r
            c["points"] = get_points_for_rarity(r)
            c["money"] = get_money_for_rarity(r)

async def auto_sort_index():
    cards = load_cards()
    if not cards: 
        return
    cards.sort(key=lambda x: x['weight'], reverse=True)
    mapping = {}
    new_cards = []
    for i, c in enumerate(cards):
        mapping[c['id']] = i + 1
        c['id'] = i + 1
        new_cards.append(c)
        
    async with aiosqlite.connect(DB_FILE) as db:
        for old_id, new_id in mapping.items():
            await db.execute("UPDATE OR REPLACE user_inventory SET card_id = ? WHERE card_id = ?", (new_id + 1000000, old_id))
        await db.execute("UPDATE OR REPLACE user_inventory SET card_id = card_id - 1000000 WHERE card_id >= 1000000")
        await db.commit()
        
    await update_chances_and_points(new_cards)
    save_cards(new_cards)


# =======================================================
# --- АДМИНСКИЕ КНОПКИ FSM (СТРОГО В НАЧАЛЕ ХЕНДЛЕРОВ) ---
# =======================================================

@dp.message(lambda msg: msg.text and msg.text.strip() == "➕ Добавить карточку", StateFilter('*'))
async def start_add(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    await message.answer("Отправьте фото для новой карты:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddCardStates.waiting_for_photo)

@dp.message(StateFilter(AddCardStates.waiting_for_photo), F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Введите название карты:")
    await state.set_state(AddCardStates.waiting_for_name)

@dp.message(StateFilter(AddCardStates.waiting_for_name), F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите вес шанса (от 0.005 до 99):")
    await state.set_state(AddCardStates.waiting_for_weight)

@dp.message(StateFilter(AddCardStates.waiting_for_weight), F.text)
async def process_weight(message: types.Message, state: FSMContext):
    try: 
        w = float(message.text.replace(',', '.'))
    except Exception: 
        return await message.answer("❌ Ошибка! Введите число.")
        
    if not (0.005 <= w <= 99): 
        return await message.answer("⚠️ Выход за пределы! Укажите вес строго от 0.005 до 99:")
        
    await state.update_data(weight=w)
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT cat_id, name FROM categories") as cursor: 
            cats = await cursor.fetchall()
            
    if not cats:
        await state.update_data(category_id=None)
        await finish_card_creation(message, state, message.from_user)
    else:
        kb = InlineKeyboardBuilder()
        for cid, cname in cats: 
            kb.button(text=cname, callback_data=f"cat_sel_{cid}")
            
        kb.button(text="⏭ Пропустить", callback_data="cat_skip")
        kb.adjust(1)
        await message.answer("Выберите категорию:", reply_markup=kb.as_markup())
        await state.set_state(AddCardStates.waiting_for_category)

@dp.callback_query(StateFilter(AddCardStates.waiting_for_category))
async def process_category(call: types.CallbackQuery, state: FSMContext):
    if call.data == "cat_skip": 
        await state.update_data(category_id=None)
    elif call.data.startswith("cat_sel_"): 
        category_id = int(call.data.split("_")[2])
        await state.update_data(category_id=category_id)
        
    await call.message.delete()
    await finish_card_creation(call.message, state, call.from_user)

async def finish_card_creation(message, state, user):
    data = await state.get_data()
    cards = load_cards()
    
    if len(cards) > 0:
        new_id = max([c['id'] for c in cards]) + 1
    else:
        new_id = 1
    
    card_name = data["name"]
    photo_id = data["photo"]
    weight = data["weight"]
    category_id = data.get("category_id")
    
    cards.append({
        "id": new_id, 
        "photo": photo_id, 
        "name": card_name, 
        "points": 0, 
        "money": 0, 
        "weight": weight, 
        "percent": 0.0, 
        "rarity": "", 
        "category_id": category_id
    })
    
    save_cards(cards)
    await auto_sort_index()
    
    updated_cards = load_cards()
    final_card = None
    for c in updated_cards:
        if c["name"] == card_name and c["weight"] == weight:
            final_card = c
            break
    
    if final_card:
        admin_text = (
            f"🆕 В базу добавлена новая карта!\n\n"
            f"🃏 <b>{final_card['name']}</b> (ID: <code>{final_card['id']}</code>)\n"
            f"💎 Редкость • {final_card['rarity']}\n"
            f"✨ Очки • {final_card['points']}\n"
            f"💰 Монеты • {final_card['money']}\n"
            f"🎲 Шанс: {fmt_percent(final_card['percent'])}%\n\n"
            f"👤 Добавил: <a href='tg://user?id={user.id}'>{user.full_name}</a>"
        )
        for admin_id in ADMINS:
            try:
                reply_kb = get_main_keyboard(admin_id) if admin_id == user.id else None
                await bot.send_photo(
                    chat_id=admin_id, 
                    photo=photo_id, 
                    caption=admin_text, 
                    parse_mode="HTML", 
                    reply_markup=reply_kb
                )
            except Exception:
                pass
    else:
        try:
            await bot.send_message(user.id, "✅ Карта успешно добавлена!", reply_markup=get_main_keyboard(user.id))
        except Exception:
            pass
            
    await state.clear()

@dp.message(lambda msg: msg.text and msg.text.strip() == "🗑 Удалить карточку", StateFilter('*'))
async def start_del(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
        
    await state.clear()
    await message.answer("Введите ID карт для удаления (через пробел):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(DeleteCardStates.waiting_for_id)

@dp.message(StateFilter(DeleteCardStates.waiting_for_id), F.text)
async def process_del(message: types.Message, state: FSMContext):
    tids_str = message.text.split()
    tids = []
    for x in tids_str:
        if x.isdigit():
            tids.append(int(x))
            
    cards = load_cards()
    new_cards = []
    deleted_ids = []
    
    for c in cards:
        if c['id'] not in tids:
            new_cards.append(c)
        else:
            deleted_ids.append(c['id'])
    
    if len(new_cards) == len(cards):
        await message.answer("❌ Карты не найдены.", reply_markup=get_main_keyboard(message.from_user.id))
    else:
        async with aiosqlite.connect(DB_FILE) as db:
            for did in deleted_ids:
                await db.execute("DELETE FROM user_inventory WHERE card_id = ?", (did,))
            await db.commit()
            
        save_cards(new_cards)
        await auto_sort_index()
        await message.answer(f"✅ Удалено карт: {len(deleted_ids)} (вместе с их Shiny и энчантами у всех игроков!)", reply_markup=get_main_keyboard(message.from_user.id))
        
    await state.clear()

# =======================================================
# --- ИГРОВЫЕ И АДМИНСКИЕ КОМАНДЫ ---
# =======================================================

@dp.message(Command("start"), StateFilter('*'))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Бот готов к работе.\nИспользуйте меню команд слева от поля ввода для игры.", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(Command("help"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(помощь|хелп|help)\s*$', msg.text), StateFilter('*'))
async def cmd_help(message: types.Message, state: FSMContext):
    await state.clear()
    txt = (
        "📖 <b>ИНСТРУКЦИЯ К ИГРЕ:</b>\n\n"
        "🎮 <b>ОСНОВНЫЕ КОМАНДЫ:</b>\n"
        "▫️ <code>/getcard</code> — Испытать удачу и выбить случайную карту. Доступно раз в 60 минут (для Premium - 54 мин). Шанс на ✨Shiny карту: 1%. Шанс на 🔮Энчант: 20%.\n"
        "▫️ <code>/cards</code> — Откроет ваш инвентарь со всеми собранными картами и их зачарованиями.\n"
        "▫️ <code>/profile</code> — Ваша статистика (ID, очки, монеты, амбиции, сезонные монеты, статусы баффов).\n"
        "▫️ <code>/index</code> — Полный список всех обычных карт в боте.\n"
        "▫️ <code>/shinyindex</code> — Список существующих ✨Shiny версий карт.\n"
        "▫️ <code>/enchants</code> — Индекс всех 🔮Зачарований и их множителей.\n\n"
        "🤝 <b>ВЗАИМОДЕЙСТВИЕ:</b>\n"
        "▫️ <code>/gift [ID карты] [Юзернейм или Реплай] [ID энчанта(опц)]</code> — Подарить карту игроку. Если вы хотите передать зачарованную карту, обязательно укажите ID энчанта третьим параметром.\n"
        "▫️ <code>/steal</code> — Ответьте этой командой на сообщение игрока, чтобы попытаться случайным образом выкрасть у него карту! (Цена: 1 🍂)\n"
        "▫️ <code>/stavka [сумма]</code> — Сделать ставку на активном аукционе.\n\n"
        "🛍 <b>МАГАЗИН И ЭКОНОМИКА:</b>\n"
        "▫️ <code>/premiumshop</code> (писать в ЛС бота) — Магазин баффов (Premium, Щит от краж, Вор, Респиратор). Можно купить за Звёзды (⭐️) или за Опыт (✨).\n\n"
        "🏆 <b>ТОПЫ И СЕЗОНЫ:</b>\n"
        "▫️ <code>/topcard</code>, <code>/topmoney</code>, <code>/toppoint</code>, <code>/topseason</code> — Доски лидеров.\n"
        "<i>В конце каждого сезона ваши амбиции сбрасываются и конвертируются в 🍂 Сезонные монеты!</i>\n\n"
    )
    
    if not IS_CHILD:
        txt += "🤖 <b>СВОЙ БОТ:</b>\n▫️ <code>/addbot [ТОКЕН]</code> — Создать и запустить свою личную версию бота через @BotFather за 5 ⭐️.\n"
        
    if message.from_user.id in ADMINS:
        txt += (
            "\n🛠 <b>АДМИНСКИЕ КОМАНДЫ:</b>\n"
            "▫️ <code>/newadmin [ID]</code>, <code>/deladmin [ID]</code>, <code>/admins</code> — Управление админами.\n"
            "▫️ <code>/globalmessage [текст]</code> — Глобальная рассылка во все группы и ЛС.\n"
            "▫️ <code>/reset</code> — Моментально завершить сезон (вайп).\n"
            "▫️ <code>/setwipe [часы]</code> — Поставить таймер на вайп.\n"
            "▫️ <code>/cancelwipe</code> — Отменить таймер вайпа.\n"
            "▫️ <code>/resetcards</code> — Удалить ВООБЩЕ ВСЕ карты из базы.\n"
            "▫️ <code>/iconchange [ID]</code> — Изменить картинку у карты.\n"
            "▫️ <code>/createauc [ID] [цена] [шаг] [ID энчанта(опц)]</code> — Создать аукцион.\n"
            "▫️ <code>/stopauc</code> — Отменить аукцион.\n"
            "▫️ <code>/newenchant [назв] [множ очки] [множ монеты] [вес]</code> — Добавить новый энчант.\n"
            "▫️ <code>/delenchant [ID]</code> — Удалить энчант.\n"
            "▫️ <code>/category</code>, <code>/addcategory</code>, <code>/addcatunit</code>, <code>/delcatunit</code> — Управление категориями.\n"
            "▫️ <code>/luckevent</code>, <code>/cooldownevent</code>, <code>/shinyevent [множ] [минуты]</code> — Запуск эвентов.\n"
            "▫️ <code>/stopevents</code> — Выключить все эвенты.\n"
        )
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("globalmessage"), StateFilter('*'))
async def cmd_globalmessage(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
    if not command.args: 
        return await message.answer("Формат: /globalmessage [Ваш текст]")
        
    await broadcast(f"📢 <b>Сообщение от администрации:</b>\n\n{command.args}", "all")
    await message.answer("✅ Глобальное сообщение успешно отправлено во все чаты и личные сообщения!")

@dp.message(Command("newenchant"), StateFilter('*'))
async def cmd_newenchant(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
    if not command.args: 
        return await message.answer("Формат: /newenchant [Название] [Множ. очков] [Множ. монет] [Вес 0.01-99]\nПример: /newenchant Огненный 1.5 2.0 50")
        
    args = command.args.split()
    if len(args) < 4: 
        return await message.answer("Слишком мало аргументов.")
        
    try:
        weight = float(args[-1])
        mon_m = float(args[-2])
        pts_m = float(args[-3])
        name = " ".join(args[:-3])
        
        if not (0.01 <= weight <= 99): 
            return await message.answer("Вес должен быть от 0.01 до 99.")
            
        enchants = load_enchants()
        
        if len(enchants) > 0:
            new_id = max([e['id'] for e in enchants]) + 1
        else:
            new_id = 1
            
        enchants.append({
            "id": new_id, 
            "name": name, 
            "mult_pts": pts_m, 
            "mult_money": mon_m, 
            "weight": weight, 
            "percent": 0.0
        })
        save_enchants(enchants)
        await message.answer(f"✅ Энчант <b>{name}</b> (ID: {new_id}) успешно добавлен!", parse_mode="HTML")
    except Exception:
        await message.answer("Ошибка в значениях. Убедитесь, что множители и вес — числа.")

@dp.message(Command("delenchant"), StateFilter('*'))
async def cmd_delenchant(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
    if not command.args or not command.args.isdigit(): 
        return await message.answer("Формат: /delenchant [ID]")
        
    e_id = int(command.args)
    enchants = load_enchants()
    new_enchants = []
    
    for e in enchants:
        if e['id'] != e_id:
            new_enchants.append(e)
            
    if len(new_enchants) == len(enchants): 
        return await message.answer("❌ Энчант не найден.")
        
    save_enchants(new_enchants)
    await message.answer(f"✅ Энчант удален.")

@dp.message(Command("enchants"), StateFilter('*'))
async def cmd_enchants(message: types.Message, state: FSMContext):
    await state.clear()
    enchants = load_enchants()
    if not enchants: 
        return await message.answer("В боте пока нет зачарований.")
        
    txt = "🔮 <b>Индекс Зачарований (Энчантов):</b>\n\n"
    
    sorted_enchants = sorted(enchants, key=lambda x: x['weight'], reverse=True)
    for e in sorted_enchants:
        txt += f"<b>{e['id']}. {e['name']}</b>\n✨ Очки: x{e['mult_pts']} | 💰 Монеты: x{e['mult_money']}\n🎲 Шанс прока: {fmt_percent(e['percent'])}%\n━━━━━━━━━━━━━━━━━━\n"
        
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("profile"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(👤 профиль|профиль)\s*$', msg.text), StateFilter('*'))
async def view_profile(message: types.Message, state: FSMContext):
    await state.clear()
    
    if message.from_user.username:
        user_identifier = f"@{message.from_user.username}"
    else:
        user_identifier = message.from_user.full_name
        
    user_id = message.from_user.id
    
    cards = load_cards()
    total_cards_count = len(cards)
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(DISTINCT card_id) FROM user_inventory WHERE user_id = ?", (user_id,)) as cursor:
            unique_row = await cursor.fetchone()
            unique_cards_count = unique_row[0]
            
        async with db.execute("SELECT SUM(count) FROM user_inventory WHERE user_id = ?", (user_id,)) as cursor:
            tc_row = await cursor.fetchone()
            total_cards = tc_row[0] if tc_row and tc_row[0] else 0
            
        async with db.execute("SELECT IFNULL(points, 0), IFNULL(money, 0), IFNULL(is_premium, 0), IFNULL(season_money, 0.0), IFNULL(has_shield, 0), IFNULL(has_thief, 0), IFNULL(has_respirator, 0), IFNULL(max_ambitions, 0) FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            
            if not row: 
                return await message.answer("Профиль пуст.")
                
            p, m, is_premium, sm, h_s, h_t, h_r, max_amb = row
            curr_amb = int((p / 100) + (m / 1000) + total_cards)
            actual_max_amb = max(curr_amb, max_amb)
            
            if curr_amb > max_amb:
                await db.execute("UPDATE users SET max_ambitions = ? WHERE user_id = ?", (curr_amb, user_id))
                await db.commit()
                
            buffs = []
            if is_premium: buffs.append("💎 PREMIUM")
            if h_s: buffs.append("🛡 Щит")
            if h_t: buffs.append("🥷 Вор")
            if h_r: buffs.append("😷 Респиратор")
            
            if buffs:
                buffs_str = " | ".join(buffs)
            else:
                buffs_str = "Нет"
            
            profile_text = (
                f"Профиль «{user_identifier}»\n"
                f"🌟 Статусы: <b>{buffs_str}</b>\n\n"
                f"🔎 ID • <code>{user_id}</code>\n"
                f"🃏 Карт • {unique_cards_count} из {total_cards_count} (Всего: {total_cards})\n"
                f"✨ Очки • {p}\n"
                f"💰 Монеты • {m}\n\n"
                f"🔥 Амбиции • {actual_max_amb} ({curr_amb})\n"
                f"🍂 Сезонные монеты • {sm:.1f}"
            )
            await message.answer(profile_text, parse_mode="HTML")

@dp.message(Command("index"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(📚 индекс|индекс)\s*$', msg.text), StateFilter('*'))
async def view_index(message: types.Message, state: FSMContext):
    await state.clear()
    cards = load_cards()
    if not cards: 
        return await message.answer("Карт нет.")
        
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT card_id FROM user_inventory WHERE user_id = ?", (message.from_user.id,)) as cursor:
            rows = await cursor.fetchall()
            opened_ids = [r[0] for r in rows]
            
        async with db.execute("SELECT card_id, SUM(count) FROM user_inventory GROUP BY card_id") as cursor:
            rows = await cursor.fetchall()
            global_counts = {r[0]: r[1] for r in rows}
            
        async with db.execute("SELECT cat_id, name FROM categories") as cursor:
            cats_db = await cursor.fetchall()
            
    cat_map = {row[0]: row[1] for row in cats_db}
    cat_map[None] = "Стандартная"
    
    grouped_cards = {}
    for c in cards:
        cid = c.get("category_id")
        if cid not in grouped_cards:
            grouped_cards[cid] = []
        grouped_cards[cid].append(c)

    header = "📚 <b>Индекс карточек:</b>\n\n"
    msg_chunk = header
    
    keys = [k for k in grouped_cards.keys() if k is not None]
    keys.sort()
    cat_order = [None] + keys

    for cid in cat_order:
        if cid not in grouped_cards: 
            continue
            
        cat_name = cat_map.get(cid, "Стандартная")
        cat_header = f"🏷 <b>Категория: {cat_name}</b>\n" + "➖"*10 + "\n"
        
        if len(msg_chunk) + len(cat_header) > 3900:
            try: 
                await message.answer(msg_chunk, parse_mode="HTML")
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                await message.answer(msg_chunk, parse_mode="HTML")
            await asyncio.sleep(0.5)
            msg_chunk = ""
            
        msg_chunk += cat_header
        
        for c in grouped_cards[cid]:
            is_opened = (message.from_user.id in ADMINS) or (c['id'] in opened_ids)
            
            if is_opened:
                name = c['name']
                rarity = c.get('rarity', get_rarity(c['weight']))
            else:
                name = "???"
                rarity = "???"
                
            pts = c.get('points', 0)
            mny = c.get('money', 0)
            total_exists = global_counts.get(c['id'], 0)
            
            item_text = f"<b>{c['id']}. {name}</b>\n💎 {rarity} | 🎲 {fmt_percent(c['percent'])}%\n✨ Очки: {pts} | 💰 Монеты: {mny}\n💫Существует: {total_exists}💫\n━━━━━━━━━━━━━━━━━━\n"
            
            if len(msg_chunk) + len(item_text) > 3900:
                try: 
                    await message.answer(msg_chunk, parse_mode="HTML")
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await message.answer(msg_chunk, parse_mode="HTML")
                await asyncio.sleep(0.5)
                msg_chunk = ""
                
            msg_chunk += item_text
            
        msg_chunk += "\n"
        
    if msg_chunk and msg_chunk.strip() != "📚 <b>Индекс карточек:</b>":
        try: 
            await message.answer(msg_chunk, parse_mode="HTML")
        except Exception: 
            pass

@dp.message(Command("shinyindex"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(✨ shiny индекс|shiny индекс|shinyindex)\s*$', msg.text), StateFilter('*'))
async def view_shiny_index(message: types.Message, state: FSMContext):
    await state.clear()
    cards = load_cards()
    if not cards: 
        return await message.answer("Карт нет.")
        
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT card_id FROM user_inventory WHERE user_id = ? AND is_shiny = 1", (message.from_user.id,)) as cursor:
            rows = await cursor.fetchall()
            opened_ids = [r[0] for r in rows]
            
        async with db.execute("SELECT card_id, SUM(count) FROM user_inventory WHERE is_shiny = 1 GROUP BY card_id") as cursor:
            rows = await cursor.fetchall()
            global_counts = {r[0]: r[1] for r in rows}
            
        async with db.execute("SELECT cat_id, name FROM categories") as cursor:
            cats_db = await cursor.fetchall()
            
    cat_map = {row[0]: row[1] for row in cats_db}
    cat_map[None] = "Стандартная"
    
    grouped_cards = {}
    for c in cards:
        cid = c.get("category_id")
        if cid not in grouped_cards:
            grouped_cards[cid] = []
        grouped_cards[cid].append(c)

    header = "✨ <b>Shiny Индекс карточек:</b>\n\n"
    msg_chunk = header
    
    keys = [k for k in grouped_cards.keys() if k is not None]
    keys.sort()
    cat_order = [None] + keys

    for cid in cat_order:
        if cid not in grouped_cards: continue
        cat_name = cat_map.get(cid, "Стандартная")
        cat_header = f"🏷 <b>Категория: {cat_name}</b>\n" + "➖"*10 + "\n"
        
        if len(msg_chunk) + len(cat_header) > 3900:
            try: 
                await message.answer(msg_chunk, parse_mode="HTML")
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                await message.answer(msg_chunk, parse_mode="HTML")
            await asyncio.sleep(0.5)
            msg_chunk = ""
            
        msg_chunk += cat_header
        
        for c in grouped_cards[cid]:
            is_opened = (message.from_user.id in ADMINS) or (c['id'] in opened_ids)
            
            if is_opened:
                name = c['name']
                rarity = c.get('rarity', get_rarity(c['weight']))
            else:
                name = "???"
                rarity = "???"
                
            pts = int(c.get('points', 0) * 1.25)
            mny = int(c.get('money', 0) * 1.25)
            shiny_chance = c['percent'] * 0.01 
            total_exists = global_counts.get(c['id'], 0)
            display_id = c['id'] + 1000000

            item_text = f"<b>{display_id}. {name}</b> ⭐️Shiny⭐️\n💎 {rarity} | 🎲 {fmt_percent(shiny_chance)}%\n✨ Очки: {pts} | 💰 Монеты: {mny}\n💫Существует: {total_exists}💫\n━━━━━━━━━━━━━━━━━━\n"
            
            if len(msg_chunk) + len(item_text) > 3900:
                try: 
                    await message.answer(msg_chunk, parse_mode="HTML")
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await message.answer(msg_chunk, parse_mode="HTML")
                await asyncio.sleep(0.5)
                msg_chunk = ""
                
            msg_chunk += item_text
            
        msg_chunk += "\n"
        
    if msg_chunk and msg_chunk.strip() != "✨ <b>Shiny Индекс карточек:</b>":
        try: 
            await message.answer(msg_chunk, parse_mode="HTML")
        except Exception: 
            pass

@dp.message(Command("cards"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(🎴 мои карты|мои карты|карты)\s*$', msg.text), StateFilter('*'))
async def cmd_cards(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT card_id, is_shiny, enchant_id, count FROM user_inventory WHERE user_id = ?", (message.from_user.id,)) as cursor:
            rows = await cursor.fetchall()
            
    if not rows: 
        return await message.answer("🎴 У тебя пока нет ни одной карты. Используй /getcard или напиши 'крутка'!")
        
    cards = load_cards()
    card_dict = {c['id']: c for c in cards}
    
    enchants = load_enchants()
    ench_dict = {e['id']: e['name'] for e in enchants}
    
    header = f"🎴 <b>Коллекция {message.from_user.full_name}:</b>\n\n"
    msg_chunk = header
    
    for cid, is_shiny, enchant_id, count in rows:
        if cid in card_dict:
            c = card_dict[cid]
            rarity = c.get('rarity', '???')
            
            if is_shiny:
                shiny_tag = " ⭐️Shiny⭐️"
                display_id = cid + 1000000
            else:
                shiny_tag = ""
                display_id = cid
                
            if enchant_id > 0:
                ench_tag = f"\n🔮 Энчант: {ench_dict.get(enchant_id, f'ID {enchant_id}')}"
            else:
                ench_tag = ""
                
            item_text = f"<b>{display_id}.</b> 🃏 <b>{c['name']}</b>{shiny_tag}{ench_tag}\n💎 {rarity} | 📦 В наличии: <code>x{count}</code>\n━━━━━━━━━━━━━━━━━━\n"
            
            if len(msg_chunk) + len(item_text) > 3900:
                try: 
                    await message.answer(msg_chunk, parse_mode="HTML")
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try: 
                        await message.answer(msg_chunk, parse_mode="HTML")
                    except Exception: 
                        pass
                await asyncio.sleep(0.5)
                msg_chunk = ""
                
            msg_chunk += item_text
            
    if msg_chunk and msg_chunk != header:
        try: 
            await message.answer(msg_chunk, parse_mode="HTML")
        except Exception: 
            pass

@dp.message(Command("getcard"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(тянуть карту 🃏|крутка|тянуть карту)\s*$', msg.text), StateFilter('*'))
async def get_card_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    cards = load_cards()
    if not cards: 
        return await message.answer("Карт в базе нет.")
    
    full_name = message.from_user.full_name
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT last_get, is_premium, IFNULL(has_respirator, 0) FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            
            if row:
                is_premium = row[1]
                has_respirator = row[2]
            else:
                is_premium = 0
                has_respirator = 0
            
            cd_mult = events["cooldown"]["mult"] if events["cooldown"]["end_time"] else 1.0
            
            if cd_mult > 0:
                base_cd = 60.0 / cd_mult
            else:
                base_cd = 60.0
                
            if is_premium: 
                base_cd *= 0.9 
            
            if row and row[0]:
                last_t = datetime.fromisoformat(row[0])
                if datetime.now() < last_t + timedelta(minutes=base_cd):
                    wait = (last_t + timedelta(minutes=base_cd) - datetime.now())
                    try:
                        return await message.reply(f"⏳ Жди {int(wait.total_seconds() // 60)} мин. {int(wait.total_seconds() % 60)} сек.")
                    except Exception: 
                        return
        
        if has_respirator == 1:
            available_cards = []
            for c in cards:
                if c['weight'] < 70:
                    available_cards.append(c)
        else:
            available_cards = cards
            
        if not available_cards: 
            available_cards = cards

        weights = []
        for c in available_cards:
            weights.append(c['weight'])
            
        luck_buff = events["luck"]["mult"] if events["luck"]["end_time"] else 1.0
        
        if is_premium:
            luck = 1.5 * luck_buff
        else:
            luck = 1.0 * luck_buff
        
        rolls = int(luck)
        if random.random() < (luck - int(luck)): 
            rolls += 1
            
        rolls = max(1, rolls)
            
        drawn_cards = []
        for _ in range(rolls):
            drawn_cards.append(random.choices(available_cards, weights=weights, k=1)[0])
            
        card = min(drawn_cards, key=lambda c: c['weight'])
            
        if 'rarity' in card:
            actual_rarity = card['rarity']
        else:
            actual_rarity = get_rarity(card['weight'])
            
        base_points = card.get('points', 0)
        base_money = card.get('money', 0)
        
        cat_name = "Стандартная"
        exp_mult = 1.0
        money_mult = 1.0
        max_inv = None
        
        cat_id = card.get("category_id")
        
        if cat_id is not None:
            async with db.execute("SELECT name, exp_mult, money_mult, max_inv FROM categories WHERE cat_id = ?", (cat_id,)) as cursor:
                cat_row = await cursor.fetchone()
            if cat_row: 
                cat_name = cat_row[0]
                exp_mult = cat_row[1]
                money_mult = cat_row[2]
                max_inv = cat_row[3]
                
        if max_inv is not None:
            async with db.execute("SELECT SUM(count) FROM user_inventory WHERE user_id = ? AND card_id = ?", (message.from_user.id, card['id'])) as cursor:
                curr_count_row = await cursor.fetchone()
            curr_count = curr_count_row[0] if curr_count_row and curr_count_row[0] else 0
            
            if curr_count >= max_inv:
                try: 
                    await message.answer(f"У тебя уже максимум карт <b>{card['name']}</b> ({max_inv} шт.)!\nКарта конвертирована в очки и монеты.", parse_mode="HTML")
                except Exception: 
                    pass
                await db.execute('''UPDATE users SET points = IFNULL(points, 0) + ?, money = IFNULL(money, 0) + ?, last_get = ? WHERE user_id = ?''', (base_points, base_money, datetime.now().isoformat(), message.from_user.id))
                await db.commit()
                await update_max_ambitions(message.from_user.id, db)
                return
        
        shiny_buff = events["shiny"]["mult"] if events["shiny"]["end_time"] else 1.0
        shiny_chance = 0.01 * shiny_buff
        
        if random.random() <= shiny_chance:
            is_shiny = 1
        else:
            is_shiny = 0
        
        enchant_id = 0
        enchant_name = ""
        enchant_mult_pts = 1.0
        enchant_mult_money = 1.0
        
        enchants = load_enchants()
        
        if enchants and random.random() <= 0.20:
            e_weights = []
            for e in enchants:
                e_weights.append(e['weight'])
                
            chosen_enchant = random.choices(enchants, weights=e_weights, k=1)[0]
            enchant_id = chosen_enchant['id']
            enchant_name = chosen_enchant['name']
            enchant_mult_pts = chosen_enchant['mult_pts']
            enchant_mult_money = chosen_enchant['mult_money']

        if is_shiny:
            actual_points = int(base_points * exp_mult * enchant_mult_pts * 1.25)
            actual_money = int(base_money * money_mult * enchant_mult_money * 1.25)
        else:
            actual_points = int(base_points * exp_mult * enchant_mult_pts)
            actual_money = int(base_money * money_mult * enchant_mult_money)
        
        if is_premium:
            premium_points_bonus = random.randint(1, 10)
            premium_money_bonus = int(actual_money * 0.1)
        else:
            premium_points_bonus = 0
            premium_money_bonus = 0
        
        final_points = actual_points + premium_points_bonus
        final_money = actual_money + premium_money_bonus
        
        await db.execute('''INSERT INTO user_inventory (user_id, card_id, is_shiny, enchant_id, count) VALUES (?, ?, ?, ?, 1) ON CONFLICT(user_id, card_id, is_shiny, enchant_id) DO UPDATE SET count = count + 1''', (message.from_user.id, card['id'], is_shiny, enchant_id))
        
        author_bonus_text = ""
        author_id = card.get("author_id")
        
        if author_id == message.from_user.id:
            sm_bonus = get_author_bonus(actual_rarity)
            if sm_bonus > 0:
                await db.execute("UPDATE users SET season_money = IFNULL(season_money, 0.0) + ? WHERE user_id = ?", (sm_bonus, message.from_user.id))
                author_bonus_text = f"\n🍂 Бонус создателя: <b>+{sm_bonus:.1f} СМ</b>!"

        await db.execute('''
            INSERT INTO users (user_id, points, money, cards_count, rarest_card_name, rarest_card_chance, last_get, full_name, is_premium) 
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET 
                points = IFNULL(points, 0) + EXCLUDED.points, money = IFNULL(money, 0) + EXCLUDED.money, cards_count = IFNULL(cards_count, 0) + 1, 
                last_get = EXCLUDED.last_get, full_name = EXCLUDED.full_name,
                rarest_card_name = CASE WHEN EXCLUDED.rarest_card_chance < rarest_card_chance THEN EXCLUDED.rarest_card_name ELSE rarest_card_name END, 
                rarest_card_chance = CASE WHEN EXCLUDED.rarest_card_chance < rarest_card_chance THEN EXCLUDED.rarest_card_chance ELSE rarest_card_chance END
        ''', (message.from_user.id, final_points, final_money, card['name'], card['weight'], datetime.now().isoformat(), full_name, is_premium))
        await db.commit()
        await update_max_ambitions(message.from_user.id, db)
    
    if message.from_user.username:
        user_name = f"@{message.from_user.username}"
    else:
        user_name = full_name
        
    if enchant_id > 0:
        enchant_txt = f"\n🔮 Энчант • {enchant_name}"
    else:
        enchant_txt = ""
        
    if is_shiny:
        shiny_txt = " ⭐️Shiny⭐️"
    else:
        shiny_txt = ""
        
    if is_premium and premium_points_bonus > 0:
        pts_str = f" (+{premium_points_bonus} 💎)"
    else:
        pts_str = ""
        
    if is_premium and premium_money_bonus > 0:
        money_str = f" (+{premium_money_bonus} 💎)"
    else:
        money_str = ""
        
    caption = (
        f"🎉 {user_name}, тебе выпала карта!\n\n"
        f"🃏{card['name']}🃏{shiny_txt}\n"
        f"⚙️ Категория • {cat_name}\n"
        f"💎 Редкость • {actual_rarity}\n"
        f"✨ Очки • {final_points}{pts_str}\n"
        f"💰 Монеты • {final_money}{money_str}"
        f"{enchant_txt}{author_bonus_text}"
    )
    
    try:
        await message.answer_photo(photo=card['photo'], caption=caption, parse_mode="HTML")
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await message.answer_photo(photo=card['photo'], caption=caption, parse_mode="HTML")
        except Exception:
            pass
    except Exception:
        pass

@dp.message(Command("category"), StateFilter('*'))
async def cmd_category(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
        
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM categories") as cursor: 
            rows = await cursor.fetchall()
            
    if not rows: 
        return await message.answer("Категорий нет.")
        
    txt = "🏷 <b>Категории:</b>\n\n"
    for r in rows:
        txt += f"ID: {r[0]} | <b>{r[1]}</b>\nEXP: x{r[2]} | Money: x{r[3]} | Max Inv: {r[4]}\n━━━━━━━━\n"
        
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("addcategory"), StateFilter('*'))
async def cmd_addcategory(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
        
    if not command.args: 
        return await message.answer("Формат: /addcategory Название | EXP множ | Money множ | Макс инв")
        
    args = []
    for x in command.args.split('|'):
        args.append(x.strip())
        
    if len(args) < 4: 
        return await message.answer("Формат: /addcategory Название | EXP множ | Money множ | Макс инв")
        
    try:
        name = args[0]
        exp_m = float(args[1])
        mon_m = float(args[2])
        max_i = int(args[3])
        
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT INTO categories (name, exp_mult, money_mult, max_inv) VALUES (?,?,?,?)", (name, exp_m, mon_m, max_i))
            await db.commit()
            
        await message.answer(f"✅ Категория {name} добавлена!")
    except Exception: 
        await message.answer("Ошибка в значениях!")

@dp.message(Command("addcatunit"), StateFilter('*'))
async def cmd_addcatunit(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
        
    if not command.args: 
        return await message.answer("Формат: /addcatunit [ID карты] [ID категории]")
        
    try:
        parts = command.args.split()
        c_id = int(parts[0])
        cat_id = int(parts[1])
        
        cards = load_cards()
        found = False
        
        for c in cards:
            if c['id'] == c_id:
                c['category_id'] = cat_id
                found = True
                break
                
        if not found: 
            return await message.answer("Карта не найдена.")
            
        save_cards(cards)
        await message.answer("✅ Категория назначена!")
    except Exception: 
        await message.answer("Ошибка формата.")

@dp.message(Command("delcatunit"), StateFilter('*'))
async def cmd_delcatunit(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
        
    if not command.args: 
        return await message.answer("Формат: /delcatunit [ID карты]")
        
    try:
        c_id = int(command.args)
        cards = load_cards()
        
        for c in cards:
            if c['id'] == c_id: 
                c['category_id'] = None
                
        save_cards(cards)
        await message.answer("✅ Категория снята с карты.")
    except Exception: 
        await message.answer("Ошибка формата.")

@dp.message(Command("iconchange"), StateFilter('*'))
async def cmd_iconchange(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if not command.args or not command.args.isdigit(): 
        return await message.answer("Использование: /iconchange [ID карты]")
        
    target_id = int(command.args)
    cards = load_cards()
    
    found = False
    for c in cards:
        if c['id'] == target_id:
            found = True
            break
            
    if not found: 
        return await message.answer(f"❌ Карта с ID {target_id} не найдена.")
        
    await state.update_data(card_id=target_id)
    await message.answer(f"Отправьте новое фото для карты ID {target_id}:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(ChangeIconStates.waiting_for_photo)

@dp.message(StateFilter(ChangeIconStates.waiting_for_photo), F.photo)
async def process_new_icon(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data['card_id']
    new_photo_id = message.photo[-1].file_id
    
    cards = load_cards()
    for c in cards:
        if c['id'] == target_id:
            c['photo'] = new_photo_id
            break
            
    save_cards(cards)
    await message.answer(f"✅ Фото карты ID {target_id} успешно обновлено!", reply_markup=get_main_keyboard(message.from_user.id))
    await state.clear()

@dp.message(Command("newadmin"), F.chat.type == "private", StateFilter('*'))
async def add_admin(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if not command.args or not command.args.isdigit(): 
        return
        
    new_id = int(command.args)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (new_id,))
        await db.commit()
        
    ADMINS.add(new_id)
    await message.answer(f"✅ {new_id} теперь админ.")

@dp.message(Command("deladmin"), F.chat.type == "private", StateFilter('*'))
async def delete_admin(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if command.args and command.args.isdigit():
        target_id = int(command.args)
    else:
        target_id = 0
        
    if target_id == SUPER_ADMIN_ID: 
        return
        
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('DELETE FROM admins WHERE user_id = ?', (target_id,))
        await db.commit()
        
    ADMINS.discard(target_id)
    await message.answer(f"🗑 Админ {target_id} удален.")

@dp.message(Command("luckevent"), StateFilter('*'))
async def cmd_luckevent(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if not command.args: 
        return await message.answer("Формат: /luckevent [множитель] [время в минутах]")
        
    try: 
        parts = command.args.split()
        mult = float(parts[0])
        minutes = int(parts[1])
    except Exception: 
        return await message.answer("Ошибка! Формат: /luckevent 2.5 60")
    
    now = datetime.now()
    events["luck"]["end_time"] = now + timedelta(minutes=minutes)
    events["luck"]["next_announce"] = now + timedelta(hours=1)
    events["luck"]["mult"] = mult
    events["luck"]["name"] = f"🍀 Удача x{mult}"
    
    save_events()
    await broadcast(f"🎉 <b>ГЛОБАЛЬНЫЙ ЭВЕНТ!</b> 🎉\nЗапущен эвент <b>{events['luck']['name']}</b> на {minutes} минут!", "all")

@dp.message(Command("shinyevent"), StateFilter('*'))
async def cmd_shinyevent(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if not command.args: 
        return await message.answer("Формат: /shinyevent [множитель] [время в минутах]")
        
    try: 
        parts = command.args.split()
        mult = float(parts[0])
        minutes = int(parts[1])
    except Exception: 
        return await message.answer("Ошибка! Формат: /shinyevent 2.5 60")
    
    now = datetime.now()
    events["shiny"]["end_time"] = now + timedelta(minutes=minutes)
    events["shiny"]["next_announce"] = now + timedelta(hours=1)
    events["shiny"]["mult"] = mult
    events["shiny"]["name"] = f"✨ Shiny Удача x{mult}"
    
    save_events()
    await broadcast(f"🎉 <b>ГЛОБАЛЬНЫЙ ЭВЕНТ!</b> 🎉\nЗапущен эвент <b>{events['shiny']['name']}</b> на {minutes} минут!\n\n<i>Шанс выбить Shiny карту увеличен в {mult} раз(а)!</i>", "all")


@dp.message(Command("cooldownevent"), StateFilter('*'))
async def cmd_cooldownevent(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if not command.args: 
        return await message.answer("Формат: /cooldownevent [множитель] [время в минутах]")
        
    try: 
        parts = command.args.split()
        mult = float(parts[0])
        minutes = int(parts[1])
    except Exception: 
        return await message.answer("Ошибка! Формат: /cooldownevent 2 60")
    
    now = datetime.now()
    events["cooldown"]["end_time"] = now + timedelta(minutes=minutes)
    events["cooldown"]["next_announce"] = now + timedelta(hours=1)
    events["cooldown"]["mult"] = mult
    events["cooldown"]["name"] = f"⚡ Ускорение x{mult}"
    
    save_events()
    await broadcast(f"🎉 <b>ГЛОБАЛЬНЫЙ ЭВЕНТ!</b> 🎉\nЗапущен эвент <b>{events['cooldown']['name']}</b> на {minutes} минут!", "all")

@dp.message(Command("stopevents"), StateFilter('*'))
async def cmd_stopevents(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    for key in events: 
        if key != "wipe":
            events[key]["end_time"] = None
            events[key]["next_announce"] = None
            
    save_events()
    await broadcast("🔴 <b>Все активные эвенты были досрочно завершены администратором!</b>", "all")

@dp.message(Command("resetcards"), StateFilter('*'))
async def cmd_resetcards(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    now = datetime.now()
    if resetcards_state["timer"] is None or now > resetcards_state["timer"] + timedelta(seconds=30):
        resetcards_state["count"] = 1
        resetcards_state["timer"] = now
        await message.answer("⚠️ Вызов УДАЛЕНИЯ ВСЕХ КАРТ (1/3). Введите /resetcards еще 2 раза в течение 30 секунд.")
    else:
        resetcards_state["count"] += 1
        if resetcards_state["count"] == 2: 
            await message.answer("⚠️ Вызов УДАЛЕНИЯ ВСЕХ КАРТ (2/3). Введите /resetcards еще 1 раз для старта.")
        elif resetcards_state["count"] >= 3:
            resetcards_state["count"] = 0
            resetcards_state["timer"] = None
            
            save_cards([])
            
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute("DELETE FROM user_inventory")
                await db.execute("UPDATE users SET cards_count = 0, rarest_card_name = 'Нет', rarest_card_chance = 100.0, max_ambitions = 0")
                await db.commit()
                
            await message.answer("✅ Абсолютно все карты удалены из базы и из инвентарей игроков!")

@dp.message(Command("reset"), StateFilter('*'))
async def cmd_reset(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    now = datetime.now()
    if reset_state["timer"] is None or now > reset_state["timer"] + timedelta(seconds=30):
        reset_state["count"] = 1
        reset_state["timer"] = now
        await message.answer("⚠️ Введите /reset еще 2 раза в течение 30 секунд для моментального вайпа.")
    else:
        reset_state["count"] += 1
        if reset_state["count"] == 2: 
            await message.answer("⚠️ Введите /reset еще 1 раз для старта сброса.")
        elif reset_state["count"] >= 3:
            reset_state["count"] = 0
            reset_state["timer"] = None
            await message.answer("⏳ Начинаю моментальный расчет амбиций и сброс сезона...")
            await perform_wipe()
            await message.answer("✅ Сброс завершен!")

@dp.message(Command("setwipe"), StateFilter('*'))
async def cmd_setwipe(message: types.Message, command: CommandObject, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if not command.args: 
        return await message.answer("Формат: /setwipe [часы]")
        
    try: 
        hours = float(command.args)
    except Exception: 
        return await message.answer("Укажите количество часов числом!")
    
    now = datetime.now()
    events["wipe"]["end_time"] = now + timedelta(hours=hours)
    events["wipe"]["next_announce"] = now + timedelta(hours=1)
    
    save_events()
    await broadcast(f"⚠️ <b>Внимание!</b> Администратор запустил таймер сброса сезона.\nВайп состоится через {hours} часов!", "all")

@dp.message(Command("cancelwipe"), StateFilter('*'))
async def cmd_cancelwipe(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: 
        return
    await state.clear()
    
    if events["wipe"]["end_time"]:
        events["wipe"]["end_time"] = None
        events["wipe"]["next_announce"] = None
        save_events()
        await broadcast("🛑 <b>Таймер сброса сезона был отменен администратором.</b> Игра продолжается!", "all")
    else:
        await message.answer("Таймер вайпа не запущен.")


@dp.message(Command("gift"), StateFilter('*'))
async def cmd_gift(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if not command.args: 
        return await message.answer("Формат: <code>/gift [ID карты] [Юзернейм] [ID энчанта (опц)]</code>\nИли ответом: <code>/gift [ID карты] [ID энчанта (опц)]</code>", parse_mode="HTML")
    
    args = command.args.split()
    if args[0].isdigit():
        input_id = int(args[0])
    else:
        input_id = 0
        
    if input_id == 0: 
        return await message.answer("Укажите правильный ID карты.")

    if input_id >= 1000000:
        is_shiny_gift = 1
    else:
        is_shiny_gift = 0
        
    if is_shiny_gift:
        real_card_id = input_id - 1000000
    else:
        real_card_id = input_id

    target_id = None
    target_name = "Игрок"
    enchant_id = 0
    
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.full_name
        if len(args) > 1 and args[1].isdigit(): 
            enchant_id = int(args[1])
    elif len(args) > 1:
        username = args[1].replace("@", "")
        if len(args) > 2 and args[2].isdigit(): 
            enchant_id = int(args[2])
            
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT user_id, full_name FROM users WHERE username = ?", (username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    target_id = row[0]
                    target_name = row[1]
                    
    if not target_id: 
        return await message.answer("Пользователь не найден в базе. Укажите @username или ответьте на его сообщение.")
        
    if target_id == message.from_user.id: 
        return await message.answer("❌ Нельзя подарить карту себе.")
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT count FROM user_inventory WHERE user_id=? AND card_id=? AND is_shiny=? AND enchant_id=? AND count>0 LIMIT 1", (message.from_user.id, real_card_id, is_shiny_gift, enchant_id)) as cursor: 
            row = await cursor.fetchone()
            
        if not row: 
            return await message.answer("❌ У вас нет такой версии этой карты (проверьте ID энчанта)!")
        
        await db.execute("UPDATE user_inventory SET count=count-1 WHERE user_id=? AND card_id=? AND is_shiny=? AND enchant_id=?", (message.from_user.id, real_card_id, is_shiny_gift, enchant_id))
        await db.execute("DELETE FROM user_inventory WHERE user_id=? AND count<=0", (message.from_user.id,))
        await db.execute("INSERT INTO user_inventory (user_id, card_id, is_shiny, enchant_id, count) VALUES (?, ?, ?, ?, 1) ON CONFLICT(user_id, card_id, is_shiny, enchant_id) DO UPDATE SET count=count+1", (target_id, real_card_id, is_shiny_gift, enchant_id))
        await db.commit()
    
    cards = load_cards()
    c_name = f"ID {real_card_id}"
    for c in cards:
        if c["id"] == real_card_id:
            c_name = c["name"]
            break
            
    if is_shiny_gift:
        shiny_text = " ⭐️Shiny⭐️"
    else:
        shiny_text = ""
        
    enchants = load_enchants()
    ench_dict = {e['id']: e['name'] for e in enchants}
    
    if enchant_id > 0:
        ench_text = f" 🔮[{ench_dict.get(enchant_id, f'ID {enchant_id}')}]"
    else:
        ench_text = ""
    
    await message.answer(f"🎁 Вы подарили карту <b>{c_name}</b>{shiny_text}{ench_text} игроку <b>{target_name}</b>!", parse_mode="HTML")
    try: 
        await bot.send_message(target_id, f"🎁 Игрок <b>{message.from_user.full_name}</b> подарил вам карту <b>{c_name}</b>{shiny_text}{ench_text}!", parse_mode="HTML")
    except Exception: 
        pass

@dp.message(Command("steal"), StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(украсть|своровать)\s*$', msg.text), StateFilter('*'))
async def cmd_steal(message: types.Message, state: FSMContext):
    await state.clear()
    if not message.reply_to_message: 
        return await message.answer("⚠️ Ответьте на сообщение игрока этой командой!")
        
    tid = message.reply_to_message.from_user.id
    if tid == message.from_user.id or message.reply_to_message.from_user.is_bot: 
        return await message.answer("❌ Нельзя!")
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT IFNULL(season_money,0), IFNULL(has_thief,0) FROM users WHERE user_id=?", (message.from_user.id,)) as cursor: 
            s_row = await cursor.fetchone()
            
        if not s_row or (s_row[0] < 1 and s_row[1] == 0): 
            return await message.answer("❌ Нужна 1 🍂 или статус Вор!")
        
        async with db.execute("SELECT last_stolen_from, IFNULL(has_shield,0), full_name FROM users WHERE user_id=?", (tid,)) as cursor: 
            t_row = await cursor.fetchone()
            
        if not t_row: 
            return await message.answer("❌ Игрок не найден.")
            
        if t_row[1] == 1: 
            return await message.answer("🛡 У игрока Щит!")
            
        if t_row[0]:
            lst = datetime.fromisoformat(t_row[0])
            if datetime.now() < lst + timedelta(hours=3): 
                return await message.answer("🛡 У игрока временный иммунитет!")
            
        async with db.execute("SELECT card_id, is_shiny, enchant_id, count FROM user_inventory WHERE user_id=? AND count>0", (tid,)) as cursor: 
            inv = await cursor.fetchall()
            
        if not inv: 
            return await message.answer("🤷 У игрока нет карт!")
        
        pool = []
        for cid, sh, eid, count in inv: 
            for _ in range(count):
                pool.append((cid, sh, eid))
                
        scid, ssh, seid = random.choice(pool)
        
        if s_row[1] == 0: 
            await db.execute("UPDATE users SET season_money=season_money-1 WHERE user_id=?", (message.from_user.id,))
            
        await db.execute("UPDATE users SET last_stolen_from=? WHERE user_id=?", (datetime.now().isoformat(), tid))
        await db.execute("UPDATE user_inventory SET count=count-1 WHERE user_id=? AND card_id=? AND is_shiny=? AND enchant_id=?", (tid, scid, ssh, seid))
        await db.execute("DELETE FROM user_inventory WHERE user_id=? AND count<=0", (tid,))
        await db.execute("INSERT INTO user_inventory (user_id, card_id, is_shiny, enchant_id, count) VALUES (?, ?, ?, ?, 1) ON CONFLICT(user_id, card_id, is_shiny, enchant_id) DO UPDATE SET count=count+1", (message.from_user.id, scid, ssh, seid))
        await db.commit()
        
    cards = load_cards()
    cname = f"ID {scid}"
    for c in cards:
        if c["id"] == scid:
            cname = c["name"]
            break
            
    if ssh:
        shiny_text = " ⭐️Shiny⭐️"
    else:
        shiny_text = ""
        
    enchants = load_enchants()
    ench_dict = {e['id']: e['name'] for e in enchants}
    
    if seid > 0:
        ench_text = f" 🔮[{ench_dict.get(seid, f'ID {seid}')}]"
    else:
        ench_text = ""
    
    await message.answer(f"🥷 Вы украли карту <b>{cname}</b>{shiny_text}{ench_text} у <b>{t_row[2]}</b>!", parse_mode="HTML")

@dp.message(Command("topcard"), StateFilter('*'))
async def cmd_topcard(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT u.full_name, SUM(i.count) as tc FROM users u JOIN user_inventory i ON u.user_id=i.user_id GROUP BY u.user_id ORDER BY tc DESC LIMIT 10") as cursor: 
            rows = await cursor.fetchall()
            
    if not rows: 
        return await message.answer("Топ пуст.")
        
    txt = "🏆 <b>Топ по картам:</b>\n\n"
    for i, r in enumerate(rows, 1):
        txt += f"<b>{i}.</b> {r[0]} — {r[1]} 🃏\n"
        
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("toppoint"), StateFilter('*'))
async def cmd_toppoint(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT full_name, points FROM users ORDER BY points DESC LIMIT 10") as cursor: 
            rows = await cursor.fetchall()
            
    if not rows: 
        return await message.answer("Топ пуст.")
        
    txt = "✨ <b>Топ по очкам:</b>\n\n"
    for i, r in enumerate(rows, 1):
        txt += f"<b>{i}.</b> {r[0]} — {r[1]} ✨\n"
        
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("topmoney"), StateFilter('*'))
async def cmd_topmoney(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT full_name, money FROM users ORDER BY money DESC LIMIT 10") as cursor: 
            rows = await cursor.fetchall()
            
    if not rows: 
        return await message.answer("Топ пуст.")
        
    txt = "💰 <b>Топ по монетам:</b>\n\n"
    for i, r in enumerate(rows, 1):
        txt += f"<b>{i}.</b> {r[0]} — {r[1]} 💰\n"
        
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("topseason"), StateFilter('*'))
async def cmd_topseason(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT full_name, season_money FROM users ORDER BY season_money DESC LIMIT 10") as cursor: 
            rows = await cursor.fetchall()
            
    if not rows: 
        return await message.answer("Топ пуст.")
        
    txt = "🍂 <b>Топ по Сезонным монетам:</b>\n\n"
    for i, r in enumerate(rows, 1):
        txt += f"<b>{i}.</b> {r[0]} — {r[1]:.1f} 🍂\n"
        
    await message.answer(txt, parse_mode="HTML")

@dp.message(Command("createauc"), StateFilter('*'))
async def cmd_createauc(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
        
    if auc_state["active"]: 
        return await message.answer("❌ Аукцион уже идет!")
        
    if command.args:
        args = command.args.split()
    else:
        args = []
        
    if len(args) < 3: 
        return await message.answer("Формат: /createauc [ID карты] [Старт цена] [Шаг] [ID энчанта(опц)]")
    
    try: 
        input_id = int(args[0])
        price = int(args[1])
        step = int(args[2])
    except Exception: 
        return await message.answer("Ошибка ввода. Должны быть числа.")
        
    if len(args) > 3 and args[3].isdigit():
        enchant_id_auc = int(args[3])
    else:
        enchant_id_auc = 0
        
    if input_id >= 1000000:
        is_shiny_auc = 1
        real_card_id = input_id - 1000000
    else:
        is_shiny_auc = 0
        real_card_id = input_id
    
    cards = load_cards()
    
    card = None
    for c in cards:
        if c['id'] == real_card_id:
            card = c
            break
            
    if not card: 
        return await message.answer("❌ Карта не найдена.")

    auc_state.update({
        "active": True, 
        "card": card, 
        "is_shiny": is_shiny_auc, 
        "enchant_id": enchant_id_auc, 
        "start_price": price, 
        "current_bid": price, 
        "min_step": step, 
        "highest_bidder": None,
        "highest_bidder_name": "", 
        "end_time": datetime.now() + timedelta(seconds=60), 
        "messages": []
    })
    
    chats = await get_auction_chats()
    time_left = int((auc_state["end_time"] - datetime.now()).total_seconds())
    text = get_auc_text(time_left)
    kb = get_auc_kb(price)
    
    success_count = 0
    for cid in chats:
        try:
            msg = await bot.send_photo(cid, card["photo"], caption=text, reply_markup=kb, parse_mode="HTML")
            auc_state["messages"].append((cid, msg.message_id))
            success_count += 1
        except Exception: 
            pass
        await asyncio.sleep(0.05)
        
    await message.answer(f"✅ Аукцион запущен в {success_count} чатах на 60 секунд!")

@dp.message(Command("stopauc"), StateFilter('*'))
async def cmd_stopauc(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS: 
        return
        
    if not auc_state["active"]: 
        return await message.answer("❌ Нет активного аукциона.")
    
    if auc_state["highest_bidder"]:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET money=money+? WHERE user_id=?", (auc_state["current_bid"], auc_state["highest_bidder"]))
            await db.commit()
            
    auc_state["active"] = False
    
    for cid, mid in auc_state["messages"]:
        try: 
            await bot.edit_message_caption(chat_id=cid, message_id=mid, caption="🛑 <b>Аукцион досрочно отменен администратором!</b>\nСтавки возвращены.", parse_mode="HTML")
        except Exception: 
            pass
            
    auc_state["messages"] = []
    await message.answer("✅ Аукцион успешно остановлен.")

@dp.message(Command("stavka"), StateFilter('*'))
async def cmd_stavka(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if not auc_state["active"]: 
        return await message.answer("❌ Нет активных аукционов.")
        
    try: 
        bid = int(command.args)
    except Exception: 
        return await message.answer("Укажите сумму: /stavka [сумма]")
        
    await process_bid(message.from_user, bid, message)

@dp.callback_query(F.data == "auc_bid")
async def cq_auc_bid(call: types.CallbackQuery):
    if not auc_state["active"]: 
        return await call.answer("Аукцион уже завершен!", show_alert=True)
        
    if auc_state["highest_bidder"]:
        next_bid = auc_state["current_bid"] + auc_state["min_step"]
    else:
        next_bid = auc_state["start_price"]
        
    await process_bid(call.from_user, next_bid, call.message, call)

async def process_bid(user, bid, message_obj, call=None):
    if auc_state["highest_bidder"]:
        next_bid = auc_state["current_bid"] + auc_state["min_step"]
    else:
        next_bid = auc_state["start_price"]
        
    if bid < next_bid:
        msg = f"❌ Минимальная ставка сейчас: {next_bid} 💰"
        if call: 
            await call.answer(msg, show_alert=True)
        else: 
            await message_obj.reply(msg)
        return
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT money FROM users WHERE user_id=?", (user.id,)) as cursor: 
            row = await cursor.fetchone()
            
        if row:
            available_money = row[0]
        else:
            available_money = 0
            
        if auc_state["highest_bidder"] == user.id:
            available_money += auc_state["current_bid"]
            
        if available_money < bid:
            msg = "❌ У вас недостаточно монет на балансе!"
            if call: 
                await call.answer(msg, show_alert=True)
            else: 
                await message_obj.reply(msg)
            return
        
        if auc_state["highest_bidder"] and auc_state["highest_bidder"] != user.id:
            await db.execute("UPDATE users SET money=money+? WHERE user_id=?", (auc_state["current_bid"], auc_state["highest_bidder"]))
        
        if auc_state["highest_bidder"] == user.id:
            diff = bid - auc_state["current_bid"]
            await db.execute("UPDATE users SET money=money-? WHERE user_id=?", (diff, user.id))
        else:
            await db.execute("UPDATE users SET money=money-? WHERE user_id=?", (bid, user.id))
            
        await db.commit()
    
    auc_state["highest_bidder"] = user.id
    auc_state["highest_bidder_name"] = user.full_name
    auc_state["current_bid"] = bid
    auc_state["end_time"] = datetime.now() + timedelta(seconds=60)
    
    if call: 
        await call.answer("✅ Ваша ставка принята!")
    else: 
        await message_obj.reply("✅ Ваша ставка принята!")
        
    await force_update_auction_messages()

@dp.message(Command("premiumshop", ignore_case=True), F.chat.type == "private", StateFilter('*'))
@dp.message(lambda msg: msg.text and re.match(r'(?i)^\s*(премиум магазин|магазин)\s*$', msg.text), F.chat.type == "private", StateFilter('*'))
async def cmd_premium_shop(message: types.Message, state: FSMContext):
    await state.clear()
    
    kb_prem = InlineKeyboardBuilder()
    kb_prem.button(text="Купить за 25 ⭐️", callback_data="buy_premium")
    kb_prem.button(text="Купить за 2500 ✨", callback_data="buyexp_premium")
    kb_prem.adjust(1)
    await message.answer("💎 <b>Premium Статус</b>\n- Снижение перезарядки на 10%\n- Удача x1.5\n- Больше очков и монет\n\n<b>Цена:</b> 25 ⭐️ или 2500 ✨", reply_markup=kb_prem.as_markup(), parse_mode="HTML")
    
    kb_shield = InlineKeyboardBuilder()
    kb_shield.button(text="Купить за 5 ⭐️", callback_data="buy_shield")
    kb_shield.button(text="Купить за 500 ✨", callback_data="buyexp_shield")
    kb_shield.adjust(1)
    await message.answer("🛡 <b>Щит</b> (На 1 сезон)\nЗащита от краж!\n\n<b>Цена:</b> 5 ⭐️ или 500 ✨", reply_markup=kb_shield.as_markup(), parse_mode="HTML")
    
    kb_thief = InlineKeyboardBuilder()
    kb_thief.button(text="Купить за 50 ⭐️", callback_data="buy_thief")
    kb_thief.button(text="Купить за 5000 ✨", callback_data="buyexp_thief")
    kb_thief.adjust(1)
    await message.answer("🥷 <b>Вор в законе</b> (На 1 сезон)\nБесплатные кражи!\n\n<b>Цена:</b> 50 ⭐️ или 5000 ✨", reply_markup=kb_thief.as_markup(), parse_mode="HTML")
    
    kb_resp = InlineKeyboardBuilder()
    kb_resp.button(text="Купить за 30 ⭐️", callback_data="buy_respirator")
    kb_resp.button(text="Купить за 3000 ✨", callback_data="buyexp_respirator")
    kb_resp.adjust(1)
    await message.answer("😷 <b>Респиратор</b> (На 1 сезон)\nБез обычных карт!\n\n<b>Цена:</b> 30 ⭐️ или 3000 ✨", reply_markup=kb_resp.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def process_shop_buy_stars(call: types.CallbackQuery):
    item = call.data.split("_")[1] 
    user_id = call.from_user.id
    is_admin = user_id in ADMINS
    
    col_map = {
        "premium": "is_premium", 
        "shield": "has_shield", 
        "thief": "has_thief", 
        "respirator": "has_respirator"
    }
    
    if item not in col_map: 
        return
        
    col = col_map[item]

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(f"SELECT {col} FROM users WHERE user_id = ?", (user_id,)) as cursor: 
            row = await cursor.fetchone()
            
        if row and row[0] == 1: 
            return await call.answer("У вас уже есть этот товар!", show_alert=True)
            
    if is_admin:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(f"UPDATE users SET {col} = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
            
        await call.message.edit_text(f"{call.message.text}\n\n✅ <b>Выдано бесплатно (Админ)!</b>", parse_mode="HTML")
        return await call.answer("Товар успешно выдан админу!", show_alert=True)
        
    prices_map = {
        "premium": 25, 
        "shield": 5, 
        "thief": 50, 
        "respirator": 30
    }
    
    titles_map = {
        "premium": "Premium Статус 💎", 
        "shield": "Щит 🛡", 
        "thief": "Вор в законе 🥷", 
        "respirator": "Респиратор 😷"
    }
    
    await call.message.answer_invoice(
        title=titles_map[item], 
        description=f"Покупка товара: {titles_map[item]}", 
        payload=f"{item}_payment", 
        provider_token="", 
        currency="XTR", 
        prices=[LabeledPrice(label=titles_map[item], amount=prices_map[item])]
    )
    await call.answer()

@dp.callback_query(F.data.startswith("buyexp_"))
async def process_shop_buy_exp(call: types.CallbackQuery):
    item = call.data.split("_")[1] 
    user_id = call.from_user.id
    
    prices_exp = {
        "premium": 2500, 
        "shield": 500, 
        "thief": 5000, 
        "respirator": 3000
    }
    
    cost = prices_exp[item]
    
    query_map = {
        "premium": "is_premium", 
        "shield": "has_shield", 
        "thief": "has_thief", 
        "respirator": "has_respirator"
    }
    
    if item not in query_map: 
        return
        
    col = query_map[item]

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(f"SELECT {col}, IFNULL(points, 0) FROM users WHERE user_id = ?", (user_id,)) as cursor: 
            row = await cursor.fetchone()
            
        if not row:
            return await call.answer("Профиль не найден.", show_alert=True)
            
        has_item = row[0]
        points = row[1]
        
        if has_item == 1: 
            return await call.answer("У вас уже есть этот товар!", show_alert=True)
            
        if points < cost:
            return await call.answer(f"❌ Недостаточно опыта! Нужно {cost} ✨", show_alert=True)
            
        await db.execute(f"UPDATE users SET {col} = 1, points = points - ? WHERE user_id = ?", (cost, user_id))
        await db.commit()
        
    titles_map = {
        "premium": "Premium Статус 💎", 
        "shield": "Щит 🛡", 
        "thief": "Вор в законе 🥷", 
        "respirator": "Респиратор 😷"
    }
    
    await call.message.edit_text(f"{call.message.text}\n\n✅ <b>Куплено за {cost} ✨!</b>", parse_mode="HTML")
    await call.answer(f"Успешно куплено: {titles_map[item]}", show_alert=True)

@dp.pre_checkout_query(lambda query: True)
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    
    if payload.startswith("addbot_"):
        if IS_CHILD:
            return 
            
        new_token = payload.replace("addbot_", "")
        
        if new_token == TOKEN:
            return await message.answer("❌ Критическая ошибка: токен принадлежит текущему боту. Запуск отменен.")
            
        try:
            async with Bot(token=new_token) as tb:
                child_me = await tb.get_me()
                bot_id = child_me.id
        except Exception as e:
            return await message.answer(f"❌ Ошибка токена после оплаты: {e}")
            
        me = await bot.get_me()
        if bot_id == me.id:
            return await message.answer("❌ Критическая ошибка: этот токен принадлежит основному боту! Привязка отменена.")
            
        hosted = {}
        if os.path.exists(HOSTED_BOTS_FILE):
            try:
                with open(HOSTED_BOTS_FILE, "r", encoding="utf-8") as f:
                    hosted = json.load(f)
            except Exception:
                pass
                
        hosted[str(bot_id)] = {
            "token": new_token, 
            "creator_id": user_id
        }
        
        with open(HOSTED_BOTS_FILE, "w", encoding="utf-8") as f:
            json.dump(hosted, f, indent=4)
            
        child_dir = os.path.join(BASE_DIR, "hosted_bots", str(bot_id))
        os.makedirs(child_dir, exist_ok=True)
            
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--child", new_token, str(user_id), str(bot_id), MAIN_BOT_USERNAME])
        return await message.answer(f"🎉 Успешная оплата!\n✅ Ваш бот @{child_me.username} запущен! Его база данных абсолютно чиста. Перейдите в него и начните добавлять карты!")

    async with aiosqlite.connect(DB_FILE) as db:
        if payload == "premium_payment":
            await db.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
            await message.answer("Успешная оплата! 🎉 Вы получили Premium Статус 💎!", reply_markup=get_main_keyboard(message.from_user.id))
        elif payload == "shield_payment":
            await db.execute("UPDATE users SET has_shield = 1 WHERE user_id = ?", (user_id,))
            await message.answer("Успешная оплата! 🎉 Вы получили Щит 🛡!")
        elif payload == "thief_payment":
            await db.execute("UPDATE users SET has_thief = 1 WHERE user_id = ?", (user_id,))
            await message.answer("Успешная оплата! 🎉 Вы получили статус Вор в законе 🥷!")
        elif payload == "respirator_payment":
            await db.execute("UPDATE users SET has_respirator = 1 WHERE user_id = ?", (user_id,))
            await message.answer("Успешная оплата! 🎉 Вы получили Респиратор 😷!")
            
        await db.commit()

@dp.message(Command("addbot"), F.chat.type == "private", StateFilter('*'))
async def cmd_addbot(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    
    if IS_CHILD:
        kb = InlineKeyboardBuilder()
        kb.button(text="🤖 Основной бот", url=f"https://t.me/{MAIN_BOT_USERNAME}")
        return await message.answer("⚠️ Создавать ботов можно только в основном боте!", reply_markup=kb.as_markup())

    if not command.args:
        return await message.answer("Формат: /addbot ТОКЕН\nСоздание своего бота стоит 5 ⭐️.")
        
    new_token = command.args.strip()
    
    if new_token == TOKEN:
        return await message.answer("❌ Ошибка: Вы указали токен текущего бота! Вам нужно зайти в @BotFather, создать НОВОГО бота и прислать его токен.")
        
    try:
        async with Bot(token=new_token) as tb:
            child_me = await tb.get_me()
            bot_id = child_me.id
    except Exception as e:
        return await message.answer(f"❌ Ошибка токена: {e}")
        
    me = await bot.get_me()
    if bot_id == me.id:
        return await message.answer("❌ Критическая ошибка: этот токен принадлежит основному боту! Привязка отменена.")
        
    hosted = {}
    if os.path.exists(HOSTED_BOTS_FILE):
        try:
            with open(HOSTED_BOTS_FILE, "r", encoding="utf-8") as f:
                hosted = json.load(f)
        except Exception:
            pass
            
    if str(bot_id) in hosted:
        return await message.answer("⚠️ Этот бот уже запущен!")
        
    prices = [LabeledPrice(label="Запуск бота", amount=5)]
    await message.answer_invoice(
        title="Запуск своего бота 🤖",
        description=f"Оплата хостинга для бота @{child_me.username}",
        payload=f"addbot_{new_token}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

# --- ПЕРЕХВАТЧИК И ЗАПУСК (ВСЕГДА В КОНЦЕ) ---
@dp.message(StateFilter('*'))
async def catch_all(message: types.Message, state: FSMContext):
    curr = await state.get_state()
    if curr:
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    if message.chat and message.chat.type == "private":
        await message.answer("Используйте команды в меню.", reply_markup=get_main_keyboard(message.from_user.id))

async def main():
    await init_db()
    load_events()
    await auto_sort_index()
    await set_commands(bot)
    
    global MAIN_BOT_USERNAME
    if not IS_CHILD:
        async with Bot(token=TOKEN) as tb:
            me = await tb.get_me()
            MAIN_BOT_USERNAME = me.username
            
        if os.path.exists(HOSTED_BOTS_FILE):
            try:
                with open(HOSTED_BOTS_FILE, "r", encoding="utf-8") as f:
                    hosted = json.load(f)
                    
                for bid, data in hosted.items():
                    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--child", data["token"], str(data["creator_id"]), str(bid), MAIN_BOT_USERNAME])
            except Exception:
                pass
                    
    asyncio.create_task(event_manager())
    asyncio.create_task(auction_manager_task())
    asyncio.create_task(shop_group_reminder_task())
    asyncio.create_task(info_group_reminder_task())
    asyncio.create_task(channel_promo_task())
    
    if not IS_CHILD:
        asyncio.create_task(host_promo_task())
        
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import os
import json
import random
import asyncio
from datetime import datetime
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                            InlineKeyboardButton, LabeledPrice, PreCheckoutQuery)
from aiogram.filters import Command, CommandObject
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))
LOG_CHAT   = os.getenv("LOG_CHAT", "")   # ID лог-канала (необязательно)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher()

# ══════════════════════════════════════════
#  ДАННЫЕ
# ══════════════════════════════════════════
DATA_FILE = "skins_data.json"

inventories  = defaultdict(list)          # {uid: [{"skin_id":..,"unique_id":..,"obtained":..}]}
stars_bal    = defaultdict(int)           # {uid: stars}
user_names   = {}                         # {uid: name}
trade_offers = {}                         # {trade_id: {from, to, give_uid, want_uid, status}}
sell_offers  = {}                         # {offer_id: {seller, skin_unique_id, skin_id, price, created}}
_trade_counter = 0
_sell_counter  = 0

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "inventories":  dict(inventories),
            "stars_bal":    dict(stars_bal),
            "user_names":   user_names,
            "trade_offers": trade_offers,
            "sell_offers":  sell_offers,
            "_trade_counter": _trade_counter,
            "_sell_counter":  _sell_counter,
        }, f, ensure_ascii=False, indent=2)

def load_data():
    global _trade_counter, _sell_counter
    if not os.path.exists(DATA_FILE): return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    for uid, inv in d.get("inventories", {}).items():
        inventories[uid] = inv
    for uid, bal in d.get("stars_bal", {}).items():
        stars_bal[uid] = bal
    user_names.update(d.get("user_names", {}))
    trade_offers.update(d.get("trade_offers", {}))
    sell_offers.update(d.get("sell_offers", {}))
    _trade_counter = d.get("_trade_counter", 0)
    _sell_counter  = d.get("_sell_counter",  0)

# ══════════════════════════════════════════
#  СКИНЫ И КЕЙСЫ
# ══════════════════════════════════════════
RARITIES = {
    "common":    {"label": "⬜ Common",    "color": "⬜", "chance": 55},
    "uncommon":  {"label": "🟩 Uncommon",  "color": "🟩", "chance": 25},
    "rare":      {"label": "🟦 Rare",      "color": "🟦", "chance": 12},
    "epic":      {"label": "🟪 Epic",      "color": "🟪", "chance": 6},
    "legendary": {"label": "🟨 Legendary", "color": "🟨", "chance": 1.5},
    "divine":    {"label": "🔴 Divine",    "color": "🔴", "chance": 0.5},
}

SKINS = {
    # Common
    "s001": {"name": "🔫 Rusty Pistol",       "rarity": "common",    "emoji": "🔫",  "value": 5},
    "s002": {"name": "🗡️ Iron Blade",          "rarity": "common",    "emoji": "🗡️",  "value": 5},
    "s003": {"name": "💣 Basic Grenade",       "rarity": "common",    "emoji": "💣",  "value": 8},
    "s004": {"name": "🪖 Steel Helmet",        "rarity": "common",    "emoji": "🪖",  "value": 7},
    "s005": {"name": "🧤 Rough Gloves",        "rarity": "common",    "emoji": "🧤",  "value": 6},
    # Uncommon
    "s006": {"name": "🔫 Chrome Glock",        "rarity": "uncommon",  "emoji": "🔫",  "value": 20},
    "s007": {"name": "⚔️ Silver Sword",        "rarity": "uncommon",  "emoji": "⚔️",  "value": 22},
    "s008": {"name": "🎯 Scope Hunter",        "rarity": "uncommon",  "emoji": "🎯",  "value": 18},
    "s009": {"name": "🛡️ Iron Shield",         "rarity": "uncommon",  "emoji": "🛡️",  "value": 25},
    # Rare
    "s010": {"name": "⚡ Electric Rifle",      "rarity": "rare",      "emoji": "⚡",  "value": 60},
    "s011": {"name": "🌊 Ocean AK",            "rarity": "rare",      "emoji": "🌊",  "value": 75},
    "s012": {"name": "🔥 Fire Knife",          "rarity": "rare",      "emoji": "🔥",  "value": 80},
    "s013": {"name": "❄️ Frost Sniper",        "rarity": "rare",      "emoji": "❄️",  "value": 70},
    # Epic
    "s014": {"name": "🌌 Galaxy M4",           "rarity": "epic",      "emoji": "🌌",  "value": 200},
    "s015": {"name": "💜 Void Walker Knife",   "rarity": "epic",      "emoji": "💜",  "value": 250},
    "s016": {"name": "🐉 Dragon AWP",          "rarity": "epic",      "emoji": "🐉",  "value": 300},
    "s017": {"name": "🤖 Cyber Gloves",        "rarity": "epic",      "emoji": "🤖",  "value": 220},
    # Legendary
    "s018": {"name": "👑 Royal Karambit",      "rarity": "legendary", "emoji": "👑",  "value": 800},
    "s019": {"name": "🌟 Star Destroyer AWP",  "rarity": "legendary", "emoji": "🌟",  "value": 1000},
    "s020": {"name": "🔱 Poseidon AK-47",      "rarity": "legendary", "emoji": "🔱",  "value": 900},
    # Divine
    "s021": {"name": "💫 GOD Knife",           "rarity": "divine",    "emoji": "💫",  "value": 5000},
    "s022": {"name": "☠️ Death's Whisper AWP", "rarity": "divine",    "emoji": "☠️",  "value": 4000},
}

CASES = {
    "starter": {
        "name": "📦 Стартовый кейс",
        "price": 50,
        "emoji": "📦",
        "skins": ["s001","s002","s003","s004","s005","s006","s007","s008","s009","s010"],
    },
    "pro": {
        "name": "🎯 Про кейс",
        "price": 150,
        "emoji": "🎯",
        "skins": ["s006","s007","s008","s009","s010","s011","s012","s013","s014","s015"],
    },
    "elite": {
        "name": "💎 Элитный кейс",
        "price": 350,
        "emoji": "💎",
        "skins": ["s010","s011","s012","s013","s014","s015","s016","s017","s018","s019"],
    },
    "divine": {
        "name": "🔮 Божественный кейс",
        "price": 1000,
        "emoji": "🔮",
        "skins": ["s014","s015","s016","s017","s018","s019","s020","s021","s022"],
    },
}

def roll_skin(case_id: str) -> dict:
    case = CASES[case_id]
    skin_pool = [SKINS[sid] | {"id": sid} for sid in case["skins"]]
    weights = [RARITIES[s["rarity"]]["chance"] for s in skin_pool]
    return random.choices(skin_pool, weights=weights, k=1)[0]

def get_unique_id() -> str:
    return f"{int(datetime.now().timestamp())}{random.randint(1000,9999)}"

def get_inv_skin(uid: str, unique_id: str):
    for item in inventories.get(uid, []):
        if item["unique_id"] == unique_id:
            return item
    return None

def rarity_icon(rarity: str) -> str:
    return RARITIES.get(rarity, {}).get("color", "⬜")

# ══════════════════════════════════════════
#  КЛАВИАТУРЫ
# ══════════════════════════════════════════
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Открыть кейс", callback_data="cases"),
         InlineKeyboardButton(text="🎒 Инвентарь",    callback_data="inv:0")],
        [InlineKeyboardButton(text="🏪 Маркет",       callback_data="market:0"),
         InlineKeyboardButton(text="🏆 Топ",          callback_data="top")],
        [InlineKeyboardButton(text="⭐ Пополнить",    callback_data="topup"),
         InlineKeyboardButton(text="ℹ️ Профиль",      callback_data="profile")],
    ])

def kb_cases():
    rows = []
    for cid, case in CASES.items():
        rows.append([InlineKeyboardButton(
            text=f"{case['emoji']} {case['name']} — {case['price']}⭐",
            callback_data=f"opencase:{cid}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_inv(uid: str, page: int = 0):
    inv = inventories.get(uid, [])
    per_page = 6
    start = page * per_page
    items = inv[start:start + per_page]
    rows = []
    for item in items:
        skin = SKINS.get(item["skin_id"], {})
        icon = rarity_icon(skin.get("rarity","common"))
        rows.append([InlineKeyboardButton(
            text=f"{icon} {skin.get('emoji','')} {skin.get('name','?')}",
            callback_data=f"skin:{item['unique_id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"inv:{page-1}"))
    total = (len(inv) - 1) // per_page + 1 if inv else 1
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if (page + 1) * per_page < len(inv):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"inv:{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_skin_actions(unique_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выставить на продажу", callback_data=f"sell_menu:{unique_id}")],
        [InlineKeyboardButton(text="◀️ Назад к инвентарю", callback_data="inv:0")],
    ])

def kb_market(page: int = 0):
    active = [(oid, o) for oid, o in sell_offers.items() if o["status"] == "active"]
    per_page = 5
    start = page * per_page
    items = active[start:start + per_page]
    rows = []
    for oid, offer in items:
        skin = SKINS.get(offer["skin_id"], {})
        icon = rarity_icon(skin.get("rarity","common"))
        seller_name = user_names.get(str(offer["seller"]), f"ID{offer['seller']}")[:12]
        rows.append([InlineKeyboardButton(
            text=f"{icon} {skin.get('emoji','')} {skin.get('name','?')} — {offer['price']}⭐ ({seller_name})",
            callback_data=f"buy_offer:{oid}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"market:{page-1}"))
    total = (len(active) - 1) // per_page + 1 if active else 1
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if (page + 1) * per_page < len(active):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"market:{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ══════════════════════════════════════════
#  ХЕЛПЕРЫ
# ══════════════════════════════════════════
def fmt_skin(skin: dict, item: dict = None) -> str:
    r = skin.get("rarity","common")
    icon = rarity_icon(r)
    rarity_label = RARITIES.get(r, {}).get("label","")
    obtained = ""
    if item:
        obtained = f"\n📅 Получен: {item.get('obtained','—')}"
    return (f"{icon} <b>{skin['name']}</b>\n"
            f"✨ Редкость: {rarity_label}\n"
            f"💰 Стоимость: <b>{skin['value']}⭐</b>"
            f"{obtained}")

async def log(text: str):
    if LOG_CHAT:
        try: await bot.send_message(LOG_CHAT, text)
        except: pass

# ══════════════════════════════════════════
#  КОМАНДЫ
# ══════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = str(message.from_user.id)
    user_names[uid] = message.from_user.full_name
    # Приветственный бонус новичкам
    if uid not in stars_bal or stars_bal[uid] == 0:
        stars_bal[uid] = 100
        bonus_text = "\n\n🎁 <b>Приветственный бонус: 100⭐!</b> Попробуй открыть стартовый кейс."
    else:
        bonus_text = ""
    save_data()
    await message.answer(
        f"╔═══════════════════╗\n"
        f"⚔️  <b>SkinVault Bot</b>\n"
        f"╚═══════════════════╝\n\n"
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n"
        f"💼 Открывай кейсы, собирай скины и торгуй с другими игроками!\n\n"
        f"⭐ Твой баланс: <b>{stars_bal[uid]}⭐</b>{bonus_text}",
        reply_markup=kb_main())

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    uid = str(message.from_user.id)
    user_names[uid] = message.from_user.full_name
    inv = inventories.get(uid, [])
    bal = stars_bal.get(uid, 0)
    # Считаем редкие скины
    rare_count = sum(1 for item in inv if SKINS.get(item["skin_id"],{}).get("rarity") in ("legendary","divine"))
    # Ценность инвентаря
    inv_value = sum(SKINS.get(item["skin_id"],{}).get("value",0) for item in inv)
    await message.answer(
        f"╔═══════════════════╗\n"
        f"👤  <b>ПРОФИЛЬ</b>\n"
        f"╚═══════════════════╝\n\n"
        f"👤 <b>{message.from_user.full_name}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n\n"
        f"⭐ <b>Баланс:</b> {bal}⭐\n"
        f"🎒 <b>Скинов:</b> {len(inv)}\n"
        f"💎 <b>Редких скинов:</b> {rare_count}\n"
        f"💰 <b>Ценность инвентаря:</b> {inv_value}⭐",
        reply_markup=kb_main())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "╔═══════════════════╗\n"
        "ℹ️  <b>КОМАНДЫ</b>\n"
        "╚═══════════════════╝\n\n"
        "📦 /cases — список кейсов\n"
        "🎒 /inv — твой инвентарь\n"
        "🏪 /market — маркет скинов\n"
        "🏆 /top — топ игроков\n"
        "👤 /profile — твой профиль\n"
        "⭐ /topup — пополнить баланс\n\n"
        "<b>Торговля:</b>\n"
        "🔄 /trade @username — предложить трейд\n"
        "📋 /trades — активные трейды\n\n"
        "<i>Бот использует Telegram Stars (⭐) для оплаты.</i>")

# ══════════════════════════════════════════
#  КЕЙСЫ
# ══════════════════════════════════════════
@dp.message(Command("cases"))
async def cmd_cases(message: Message):
    text = "╔═══════════════════╗\n📦  <b>КЕЙСЫ</b>\n╚═══════════════════╝\n\n"
    for cid, case in CASES.items():
        skins_preview = " ".join(SKINS[sid]["emoji"] for sid in case["skins"][:5])
        text += f"{case['emoji']} <b>{case['name']}</b> — {case['price']}⭐\n{skins_preview}...\n\n"
    await message.answer(text, reply_markup=kb_cases())

@dp.callback_query(F.data == "cases")
async def cb_cases(call: CallbackQuery):
    text = "╔═══════════════════╗\n📦  <b>КЕЙСЫ</b>\n╚═══════════════════╝\n\n"
    for cid, case in CASES.items():
        skins_preview = " ".join(SKINS[sid]["emoji"] for sid in case["skins"][:5])
        text += f"{case['emoji']} <b>{case['name']}</b> — {case['price']}⭐\n{skins_preview}...\n\n"
    await call.message.edit_text(text, reply_markup=kb_cases())
    await call.answer()

@dp.callback_query(F.data.startswith("opencase:"))
async def cb_open_case(call: CallbackQuery):
    uid = str(call.from_user.id)
    user_names[uid] = call.from_user.full_name
    case_id = call.data.split(":")[1]
    case = CASES.get(case_id)
    if not case:
        await call.answer("❌ Кейс не найден", show_alert=True); return
    bal = stars_bal.get(uid, 0)
    if bal < case["price"]:
        await call.answer(
            f"❌ Недостаточно звёзд!\n"
            f"Нужно: {case['price']}⭐\n"
            f"У тебя: {bal}⭐", show_alert=True); return
    # Списываем и роллим
    stars_bal[uid] -= case["price"]
    skin = roll_skin(case_id)
    unique_id = get_unique_id()
    inventories[uid].append({
        "skin_id": skin["id"],
        "unique_id": unique_id,
        "obtained": datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    save_data()
    r = skin["rarity"]
    icon = rarity_icon(r)
    rarity_label = RARITIES.get(r, {}).get("label","")
    # Спецэффект для легендарных
    if r in ("legendary", "divine"):
        effect = "\n\n🎊🎊🎊 <b>НЕВЕРОЯТНОЕ ВЫПАДЕНИЕ!</b> 🎊🎊🎊"
        await log(f"🎊 <b>РЕДКИЙ ДРОП!</b>\nИгрок: {call.from_user.full_name} (<code>{uid}</code>)\nСкин: {skin['name']}\nРедкость: {rarity_label}")
    elif r == "epic":
        effect = "\n\n✨ <b>Отличное выпадение!</b> ✨"
    else:
        effect = ""
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"📦  <b>ОТКРЫТИЕ КЕЙСА</b>\n"
        f"╚═══════════════════╝\n\n"
        f"Кейс: {case['emoji']} <b>{case['name']}</b>\n\n"
        f"🎲 Результат:\n\n"
        f"{icon} <b>{skin['name']}</b> {skin['emoji']}\n"
        f"✨ Редкость: {rarity_label}\n"
        f"💰 Стоимость: <b>{skin['value']}⭐</b>\n\n"
        f"⭐ Остаток: <b>{stars_bal[uid]}⭐</b>"
        f"{effect}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Открыть ещё", callback_data=f"opencase:{case_id}"),
             InlineKeyboardButton(text="🎒 В инвентарь",  callback_data="inv:0")],
            [InlineKeyboardButton(text="◀️ К кейсам", callback_data="cases")],
        ]))
    await call.answer(f"Выпало: {skin['name']}!")

# ══════════════════════════════════════════
#  ИНВЕНТАРЬ
# ══════════════════════════════════════════
@dp.message(Command("inv"))
async def cmd_inv(message: Message):
    uid = str(message.from_user.id)
    inv = inventories.get(uid, [])
    if not inv:
        await message.answer("🎒 Твой инвентарь пуст!\n\nОткрой кейс через 📦 /cases", reply_markup=kb_main()); return
    await message.answer(
        f"╔═══════════════════╗\n"
        f"🎒  <b>ИНВЕНТАРЬ</b> ({len(inv)} скинов)\n"
        f"╚═══════════════════╝\n\n"
        f"Выбери скин для действий:",
        reply_markup=kb_inv(uid))

@dp.callback_query(F.data.startswith("inv:"))
async def cb_inv(call: CallbackQuery):
    uid = str(call.from_user.id)
    page = int(call.data.split(":")[1])
    inv = inventories.get(uid, [])
    if not inv:
        await call.message.edit_text("🎒 Инвентарь пуст!", reply_markup=kb_main()); return
    inv_value = sum(SKINS.get(item["skin_id"],{}).get("value",0) for item in inv)
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"🎒  <b>ИНВЕНТАРЬ</b> ({len(inv)} скинов)\n"
        f"╚═══════════════════╝\n\n"
        f"💰 Общая ценность: <b>{inv_value}⭐</b>\n\n"
        f"Выбери скин:",
        reply_markup=kb_inv(uid, page))
    await call.answer()

@dp.callback_query(F.data.startswith("skin:"))
async def cb_skin(call: CallbackQuery):
    uid = str(call.from_user.id)
    unique_id = call.data.split(":")[1]
    item = get_inv_skin(uid, unique_id)
    if not item:
        await call.answer("❌ Скин не найден", show_alert=True); return
    skin = SKINS.get(item["skin_id"], {})
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"🎮  <b>СКИН</b>\n"
        f"╚═══════════════════╝\n\n"
        f"{fmt_skin(skin, item)}",
        reply_markup=kb_skin_actions(unique_id))
    await call.answer()

# ══════════════════════════════════════════
#  МАРКЕТ
# ══════════════════════════════════════════
@dp.message(Command("market"))
async def cmd_market(message: Message):
    active = [(oid, o) for oid, o in sell_offers.items() if o["status"] == "active"]
    await message.answer(
        f"╔═══════════════════╗\n"
        f"🏪  <b>МАРКЕТ</b>\n"
        f"╚═══════════════════╝\n\n"
        f"Активных предложений: <b>{len(active)}</b>\n\n"
        f"Выбери скин для покупки:",
        reply_markup=kb_market())

@dp.callback_query(F.data.startswith("market:"))
async def cb_market(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    active = [(oid, o) for oid, o in sell_offers.items() if o["status"] == "active"]
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"🏪  <b>МАРКЕТ</b>\n"
        f"╚═══════════════════╝\n\n"
        f"Активных предложений: <b>{len(active)}</b>\n\n"
        f"Выбери скин для покупки:",
        reply_markup=kb_market(page))
    await call.answer()

@dp.callback_query(F.data.startswith("sell_menu:"))
async def cb_sell_menu(call: CallbackQuery):
    uid = str(call.from_user.id)
    unique_id = call.data.split(":")[1]
    item = get_inv_skin(uid, unique_id)
    if not item:
        await call.answer("❌ Скин не найден", show_alert=True); return
    skin = SKINS.get(item["skin_id"], {})
    await call.message.edit_text(
        f"💰 <b>Продажа скина</b>\n\n"
        f"{fmt_skin(skin)}\n\n"
        f"Введи цену в звёздах командой:\n"
        f"<code>/sell {unique_id} [цена]</code>\n\n"
        f"Например: <code>/sell {unique_id} {skin['value']}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"skin:{unique_id}")]]))
    await call.answer()

@dp.message(Command("sell"))
async def cmd_sell(message: Message, command: CommandObject):
    uid = str(message.from_user.id)
    if not command.args or len(command.args.split()) < 2:
        await message.reply("⚠️ Формат: <code>/sell [unique_id] [цена]</code>"); return
    parts = command.args.split()
    unique_id, price_str = parts[0], parts[1]
    try:
        price = int(price_str)
        if price < 1: raise ValueError
    except:
        await message.reply("❌ Цена должна быть числом больше 0"); return
    item = get_inv_skin(uid, unique_id)
    if not item:
        await message.reply("❌ Скин не найден в инвентаре"); return
    skin = SKINS.get(item["skin_id"], {})
    # Убираем из инвентаря
    inventories[uid] = [i for i in inventories[uid] if i["unique_id"] != unique_id]
    global _sell_counter
    _sell_counter += 1
    offer_id = f"s{_sell_counter}"
    sell_offers[offer_id] = {
        "seller": int(uid), "skin_unique_id": unique_id,
        "skin_id": item["skin_id"], "price": price,
        "status": "active", "created": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    save_data()
    await message.reply(
        f"✅ Скин выставлен на продажу!\n\n"
        f"{fmt_skin(skin)}\n\n"
        f"💰 Цена: <b>{price}⭐</b>\n"
        f"🔖 ID лота: <code>{offer_id}</code>\n\n"
        f"Чтобы снять с продажи: <code>/cancel_sell {offer_id}</code>")

@dp.message(Command("cancel_sell"))
async def cmd_cancel_sell(message: Message, command: CommandObject):
    uid = str(message.from_user.id)
    if not command.args:
        await message.reply("⚠️ Формат: <code>/cancel_sell [offer_id]</code>"); return
    offer_id = command.args.strip()
    offer = sell_offers.get(offer_id)
    if not offer or str(offer["seller"]) != uid:
        await message.reply("❌ Лот не найден или не твой"); return
    if offer["status"] != "active":
        await message.reply("❌ Лот уже не активен"); return
    # Возвращаем скин
    inventories[uid].append({
        "skin_id": offer["skin_id"],
        "unique_id": offer["skin_unique_id"],
        "obtained": offer.get("created","—")
    })
    offer["status"] = "cancelled"
    save_data()
    skin = SKINS.get(offer["skin_id"], {})
    await message.reply(f"✅ Лот снят с продажи.\n{fmt_skin(skin)}\nВозвращён в инвентарь.")

@dp.callback_query(F.data.startswith("buy_offer:"))
async def cb_buy_offer(call: CallbackQuery):
    uid = str(call.from_user.id)
    offer_id = call.data.split(":")[1]
    offer = sell_offers.get(offer_id)
    if not offer or offer["status"] != "active":
        await call.answer("❌ Лот уже недоступен", show_alert=True); return
    if str(offer["seller"]) == uid:
        await call.answer("❌ Нельзя купить свой скин!", show_alert=True); return
    skin = SKINS.get(offer["skin_id"], {})
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"🛒  <b>ПОКУПКА</b>\n"
        f"╚═══════════════════╝\n\n"
        f"{fmt_skin(skin)}\n\n"
        f"💰 Цена: <b>{offer['price']}⭐</b>\n"
        f"👤 Продавец: {user_names.get(str(offer['seller']), '?')}\n\n"
        f"⭐ Твой баланс: <b>{stars_bal.get(uid,0)}⭐</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Купить за {offer['price']}⭐", callback_data=f"confirm_buy:{offer_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="market:0")],
        ]))
    await call.answer()

@dp.callback_query(F.data.startswith("confirm_buy:"))
async def cb_confirm_buy(call: CallbackQuery):
    uid = str(call.from_user.id)
    offer_id = call.data.split(":")[1]
    offer = sell_offers.get(offer_id)
    if not offer or offer["status"] != "active":
        await call.answer("❌ Лот уже недоступен", show_alert=True); return
    if str(offer["seller"]) == uid:
        await call.answer("❌ Нельзя купить свой скин!", show_alert=True); return
    bal = stars_bal.get(uid, 0)
    if bal < offer["price"]:
        await call.answer(f"❌ Недостаточно звёзд! Нужно {offer['price']}⭐, у тебя {bal}⭐", show_alert=True); return
    # Транзакция
    stars_bal[uid] -= offer["price"]
    stars_bal[str(offer["seller"])] = stars_bal.get(str(offer["seller"]), 0) + offer["price"]
    inventories[uid].append({
        "skin_id": offer["skin_id"],
        "unique_id": offer["skin_unique_id"],
        "obtained": datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    offer["status"] = "sold"
    save_data()
    skin = SKINS.get(offer["skin_id"], {})
    await call.message.edit_text(
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"{fmt_skin(skin)}\n\n"
        f"💸 Списано: <b>{offer['price']}⭐</b>\n"
        f"⭐ Остаток: <b>{stars_bal[uid]}⭐</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv:0")],
            [InlineKeyboardButton(text="🏪 Маркет", callback_data="market:0")],
        ]))
    # Уведомляем продавца
    try:
        buyer_name = user_names.get(uid, f"ID{uid}")
        await bot.send_message(
            offer["seller"],
            f"✅ <b>Твой скин куплен!</b>\n\n"
            f"{fmt_skin(skin)}\n\n"
            f"👤 Покупатель: {buyer_name}\n"
            f"💰 Получено: <b>{offer['price']}⭐</b>\n"
            f"⭐ Новый баланс: <b>{stars_bal[str(offer['seller'])]}⭐</b>")
    except: pass
    await call.answer("✅ Куплено!")
    await log(f"🛒 <b>ПРОДАЖА</b>\nСкин: {skin['name']}\nЦена: {offer['price']}⭐\nПродавец: {offer['seller']}\nПокупатель: {uid}")

# ══════════════════════════════════════════
#  ТОП ИГРОКОВ
# ══════════════════════════════════════════
@dp.message(Command("top"))
async def cmd_top(message: Message):
    await show_top(message)

@dp.callback_query(F.data == "top")
async def cb_top(call: CallbackQuery):
    await show_top(call.message, edit=True)
    await call.answer()

async def show_top(message, edit=False):
    # Топ по редким скинам (legendary + divine)
    scores = []
    for uid, inv in inventories.items():
        rare = sum(1 for item in inv if SKINS.get(item["skin_id"],{}).get("rarity") in ("legendary","divine"))
        inv_val = sum(SKINS.get(item["skin_id"],{}).get("value",0) for item in inv)
        if rare > 0 or inv_val > 0:
            scores.append((uid, rare, inv_val))
    scores.sort(key=lambda x: (x[1], x[2]), reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["╔═══════════════════╗\n🏆  <b>ТОП ИГРОКОВ</b>\n╚═══════════════════╝\n\n<b>По редким скинам:</b>\n"]
    for i, (uid, rare, inv_val) in enumerate(scores[:10]):
        name = user_names.get(uid, f"ID{uid}")
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(f"{medal} <b>{name}</b>\n    💎 Редких: {rare} | 💰 Ценность: {inv_val}⭐")
    if not scores:
        lines.append("Пока никто не открывал кейсы!")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="main")]])
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

# ══════════════════════════════════════════
#  ПОПОЛНЕНИЕ (Telegram Stars)
# ══════════════════════════════════════════
TOPUP_PACKAGES = {
    "100":  {"stars": 100,  "xtr": 1},
    "500":  {"stars": 500,  "xtr": 5},
    "1000": {"stars": 1000, "xtr": 9},
    "3000": {"stars": 3000, "xtr": 25},
}

@dp.message(Command("topup"))
async def cmd_topup(message: Message):
    await show_topup(message)

@dp.callback_query(F.data == "topup")
async def cb_topup(call: CallbackQuery):
    await show_topup(call.message, edit=True)
    await call.answer()

async def show_topup(message, edit=False):
    text = ("╔═══════════════════╗\n"
            "⭐  <b>ПОПОЛНЕНИЕ</b>\n"
            "╚═══════════════════╝\n\n"
            "Выбери пакет звёзд:\n\n"
            "💡 <i>Оплата через Telegram Stars (XTR)</i>")
    rows = []
    for pkg_id, pkg in TOPUP_PACKAGES.items():
        rows.append([InlineKeyboardButton(
            text=f"⭐ {pkg['stars']} звёзд — {pkg['xtr']} XTR",
            callback_data=f"buy_stars:{pkg_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_stars:"))
async def cb_buy_stars(call: CallbackQuery):
    pkg_id = call.data.split(":")[1]
    pkg = TOPUP_PACKAGES.get(pkg_id)
    if not pkg:
        await call.answer("❌ Пакет не найден", show_alert=True); return
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"⭐ {pkg['stars']} игровых звёзд",
        description=f"Пополнение баланса в SkinVault Bot на {pkg['stars']}⭐",
        payload=f"topup:{pkg_id}:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{pkg['stars']} звёзд", amount=pkg["xtr"])],
        provider_token="")
    await call.answer()

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    uid = str(message.from_user.id)
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if parts[0] == "topup":
        pkg_id = parts[1]
        pkg = TOPUP_PACKAGES.get(pkg_id)
        if pkg:
            stars_bal[uid] = stars_bal.get(uid, 0) + pkg["stars"]
            save_data()
            await message.answer(
                f"✅ <b>Пополнение успешно!</b>\n\n"
                f"➕ Добавлено: <b>{pkg['stars']}⭐</b>\n"
                f"⭐ Новый баланс: <b>{stars_bal[uid]}⭐</b>",
                reply_markup=kb_main())
            await log(f"💳 <b>ПОПОЛНЕНИЕ</b>\nПользователь: {message.from_user.full_name} (<code>{uid}</code>)\nПакет: {pkg['stars']}⭐\nОплачено: {pkg['xtr']} XTR")

# ══════════════════════════════════════════
#  КНОПКИ НАВИГАЦИИ
# ══════════════════════════════════════════
@dp.callback_query(F.data == "main")
async def cb_main(call: CallbackQuery):
    uid = str(call.from_user.id)
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"⚔️  <b>SkinVault Bot</b>\n"
        f"╚═══════════════════╝\n\n"
        f"⭐ Твой баланс: <b>{stars_bal.get(uid,0)}⭐</b>\n"
        f"🎒 Скинов: <b>{len(inventories.get(uid,[]))}</b>",
        reply_markup=kb_main())
    await call.answer()

@dp.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery):
    uid = str(call.from_user.id)
    inv = inventories.get(uid, [])
    bal = stars_bal.get(uid, 0)
    rare_count = sum(1 for item in inv if SKINS.get(item["skin_id"],{}).get("rarity") in ("legendary","divine"))
    inv_value = sum(SKINS.get(item["skin_id"],{}).get("value",0) for item in inv)
    await call.message.edit_text(
        f"╔═══════════════════╗\n"
        f"👤  <b>ПРОФИЛЬ</b>\n"
        f"╚═══════════════════╝\n\n"
        f"👤 <b>{call.from_user.full_name}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n\n"
        f"⭐ <b>Баланс:</b> {bal}⭐\n"
        f"🎒 <b>Скинов:</b> {len(inv)}\n"
        f"💎 <b>Редких скинов:</b> {rare_count}\n"
        f"💰 <b>Ценность инвентаря:</b> {inv_value}⭐",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="main")]]))
    await call.answer()

@dp.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()

# ══════════════════════════════════════════
#  АДМИН
# ══════════════════════════════════════════
@dp.message(Command("give_stars"))
async def cmd_give_stars(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        await message.reply("🚫 Только для администратора"); return
    if not command.args:
        await message.reply("⚠️ /give_stars [user_id] [amount]"); return
    parts = command.args.split()
    if len(parts) < 2:
        await message.reply("⚠️ /give_stars [user_id] [amount]"); return
    try:
        target_uid, amount = str(parts[0]), int(parts[1])
    except:
        await message.reply("❌ Неверный формат"); return
    stars_bal[target_uid] = stars_bal.get(target_uid, 0) + amount
    save_data()
    await message.reply(f"✅ Выдано {amount}⭐ пользователю {target_uid}\nНовый баланс: {stars_bal[target_uid]}⭐")

# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════
async def main():
    load_data()
    print("⚔️ SkinVault Bot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

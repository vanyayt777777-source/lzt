import os
import sys
import asyncio
import logging
import sqlite3
import json
import time
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, InputPeerUser, InputPeerChat, InputPeerChannel
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, 
    PeerIdInvalidError, ChatAdminRequiredError,
    UserPrivacyRestrictedError, RPCError
)
from telethon.sessions import StringSession
import requests

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

# Настройки из переменных окружения
API_ID = int(os.getenv('API_ID', '32480523'))
API_HASH = os.getenv('API_HASH', '147839735c9fa4e83451209e9b55cfc5')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN', '549010:AAppnlCnLcg0vq9FR5CKDE8vpatHDV5FYvT')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# Создаем клиента
bot = TelegramClient('vest_soft_bot', API_ID, API_HASH)

# Хранилище временных данных
user_sessions = {}
user_mailing = {}
user_temp = {}
active_mailings = {}  # Активные рассылки {mailing_id: data}

# База данных
def init_db():
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  subscription_end TIMESTAMP,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица аккаунтов
    c.execute('''CREATE TABLE IF NOT EXISTS accounts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  phone TEXT,
                  session_string TEXT,
                  is_active INTEGER DEFAULT 1,
                  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица чатов
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  account_id INTEGER,
                  chat_id INTEGER,
                  chat_title TEXT,
                  chat_type TEXT,
                  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(user_id, account_id, chat_id))''')
    
    # Таблица рассылок
    c.execute('''CREATE TABLE IF NOT EXISTS mailings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  name TEXT,
                  message TEXT,
                  total_chats INTEGER,
                  sent INTEGER DEFAULT 0,
                  failed INTEGER DEFAULT 0,
                  status TEXT DEFAULT 'active',
                  delay INTEGER,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица промокодов
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes
                 (code TEXT PRIMARY KEY,
                  days INTEGER,
                  uses INTEGER DEFAULT 0,
                  max_uses INTEGER)''')
    
    # Таблица использованных промокодов
    c.execute('''CREATE TABLE IF NOT EXISTS used_promocodes
                 (user_id INTEGER,
                  code TEXT,
                  used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (user_id, code))''')
    
    # Добавляем промокоды
    c.execute("INSERT OR IGNORE INTO promocodes (code, days, max_uses) VALUES (?, ?, ?)",
              ('FREE', 1, 1000))
    c.execute("INSERT OR IGNORE INTO promocodes (code, days, max_uses) VALUES (?, ?, ?)",
              ('TEST30', 30, 10))
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Функция проверки подписки
def check_subscription(user_id):
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        try:
            sub_end = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            return sub_end > datetime.now()
        except:
            return False
    return False

# Функция создания платежа
async def create_crypto_invoice(amount_usd, user_id):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    
    bot_info = await bot.get_me()
    
    data = {
        "asset": "USDT",
        "amount": str(amount_usd),
        "description": f"Подписка Vest Soft - {user_id}",
        "payload": str(user_id),
        "paid_btn_name": "openBot",
        "paid_btn_url": f"https://t.me/{bot_info.username}"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        return None

# Клавиатуры
def main_keyboard():
    return [
        [Button.text("📱 Менеджер аккаунтов")],
        [Button.text("⚙️ Функции")],
        [Button.text("👤 Профиль")]
    ]

def accounts_keyboard():
    return [
        [Button.text("📱 Войти по номеру")],
        [Button.text("📋 Список аккаунтов")],
        [Button.text("🗑 Удалить аккаунт")],
        [Button.text("◀️ Назад")]
    ]

def functions_keyboard():
    return [
        [Button.text("📨 Создать рассылку")],
        [Button.text("👥 Загрузить чаты")],
        [Button.text("📊 Статус рассылок")],
        [Button.text("◀️ Назад")]
    ]

def profile_keyboard(has_subscription):
    keyboard = []
    if not has_subscription:
        keyboard.append([Button.text("💎 Купить подписку (25₽ навсегда)")])
        keyboard.append([Button.text("🎫 Активировать промокод")])
    keyboard.append([Button.text("◀️ Назад")])
    return keyboard

def back_keyboard():
    return [[Button.text("◀️ Отмена")]]

# ИСПРАВЛЕННАЯ ФУНКЦИЯ ЗАГРУЗКИ ЧАТОВ
async def load_account_chats(user_id, account_id, session_string):
    """Загружает чаты с аккаунта"""
    client = None
    try:
        # Создаем клиента из сохраненной сессии
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            return False, "Аккаунт не авторизован"
        
        # Получаем информацию о пользователе
        me = await client.get_me()
        logger.info(f"Загрузка чатов для аккаунта {me.phone}")
        
        # Получаем диалоги
        dialogs = await client.get_dialogs()
        
        if not dialogs:
            return False, "Нет доступных чатов"
        
        conn = sqlite3.connect('vest_soft.db')
        c = conn.cursor()
        
        # Удаляем старые чаты этого аккаунта
        c.execute("DELETE FROM chats WHERE user_id = ? AND account_id = ?", (user_id, account_id))
        
        chats_count = 0
        for dialog in dialogs:
            # Определяем тип чата
            if dialog.is_user:
                chat_type = 'user'
            elif dialog.is_group:
                chat_type = 'group'
            elif dialog.is_channel:
                chat_type = 'channel'
            else:
                continue
            
            # Получаем ID чата
            chat_id = dialog.id
            if hasattr(dialog.entity, 'username') and dialog.entity.username:
                chat_title = f"{dialog.name} (@{dialog.entity.username})"
            else:
                chat_title = dialog.name or "Без названия"
            
            try:
                c.execute('''INSERT OR IGNORE INTO chats 
                            (user_id, account_id, chat_id, chat_title, chat_type) 
                            VALUES (?, ?, ?, ?, ?)''',
                         (user_id, account_id, chat_id, chat_title[:100], chat_type))
                chats_count += 1
            except Exception as e:
                logger.error(f"Ошибка сохранения чата: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        await client.disconnect()
        
        return True, f"Загружено {chats_count} чатов"
        
    except Exception as e:
        logger.error(f"Ошибка загрузки чатов: {e}")
        if client:
            await client.disconnect()
        return False, str(e)

# Функция выполнения рассылки
async def run_mailing(mailing_id, user_id, account_ids, chat_ids, message, delay, total_count):
    """Функция для выполнения рассылки в фоне"""
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    
    # Получаем сессии аккаунтов
    accounts = []
    for acc_id in account_ids:
        c.execute("SELECT session_string FROM accounts WHERE id = ? AND user_id = ?", (acc_id, user_id))
        result = c.fetchone()
        if result:
            accounts.append({'id': acc_id, 'session': result[0]})
    
    conn.close()
    
    sent = 0
    failed = 0
    
    # Для каждого аккаунта создаем клиента
    clients = []
    for acc in accounts:
        try:
            client = TelegramClient(StringSession(acc['session']), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                clients.append({'client': client, 'id': acc['id']})
        except Exception as e:
            logger.error(f"Ошибка подключения аккаунта: {e}")
    
    if not clients:
        # Обновляем статус рассылки
        conn = sqlite3.connect('vest_soft.db')
        c = conn.cursor()
        c.execute("UPDATE mailings SET status = 'failed' WHERE id = ?", (mailing_id,))
        conn.commit()
        conn.close()
        
        await bot.send_message(
            user_id,
            f"❌ **Ошибка рассылки**\n\nНе удалось подключиться ни к одному аккаунту",
            parse_mode='md'
        )
        return
    
    # Отправляем сообщения
    for chat_id in chat_ids:
        try:
            # Выбираем случайный аккаунт из доступных
            acc = random.choice(clients)
            
            # Отправляем сообщение
            await acc['client'].send_message(chat_id, message)
            sent += 1
            
            # Обновляем статистику
            conn = sqlite3.connect('vest_soft.db')
            c = conn.cursor()
            c.execute("UPDATE mailings SET sent = ? WHERE id = ?", (sent, mailing_id))
            conn.commit()
            conn.close()
            
            # Задержка
            await asyncio.sleep(delay)
            
        except FloodWaitError as e:
            # Ждем указанное время
            wait_time = e.seconds
            logger.warning(f"Flood wait: {wait_time} секунд")
            failed += 1
            
            # Обновляем статистику ошибок
            conn = sqlite3.connect('vest_soft.db')
            c = conn.cursor()
            c.execute("UPDATE mailings SET failed = ? WHERE id = ?", (failed, mailing_id))
            conn.commit()
            conn.close()
            
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            failed += 1
            # Обновляем статистику ошибок
            conn = sqlite3.connect('vest_soft.db')
            c = conn.cursor()
            c.execute("UPDATE mailings SET failed = ? WHERE id = ?", (failed, mailing_id))
            conn.commit()
            conn.close()
    
    # Закрываем всех клиентов
    for acc in clients:
        await acc['client'].disconnect()
    
    # Обновляем статус рассылки
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("UPDATE mailings SET status = 'completed' WHERE id = ?", (mailing_id,))
    conn.commit()
    conn.close()
    
    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        f"✅ **Рассылка #{mailing_id} завершена!**\n\n"
        f"📊 **Статистика:**\n"
        f"• Отправлено: {sent}\n"
        f"• Ошибок: {failed}\n"
        f"• Всего чатов: {total_count}",
        parse_mode='md'
    )

# Обработчики команд
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    username = event.sender.username or "NoUsername"
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
              (user_id, username))
    conn.commit()
    conn.close()
    
    await event.respond(
        "👋 Добро пожаловать в **Vest Soft**!\n\n"
        "🔹 Добавляйте аккаунты Telegram\n"
        "🔹 Загружайте чаты\n"
        "🔹 Делайте массовые рассылки\n\n"
        "Выберите раздел:",
        buttons=main_keyboard(),
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='📱 Менеджер аккаунтов'))
async def accounts_manager(event):
    await event.respond(
        "📱 **Менеджер аккаунтов**\n\n"
        "Выберите действие:",
        buttons=accounts_keyboard(),
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='📱 Войти по номеру'))
async def login_by_phone(event):
    user_id = event.sender_id
    
    # Проверяем лимит аккаунтов
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    
    if count >= 20:
        await event.respond("❌ Вы достигли лимита аккаунтов (20)")
        return
    
    user_temp[user_id] = {'action': 'waiting_phone'}
    await event.respond(
        "📱 Введите номер телефона в формате:\n"
        "`+79123456789`\n\n"
        "Или нажмите Отмена:",
        buttons=back_keyboard(),
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='📋 Список аккаунтов'))
async def list_accounts(event):
    user_id = event.sender_id
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT id, phone, added_at FROM accounts WHERE user_id = ?", (user_id,))
    accounts = c.fetchall()
    conn.close()
    
    if not accounts:
        await event.respond("❌ У вас нет добавленных аккаунтов")
        return
    
    text = "📋 **Ваши аккаунты:**\n\n"
    for i, (acc_id, phone, added_at) in enumerate(accounts, 1):
        try:
            added = datetime.strptime(added_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
        except:
            added = added_at[:10]
        text += f"{i}. ID: {acc_id} | `{phone}`\n   Добавлен: {added}\n\n"
    
    await event.respond(text, parse_mode='md')

@bot.on(events.NewMessage(pattern='🗑 Удалить аккаунт'))
async def delete_account(event):
    user_id = event.sender_id
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT id, phone FROM accounts WHERE user_id = ?", (user_id,))
    accounts = c.fetchall()
    conn.close()
    
    if not accounts:
        await event.respond("❌ У вас нет аккаунтов для удаления")
        return
    
    user_temp[user_id] = {'action': 'deleting_account', 'accounts': accounts}
    
    buttons = []
    for acc_id, phone in accounts[:10]:
        buttons.append([Button.text(f"❌ {phone}")])
    buttons.append([Button.text("◀️ Отмена")])
    
    await event.respond(
        "🗑 Выберите аккаунт для удаления:",
        buttons=buttons
    )

@bot.on(events.NewMessage(pattern='⚙️ Функции'))
async def functions_menu(event):
    user_id = event.sender_id
    
    if not check_subscription(user_id):
        await event.respond(
            "❌ Для использования функций нужна подписка!\n"
            "Приобретите её в профиле.",
            buttons=[[Button.text("👤 Перейти в профиль")]]
        )
        return
    
    await event.respond(
        "⚙️ **Доступные функции:**\n\n"
        "📨 Создать рассылку - массовая отправка сообщений\n"
        "👥 Загрузить чаты - загрузить чаты с аккаунтов\n"
        "📊 Статус рассылок - просмотр активных рассылок",
        buttons=functions_keyboard(),
        parse_mode='md'
    )

# ИСПРАВЛЕННЫЙ ОБРАБОТЧИК ЗАГРУЗКИ ЧАТОВ
@bot.on(events.NewMessage(pattern='👥 Загрузить чаты'))
async def load_chats(event):
    user_id = event.sender_id
    
    if not check_subscription(user_id):
        await event.respond("❌ Нет активной подписки!")
        return
    
    # Получаем аккаунты пользователя
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT id, phone FROM accounts WHERE user_id = ?", (user_id,))
    accounts = c.fetchall()
    conn.close()
    
    if not accounts:
        await event.respond("❌ Сначала добавьте аккаунты!")
        return
    
    # Сохраняем состояние
    user_temp[user_id] = {'action': 'loading_chats', 'accounts': accounts}
    
    text = "👥 **Загрузка чатов**\n\n"
    text += "Выберите аккаунт для загрузки:\n\n"
    
    buttons = []
    for acc_id, phone in accounts:
        buttons.append([Button.text(f"📱 {phone}")])
    buttons.append([Button.text("◀️ Отмена")])
    
    await event.respond(text, buttons=buttons, parse_mode='md')

# ИСПРАВЛЕННЫЙ ОБРАБОТЧИК ВЫБОРА АККАУНТА ДЛЯ ЗАГРУЗКИ
@bot.on(events.NewMessage)
async def handle_chat_loading(event):
    user_id = event.sender_id
    text = event.raw_text
    
    if user_id in user_temp and user_temp[user_id].get('action') == 'loading_chats':
        if text == "◀️ Отмена":
            del user_temp[user_id]
            await event.respond("Отменено", buttons=main_keyboard())
            return
        
        # Ищем выбранный аккаунт
        accounts = user_temp[user_id].get('accounts', [])
        selected_account = None
        
        for acc_id, phone in accounts:
            if text == f"📱 {phone}":
                selected_account = (acc_id, phone)
                break
        
        if selected_account:
            acc_id, phone = selected_account
            
            # Получаем сессию аккаунта
            conn = sqlite3.connect('vest_soft.db')
            c = conn.cursor()
            c.execute("SELECT session_string FROM accounts WHERE id = ? AND user_id = ?", (acc_id, user_id))
            result = c.fetchone()
            conn.close()
            
            if not result:
                await event.respond("❌ Ошибка: сессия аккаунта не найдена")
                return
            
            session_string = result[0]
            
            await event.respond(f"⏳ Загружаю чаты для {phone}... Это может занять некоторое время")
            
            # Загружаем чаты
            success, message = await load_account_chats(user_id, acc_id, session_string)
            
            if success:
                await event.respond(f"✅ {message}")
            else:
                await event.respond(f"❌ Ошибка загрузки: {message}")
            
            # Возвращаемся в меню функций
            await asyncio.sleep(2)
            await functions_menu(event)
            
            del user_temp[user_id]

@bot.on(events.NewMessage(pattern='📨 Создать рассылку'))
async def create_mailing(event):
    user_id = event.sender_id
    
    if not check_subscription(user_id):
        await event.respond("❌ Нет активной подписки!")
        return
    
    # Проверяем наличие аккаунтов
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,))
    accounts_count = c.fetchone()[0]
    
    # Проверяем наличие чатов
    c.execute("SELECT COUNT(*) FROM chats WHERE user_id = ?", (user_id,))
    chats_count = c.fetchone()[0]
    conn.close()
    
    if accounts_count == 0:
        await event.respond("❌ Сначала добавьте аккаунты!")
        return
    
    if chats_count == 0:
        await event.respond("❌ Сначала загрузите чаты (раздел Функции → Загрузить чаты)!")
        return
    
    # Начинаем создание рассылки
    user_mailing[user_id] = {
        'step': 'select_chats',
        'selected_chats': [],
        'selected_accounts': []
    }
    
    # Получаем все чаты пользователя
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT chat_id, chat_title, chat_type FROM chats WHERE user_id = ? ORDER BY chat_title", (user_id,))
    chats = c.fetchall()
    conn.close()
    
    if not chats:
        await event.respond("❌ Нет доступных чатов")
        return
    
    # Ограничиваем до 20 для выбора
    chats = chats[:20]
    user_temp[user_id] = {'chats': chats}
    
    text = "📨 **Создание рассылки**\n\n"
    text += "Шаг 1: Выберите чаты для рассылки (до 20)\n"
    text += "Нажимайте на чаты чтобы выбрать/отменить\n\n"
    text += "**Доступные чаты:**\n"
    
    buttons = []
    for chat_id, title, chat_type in chats:
        emoji = "👤" if chat_type == 'user' else "👥" if chat_type == 'group' else "📢"
        # Обрезаем длинные названия
        short_title = title[:30] + "..." if len(title) > 30 else title
        buttons.append([Button.text(f"{emoji} {short_title}")])
    
    buttons.append([Button.text("✅ Продолжить")])
    buttons.append([Button.text("◀️ Отмена")])
    
    await event.respond(text, buttons=buttons, parse_mode='md')

@bot.on(events.NewMessage(pattern='📊 Статус рассылок'))
async def mailing_status(event):
    user_id = event.sender_id
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute('''SELECT id, name, total_chats, sent, failed, status, created_at 
                 FROM mailings WHERE user_id = ? ORDER BY created_at DESC LIMIT 10''', 
              (user_id,))
    mailings = c.fetchall()
    conn.close()
    
    if not mailings:
        await event.respond("📊 У вас нет активных рассылок")
        return
    
    text = "📊 **Статус рассылок:**\n\n"
    for m in mailings:
        status_emoji = "🟢" if m[5] == 'active' else "✅" if m[5] == 'completed' else "🔴"
        text += f"{status_emoji} **Рассылка #{m[0]}**\n"
        text += f"📝 {m[1][:30]}\n"
        text += f"📊 {m[3]}/{m[2]} отправлено\n"
        text += f"❌ Ошибок: {m[4]}\n"
        text += f"📅 {m[6][:16]}\n\n"
    
    await event.respond(text, parse_mode='md')

@bot.on(events.NewMessage(pattern='👤 Профиль'))
async def profile(event):
    user_id = event.sender_id
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,))
    accounts_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM chats WHERE user_id = ?", (user_id,))
    chats_count = c.fetchone()[0]
    conn.close()
    
    has_sub = False
    sub_text = "❌ Нет активной подписки"
    
    if result and result[0]:
        try:
            sub_end = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            if sub_end > datetime.now():
                has_sub = True
                sub_text = f"✅ Активна до {sub_end.strftime('%d.%m.%Y %H:%M')}"
            else:
                sub_text = "❌ Подписка истекла"
        except:
            sub_text = "❌ Нет активной подписки"
    
    await event.respond(
        f"👤 **Ваш профиль**\n\n"
        f"ID: `{user_id}`\n"
        f"Аккаунтов: {accounts_count}/20\n"
        f"Загружено чатов: {chats_count}\n"
        f"Подписка: {sub_text}\n\n"
        f"**Тариф:**\n"
        f"• Навсегда - 25₽ (~0.28 USDT)",
        buttons=profile_keyboard(has_sub),
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='💎 Купить подписку'))
async def buy_subscription(event):
    user_id = event.sender_id
    
    usdt_amount = round(25 / 90, 2)
    
    invoice = await create_crypto_invoice(usdt_amount, user_id)
    
    if invoice and invoice.get('ok'):
        invoice_data = invoice['result']
        await event.respond(
            f"💎 **Покупка подписки**\n\n"
            f"Сумма: {usdt_amount} USDT (25₽)\n\n"
            f"Для оплаты нажмите кнопку ниже:",
            buttons=[[Button.url("💳 Оплатить USDT", invoice_data['pay_url'])]],
            parse_mode='md'
        )
    else:
        await event.respond(
            "❌ Ошибка создания платежа. Попробуйте позже."
        )

@bot.on(events.NewMessage(pattern='🎫 Активировать промокод'))
async def activate_promo(event):
    user_id = event.sender_id
    user_temp[user_id] = {'action': 'waiting_promo'}
    await event.respond(
        "🎫 Введите промокод:\n\n"
        "Доступные промокоды:\n"
        "• FREE - 1 день\n"
        "• TEST30 - 30 дней\n\n"
        "Или нажмите Отмена:",
        buttons=back_keyboard()
    )

@bot.on(events.NewMessage(pattern='◀️ Назад'))
async def back_to_main(event):
    user_id = event.sender_id
    if user_id in user_temp:
        del user_temp[user_id]
    if user_id in user_mailing:
        del user_mailing[user_id]
    if user_id in user_sessions:
        if 'client' in user_sessions[user_id]:
            try:
                await user_sessions[user_id]['client'].disconnect()
            except:
                pass
        del user_sessions[user_id]
    
    await event.respond(
        "Главное меню:",
        buttons=main_keyboard()
    )

@bot.on(events.NewMessage(pattern='◀️ Отмена'))
async def cancel_action(event):
    user_id = event.sender_id
    if user_id in user_temp:
        del user_temp[user_id]
    if user_id in user_mailing:
        del user_mailing[user_id]
    if user_id in user_sessions:
        if 'client' in user_sessions[user_id]:
            try:
                await user_sessions[user_id]['client'].disconnect()
            except:
                pass
        del user_sessions[user_id]
    
    await event.respond(
        "Действие отменено",
        buttons=main_keyboard()
    )

# Обработка выбора чатов для рассылки
@bot.on(events.NewMessage)
async def handle_chat_selection(event):
    user_id = event.sender_id
    text = event.raw_text
    
    if user_id in user_mailing and user_mailing[user_id].get('step') == 'select_chats':
        if text == "✅ Продолжить":
            selected = user_mailing[user_id]['selected_chats']
            if not selected:
                await event.respond("❌ Выберите хотя бы один чат!")
                return
            
            user_mailing[user_id]['step'] = 'enter_message'
            await event.respond(
                f"📝 Выбрано чатов: {len(selected)}\n\n"
                f"Шаг 2: Введите текст сообщения для рассылки:"
            )
            return
        
        if text == "◀️ Отмена":
            del user_mailing[user_id]
            await event.respond("Отменено", buttons=main_keyboard())
            return
        
        # Выбор/отмена чата
        if user_id in user_temp and 'chats' in user_temp[user_id]:
            chats = user_temp[user_id]['chats']
            for chat_id, title, chat_type in chats:
                emoji = "👤" if chat_type == 'user' else "👥" if chat_type == 'group' else "📢"
                short_title = title[:30] + "..." if len(title) > 30 else title
                display_text = f"{emoji} {short_title}"
                
                if text == display_text:
                    if chat_id in user_mailing[user_id]['selected_chats']:
                        user_mailing[user_id]['selected_chats'].remove(chat_id)
                        await event.respond(f"❌ Чат '{title[:50]}' убран из списка")
                    else:
                        if len(user_mailing[user_id]['selected_chats']) < 20:
                            user_mailing[user_id]['selected_chats'].append(chat_id)
                            await event.respond(f"✅ Чат '{title[:50]}' добавлен")
                        else:
                            await event.respond("❌ Максимум 20 чатов")
                    return

# Обработка ввода сообщения для рассылки
@bot.on(events.NewMessage)
async def handle_mailing_message(event):
    user_id = event.sender_id
    text = event.raw_text
    
    if user_id in user_mailing and user_mailing[user_id].get('step') == 'enter_message':
        if text == "◀️ Отмена":
            del user_mailing[user_id]
            await event.respond("Отменено", buttons=main_keyboard())
            return
        
        user_mailing[user_id]['message'] = text
        user_mailing[user_id]['step'] = 'enter_delay'
        
        await event.respond(
            f"📝 Сообщение сохранено\n\n"
            f"Шаг 3: Введите задержку между сообщениями (в секундах)\n"
            f"Например: 5"
        )

# Обработка ввода задержки
@bot.on(events.NewMessage)
async def handle_delay(event):
    user_id = event.sender_id
    text = event.raw_text
    
    if user_id in user_mailing and user_mailing[user_id].get('step') == 'enter_delay':
        if text == "◀️ Отмена":
            del user_mailing[user_id]
            await event.respond("Отменено", buttons=main_keyboard())
            return
        
        try:
            delay = int(text)
            if delay < 1:
                delay = 1
            if delay > 60:
                delay = 60
        except:
            await event.respond("❌ Введите число (секунды)")
            return
        
        user_mailing[user_id]['delay'] = delay
        user_mailing[user_id]['step'] = 'confirm'
        
        # Получаем аккаунты для рассылки
        conn = sqlite3.connect('vest_soft.db')
        c = conn.cursor()
        c.execute("SELECT id, phone FROM accounts WHERE user_id = ?", (user_id,))
        accounts = c.fetchall()
        conn.close()
        
        text = f"📨 **Проверьте данные рассылки:**\n\n"
        text += f"📝 Сообщение:\n{user_mailing[user_id]['message'][:100]}"
        text += f"{'...' if len(user_mailing[user_id]['message']) > 100 else ''}\n\n"
        text += f"⏱ Задержка: {delay} сек\n"
        text += f"📊 Чатов: {len(user_mailing[user_id]['selected_chats'])}\n"
        text += f"📱 Аккаунтов: {len(accounts)}\n\n"
        text += f"Запустить рассылку?"
        
        buttons = [
            [Button.text("✅ Запустить")],
            [Button.text("◀️ Отмена")]
        ]
        
        await event.respond(text, buttons=buttons, parse_mode='md')

# Запуск рассылки
@bot.on(events.NewMessage(pattern='✅ Запустить'))
async def start_mailing(event):
    user_id = event.sender_id
    
    if user_id in user_mailing and user_mailing[user_id].get('step') == 'confirm':
        data = user_mailing[user_id]
        
        # Получаем аккаунты
        conn = sqlite3.connect('vest_soft.db')
        c = conn.cursor()
        c.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,))
        accounts = [row[0] for row in c.fetchall()]
        
        # Создаем запись о рассылке
        mailing_name = f"Рассылка от {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        c.execute('''INSERT INTO mailings 
                    (user_id, name, message, total_chats, delay, status) 
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (user_id, mailing_name, data['message'], len(data['selected_chats']), data['delay'], 'active'))
        mailing_id = c.lastrowid
        conn.commit()
        conn.close()
        
        await event.respond(
            f"✅ **Рассылка #{mailing_id} запущена!**\n\n"
            f"Отправка началась, вы получите уведомление о завершении.",
            parse_mode='md'
        )
        
        # Запускаем рассылку в фоне
        asyncio.create_task(run_mailing(
            mailing_id, 
            user_id, 
            accounts, 
            data['selected_chats'], 
            data['message'], 
            data['delay'],
            len(data['selected_chats'])
        ))
        
        del user_mailing[user_id]

# Обработка ввода номера и кодов
@bot.on(events.NewMessage)
async def handle_auth_input(event):
    user_id = event.sender_id
    text = event.raw_text
    
    # Пропускаем команды
    if text.startswith('/'):
        return
    
    # Обработка ввода номера телефона
    if user_id in user_temp and user_temp[user_id].get('action') == 'waiting_phone':
        phone = text.strip()
        
        if not phone.startswith('+') or not phone[1:].replace(' ', '').isdigit():
            await event.respond("❌ Неверный формат. Используйте +79123456789")
            return
        
        phone = phone.replace(' ', '')
        
        client = TelegramClient(f'session_{user_id}_{int(time.time())}', API_ID, API_HASH)
        await client.connect()
        
        try:
            result = await client.send_code_request(phone)
            phone_code_hash = result.phone_code_hash
            
            user_sessions[user_id] = {
                'client': client,
                'phone': phone,
                'phone_code_hash': phone_code_hash,
                'step': 'waiting_code'
            }
            
            user_temp[user_id] = {'action': 'waiting_code'}
            await event.respond(
                "📲 Код подтверждения отправлен!\n"
                "Введите код из Telegram:"
            )
        except FloodWaitError as e:
            await event.respond(f"❌ Слишком много попыток. Подождите {e.seconds} секунд")
            await client.disconnect()
        except Exception as e:
            await event.respond(f"❌ Ошибка: {str(e)}")
            await client.disconnect()
    
    # Обработка ввода кода
    elif user_id in user_temp and user_temp[user_id].get('action') == 'waiting_code':
        code = text.strip()
        
        if user_id in user_sessions:
            session = user_sessions[user_id]
            client = session['client']
            
            try:
                await client.sign_in(
                    phone=session['phone'],
                    code=code,
                    phone_code_hash=session['phone_code_hash']
                )
                
                me = await client.get_me()
                
                # Сохраняем сессию
                session_string = StringSession.save(client.session)
                
                conn = sqlite3.connect('vest_soft.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO accounts (user_id, phone, session_string) VALUES (?, ?, ?)",
                    (user_id, session['phone'], session_string)
                )
                conn.commit()
                conn.close()
                
                await event.respond(
                    f"✅ Аккаунт успешно добавлен!\n"
                    f"Имя: {me.first_name}\n"
                    f"Username: @{me.username if me.username else 'нет'}"
                )
                
                await client.disconnect()
                del user_sessions[user_id]
                del user_temp[user_id]
                
            except SessionPasswordNeededError:
                user_temp[user_id] = {'action': 'waiting_2fa'}
                await event.respond(
                    "🔐 Включена двухфакторная аутентификация.\n"
                    "Введите пароль:"
                )
            except Exception as e:
                await event.respond(f"❌ Ошибка: {str(e)}")
                await client.disconnect()
    
    # Обработка 2FA пароля
    elif user_id in user_temp and user_temp[user_id].get('action') == 'waiting_2fa':
        password = text.strip()
        
        if user_id in user_sessions:
            client = user_sessions[user_id]['client']
            
            try:
                await client.sign_in(password=password)
                
                me = await client.get_me()
                
                session_string = StringSession.save(client.session)
                
                conn = sqlite3.connect('vest_soft.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO accounts (user_id, phone, session_string) VALUES (?, ?, ?)",
                    (user_id, user_sessions[user_id]['phone'], session_string)
                )
                conn.commit()
                conn.close()
                
                await event.respond(
                    f"✅ Аккаунт успешно добавлен!\n"
                    f"Имя: {me.first_name}\n"
                    f"Username: @{me.username if me.username else 'нет'}"
                )
                
                await client.disconnect()
                del user_sessions[user_id]
                del user_temp[user_id]
                
            except Exception as e:
                await event.respond(f"❌ Ошибка: {str(e)}")
    
    # Обработка промокода
    elif user_id in user_temp and user_temp[user_id].get('action') == 'waiting_promo':
        code = text.upper().strip()
        
        conn = sqlite3.connect('vest_soft.db')
        c = conn.cursor()
        
        c.execute("SELECT days, uses, max_uses FROM promocodes WHERE code = ?", (code,))
        promo = c.fetchone()
        
        if not promo:
            await event.respond("❌ Промокод не найден")
            conn.close()
            return
        
        days, uses, max_uses = promo
        
        if uses >= max_uses:
            await event.respond("❌ Промокод уже использован максимальное количество раз")
            conn.close()
            return
        
        c.execute("SELECT * FROM used_promocodes WHERE user_id = ? AND code = ?", (user_id, code))
        if c.fetchone():
            await event.respond("❌ Вы уже использовали этот промокод")
            conn.close()
            return
        
        sub_end = datetime.now() + timedelta(days=days)
        c.execute(
            "UPDATE users SET subscription_end = ? WHERE user_id = ?",
            (sub_end.strftime('%Y-%m-%d %H:%M:%S'), user_id)
        )
        
        c.execute("UPDATE promocodes SET uses = uses + 1 WHERE code = ?", (code,))
        c.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", (user_id, code))
        
        conn.commit()
        conn.close()
        
        del user_temp[user_id]
        
        await event.respond(
            f"✅ Промокод активирован!\n"
            f"Подписка активна {days} дн.\n\n"
            f"Спасибо за использование Vest Soft!"
        )
    
    # Обработка выбора аккаунта для удаления
    elif user_id in user_temp and user_temp[user_id].get('action') == 'deleting_account':
        if text.startswith('❌ '):
            phone = text.replace('❌ ', '')
            
            conn = sqlite3.connect('vest_soft.db')
            c = conn.cursor()
            c.execute("DELETE FROM accounts WHERE user_id = ? AND phone = ?", (user_id, phone))
            c.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))  # Удаляем связанные чаты
            conn.commit()
            conn.close()
            
            await event.respond(f"✅ Аккаунт {phone} удален")
            del user_temp[user_id]

# Запуск бота
async def main():
    logger.info("🚀 Бот Vest Soft запускается...")
    logger.info(f"API ID: {API_ID}")
    logger.info(f"Bot Token: {BOT_TOKEN[:10]}...")
    
    init_db()
    
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ Бот успешно запущен!")
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

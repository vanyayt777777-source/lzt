import os
import asyncio
import logging
import sqlite3
import json
import shutil
import zipfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, InputPeerUser, InputPeerChat, InputPeerChannel
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import requests

# Настройки из переменных окружения
API_ID = int(os.environ.get('API_ID', '32480523'))
API_HASH = os.environ.get('API_HASH', '147839735c9fa4e83451209e9b55cfc5')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CRYPTO_BOT_TOKEN = os.environ.get('CRYPTO_BOT_TOKEN', '549010:AAppnlCnLcg0vq9FR5CKDE8vpatHDV5FYvT')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# Создаем клиента
bot = TelegramClient('vest_soft_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Хранилище временных данных
user_sessions = {}  # Для хранения клиентов при авторизации
user_mailing = {}   # Для хранения данных рассылки
user_temp = {}      # Для временных данных

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
    except:
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
        "🔹 Делайте массовые рассылки\n"
        "🔹 Управляйте подпиской\n\n"
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
    c.execute("SELECT phone, added_at FROM accounts WHERE user_id = ?", (user_id,))
    accounts = c.fetchall()
    conn.close()
    
    if not accounts:
        await event.respond("❌ У вас нет добавленных аккаунтов")
        return
    
    text = "📋 **Ваши аккаунты:**\n\n"
    for i, (phone, added_at) in enumerate(accounts, 1):
        added = datetime.strptime(added_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
        text += f"{i}. `{phone}`\n   Добавлен: {added}\n\n"
    
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
    for acc_id, phone in accounts[:10]:  # Показываем первые 10
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
        "📊 Статус рассылок - просмотр активных рассылок",
        buttons=functions_keyboard(),
        parse_mode='md'
    )

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
    conn.close()
    
    if accounts_count == 0:
        await event.respond("❌ Сначала добавьте аккаунты!")
        return
    
    user_mailing[user_id] = {'step': 'select_accounts', 'selected_chats': []}
    
    # Получаем аккаунты пользователя
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT id, phone FROM accounts WHERE user_id = ?", (user_id,))
    accounts = c.fetchall()
    conn.close()
    
    text = "📨 **Создание рассылки**\n\n"
    text += "Шаг 1: Выберите аккаунты для загрузки чатов\n"
    text += "(можно выбрать несколько)\n\n"
    
    buttons = []
    for acc_id, phone in accounts:
        buttons.append([Button.text(f"📱 {phone}")])
    buttons.append([Button.text("✅ Загрузить чаты")])
    buttons.append([Button.text("◀️ Отмена")])
    
    await event.respond(text, buttons=buttons, parse_mode='md')

@bot.on(events.NewMessage(pattern='👤 Профиль'))
async def profile(event):
    user_id = event.sender_id
    
    conn = sqlite3.connect('vest_soft.db')
    c = conn.cursor()
    c.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,))
    accounts_count = c.fetchone()[0]
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
        f"Подписка: {sub_text}\n\n"
        f"**Тариф:**\n"
        f"• Навсегда - 25₽ (~0.28 USDT)",
        buttons=profile_keyboard(has_sub),
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='💎 Купить подписку'))
async def buy_subscription(event):
    user_id = event.sender_id
    
    usdt_amount = round(25 / 90, 2)  # 25₽ = 0.28 USDT
    
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
    if user_id in user_sessions:
        # Закрываем клиент если есть
        if 'client' in user_sessions[user_id]:
            asyncio.create_task(user_sessions[user_id]['client'].disconnect())
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
    if user_id in user_sessions:
        if 'client' in user_sessions[user_id]:
            asyncio.create_task(user_sessions[user_id]['client'].disconnect())
        del user_sessions[user_id]
    
    await event.respond(
        "Действие отменено",
        buttons=main_keyboard()
    )

# Обработка ввода номера и кодов
@bot.on(events.NewMessage)
async def handle_input(event):
    user_id = event.sender_id
    text = event.raw_text
    
    # Обработка ввода номера телефона
    if user_id in user_temp and user_temp[user_id].get('action') == 'waiting_phone':
        phone = text.strip()
        
        # Валидация номера
        if not phone.startswith('+') or not phone[1:].replace(' ', '').isdigit():
            await event.respond("❌ Неверный формат. Используйте +79123456789")
            return
        
        # Очищаем номер от пробелов
        phone = phone.replace(' ', '')
        
        # Создаем клиента для авторизации
        client = TelegramClient(f'session_{user_id}_{int(time.time())}', API_ID, API_HASH)
        await client.connect()
        
        try:
            # Отправляем код
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
                # Пробуем войти с кодом
                await client.sign_in(
                    phone=session['phone'],
                    code=code,
                    phone_code_hash=session['phone_code_hash']
                )
                
                # Успешный вход
                me = await client.get_me()
                
                # Сохраняем сессию
                session_string = client.session.save()
                
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
                # Требуется 2FA
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
                # Вход с 2FA
                await client.sign_in(password=password)
                
                me = await client.get_me()
                
                # Сохраняем сессию
                session_string = client.session.save()
                
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
        
        # Проверяем промокод
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
        
        # Проверяем, не использовал ли пользователь
        c.execute("SELECT * FROM used_promocodes WHERE user_id = ? AND code = ?", (user_id, code))
        if c.fetchone():
            await event.respond("❌ Вы уже использовали этот промокод")
            conn.close()
            return
        
        # Активируем подписку
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
            conn.commit()
            conn.close()
            
            await event.respond(f"✅ Аккаунт {phone} удален")
            del user_temp[user_id]

# Запуск бота
async def main():
    print("🚀 Бот Vest Soft запускается...")
    print(f"API ID: {API_ID}")
    print(f"Bot Token: {BOT_TOKEN[:10]}...")
    
    init_db()
    print("✅ База данных инициализирована")
    
    print("✅ Бот успешно запущен!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

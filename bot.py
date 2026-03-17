# main.py
import os
import asyncio
import random
import json
import logging
import shutil
import string
import chardet
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, SessionPasswordNeeded, UsernameInvalid, PeerIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired
from pyrogram.enums import ChatType, ChatMemberStatus
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "32480523"))
API_HASH = os.getenv("API_HASH", "147839735c9fa4e83451209e9b55cfc5")
SESSIONS_DIR = "sessions"
DATA_FILE = "accounts_data.json"
MESSAGES_FILE = "messages.json"
TEMP_DIR = "temp_sessions"
PHOTOS_DIR = "photos"
CHATS_FILE = "chats_data.json"
CHANNELS_FILE = "channels_data.json"
ADMIN_USERNAME = "v3estnikov"
SPAM_BOT = "spambot"

# Создаем необходимые папки
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)

# Класс для проверки спам-блока
class SpamBlockChecker:
    @staticmethod
    async def check_spam_block(client: Client) -> Tuple[bool, str, str]:
        """Проверяет, не в спам-блоке ли аккаунт"""
        try:
            # Пробуем найти бота @spambot
            try:
                spambot = await client.get_users(SPAM_BOT)
            except PeerIdInvalid:
                return False, "❌ Не удалось найти бота @spambot", "error"
            
            # Отправляем /start
            await client.send_message(SPAM_BOT, "/start")
            
            # Ждем ответа
            await asyncio.sleep(2)
            
            # Получаем последние сообщения
            bot_response = None
            async for message in client.get_chat_history(SPAM_BOT, limit=5):
                if message.from_user and message.from_user.is_bot:
                    bot_response = message.text
                    break
            
            if not bot_response:
                return False, "❌ Бот не ответил", "error"
            
            # Анализируем ответ
            restricted_phrases = [
                "limited", "restricted", "banned", "spam",
                "заблокирован", "ограничен", "спам", "не может",
                "невозможно", "ошибка", "error", "limited"
            ]
            
            response_lower = bot_response.lower()
            is_restricted = any(phrase in response_lower for phrase in restricted_phrases)
            
            if is_restricted:
                return False, f"⚠️ **Аккаунт в спам-блоке!**\n\nОтвет бота:\n```{bot_response[:200]}```", "restricted"
            else:
                return True, f"✅ **Аккаунт чист!**\n\nОтвет бота:\n```{bot_response[:200]}```", "clean"
            
        except FloodWait as e:
            return False, f"⏳ Flood wait: {e.value} секунд", "flood"
        except Exception as e:
            logger.error(f"Ошибка при проверке спам-блока: {e}")
            return False, f"❌ Ошибка: {str(e)}", "error"

# Класс для создания каналов
class ChannelManager:
    def __init__(self):
        self.channels_data = self.load_channels()
        self.creation_tasks = {}
    
    def load_channels(self) -> Dict:
        """Загружает данные каналов"""
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"channels": {}}
    
    def save_channels(self):
        """Сохраняет данные каналов"""
        with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.channels_data, f, ensure_ascii=False, indent=2)
    
    async def create_multiple_channels(self, user_id: int, account_name: str, count: int, 
                                       base_title: str, description: str = "") -> str:
        """Создает несколько каналов"""
        task_id = f"{user_id}_{account_name}_{datetime.now().timestamp()}"
        
        task = asyncio.create_task(
            self._create_channels_process(user_id, account_name, count, base_title, description, task_id)
        )
        self.creation_tasks[task_id] = task
        
        return task_id
    
    async def _create_channels_process(self, user_id: int, account_name: str, count: int,
                                       base_title: str, description: str, task_id: str):
        """Процесс создания нескольких каналов"""
        try:
            client = account_manager.accounts.get(account_name)
            if not client:
                logger.error(f"Аккаунт {account_name} не найден")
                return
            
            created = []
            failed = 0
            
            for i in range(1, count + 1):
                if task_id not in self.creation_tasks:
                    break
                
                if count > 1:
                    title = f"{base_title} {i}"
                else:
                    title = base_title
                
                try:
                    channel = await client.create_channel(title, description)
                    created.append({
                        'id': channel.id,
                        'title': title,
                        'created_at': datetime.now().isoformat()
                    })
                    
                    logger.info(f"[{task_id}] Создан канал {i}/{count}: {title}")
                    
                    if i < count:
                        await asyncio.sleep(random.uniform(5, 10))
                    
                except FloodWait as e:
                    logger.warning(f"Flood wait: {e.value} секунд")
                    await asyncio.sleep(e.value)
                    failed += 1
                except Exception as e:
                    logger.error(f"Ошибка создания канала {title}: {e}")
                    failed += 1
            
            # Сохраняем результаты
            if str(user_id) not in self.channels_data["channels"]:
                self.channels_data["channels"][str(user_id)] = {}
            
            if account_name not in self.channels_data["channels"][str(user_id)]:
                self.channels_data["channels"][str(user_id)][account_name] = []
            
            self.channels_data["channels"][str(user_id)][account_name].extend(created)
            self.save_channels()
            
            # Отправляем отчет
            try:
                bot_client = next(iter(account_manager.accounts.values()))
                if bot_client:
                    await bot_client.send_message(
                        user_id,
                        f"✅ **Создание каналов завершено**\n\n"
                        f"• Аккаунт: {account_manager.get_account_display_name(account_name)}\n"
                        f"• Создано: {len(created)}/{count}\n"
                        f"• Ошибок: {failed}\n\n"
                        f"Созданные каналы:\n" + "\n".join([f"• {c['title']}" for c in created[:10]])
                    )
            except:
                pass
            
        except asyncio.CancelledError:
            logger.info(f"Создание каналов {task_id} остановлено")
        except Exception as e:
            logger.error(f"Ошибка создания каналов: {e}")
    
    def stop_creation(self, task_id: str):
        """Останавливает создание каналов"""
        if task_id in self.creation_tasks:
            self.creation_tasks[task_id].cancel()
            del self.creation_tasks[task_id]

# Класс для управления чатами
class ChatManager:
    def __init__(self):
        self.chats_data = self.load_chats()
        self.selected_chats = {}
    
    def load_chats(self) -> Dict:
        """Загружает данные чатов"""
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"chats": {}}
    
    def save_chats(self):
        """Сохраняет данные чатов"""
        with open(CHATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.chats_data, f, ensure_ascii=False, indent=2)
    
    async def load_user_chats(self, client: Client, user_id: int, account_name: str) -> List[Dict]:
        """Загружает чаты пользователя"""
        chats = []
        try:
            async for dialog in client.get_dialogs():
                chat = {
                    'id': dialog.chat.id,
                    'title': dialog.chat.title or f"{dialog.chat.first_name or ''} {dialog.chat.last_name or ''}".strip() or "Без названия",
                    'type': str(dialog.chat.type).split('.')[-1],
                    'username': dialog.chat.username,
                    'unread_count': dialog.unread_messages_count
                }
                chats.append(chat)
            
            if str(user_id) not in self.chats_data["chats"]:
                self.chats_data["chats"][str(user_id)] = {}
            
            self.chats_data["chats"][str(user_id)][account_name] = {
                'loaded_at': datetime.now().isoformat(),
                'chats': chats
            }
            self.save_chats()
            
            return chats
        except Exception as e:
            logger.error(f"Ошибка загрузки чатов: {e}")
            return []
    
    def get_user_chats(self, user_id: int, account_name: str) -> List[Dict]:
        """Получает сохраненные чаты пользователя"""
        try:
            return self.chats_data["chats"][str(user_id)][account_name]['chats']
        except:
            return []
    
    def get_chats_page(self, user_id: int, account_name: str, page: int = 0, per_page: int = 10) -> Tuple[List[Dict], int]:
        """Получает страницу чатов"""
        chats = self.get_user_chats(user_id, account_name)
        if not chats:
            return [], 0
        
        start = page * per_page
        end = start + per_page
        page_chats = chats[start:end]
        total_pages = (len(chats) + per_page - 1) // per_page
        
        return page_chats, total_pages
    
    def select_chat(self, user_id: int, chat_id: int):
        """Выбирает чат для рассылки"""
        if user_id not in self.selected_chats:
            self.selected_chats[user_id] = []
        
        if chat_id not in self.selected_chats[user_id]:
            self.selected_chats[user_id].append(chat_id)
    
    def unselect_chat(self, user_id: int, chat_id: int):
        """Отменяет выбор чата"""
        if user_id in self.selected_chats and chat_id in self.selected_chats[user_id]:
            self.selected_chats[user_id].remove(chat_id)
    
    def get_selected_chats(self, user_id: int) -> List[int]:
        """Получает выбранные чаты"""
        return self.selected_chats.get(user_id, [])
    
    def clear_selected(self, user_id: int):
        """Очищает выбранные чаты"""
        if user_id in self.selected_chats:
            self.selected_chats[user_id] = []

# Класс для управления рассылкой
class MailingManager:
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.mailing_tasks = {}
        self.mailing_stats = {}
    
    async def start_mailing(self, user_id: int, account_name: str, chats: List[int], 
                           message_text: str, count: int, delay: int):
        """Запускает рассылку"""
        task_id = f"{user_id}_{account_name}_{datetime.now().timestamp()}"
        
        task = asyncio.create_task(
            self._mailing_process(user_id, account_name, chats, message_text, count, delay, task_id)
        )
        self.mailing_tasks[task_id] = task
        
        self.mailing_stats[task_id] = {
            'user_id': user_id,
            'account_name': account_name,
            'total_chats': len(chats),
            'total_messages': count * len(chats),
            'sent': 0,
            'failed': 0,
            'status': 'running',
            'start_time': datetime.now().isoformat()
        }
        
        return task_id
    
    async def stop_mailing(self, task_id: str):
        """Останавливает рассылку"""
        if task_id in self.mailing_tasks:
            self.mailing_tasks[task_id].cancel()
            del self.mailing_tasks[task_id]
        
        if task_id in self.mailing_stats:
            self.mailing_stats[task_id]['status'] = 'stopped'
    
    async def _mailing_process(self, user_id: int, account_name: str, chats: List[int],
                               message_text: str, count: int, delay: int, task_id: str):
        """Процесс рассылки"""
        try:
            client = self.account_manager.accounts.get(account_name)
            if not client:
                logger.error(f"Аккаунт {account_name} не найден")
                return
            
            stats = self.mailing_stats[task_id]
            
            for chat_id in chats:
                if task_id not in self.mailing_tasks:
                    break
                
                for i in range(count):
                    if task_id not in self.mailing_tasks:
                        break
                    
                    try:
                        async with client.action(chat_id, "typing"):
                            await asyncio.sleep(random.uniform(2, 5))
                        
                        await client.send_message(chat_id, message_text)
                        
                        stats['sent'] += 1
                        logger.info(f"[Рассылка {task_id}] Отправлено в чат {chat_id} ({i+1}/{count})")
                        
                        if i < count - 1:
                            await asyncio.sleep(delay)
                        
                    except FloodWait as e:
                        logger.warning(f"Flood wait: {e.value} секунд")
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        logger.error(f"Ошибка отправки в чат {chat_id}: {e}")
                        stats['failed'] += 1
                
                if chat_id != chats[-1]:
                    await asyncio.sleep(delay * 2)
            
            stats['status'] = 'completed'
            
        except asyncio.CancelledError:
            logger.info(f"Рассылка {task_id} остановлена")
        except Exception as e:
            logger.error(f"Ошибка рассылки: {e}")
            if task_id in self.mailing_stats:
                self.mailing_stats[task_id]['status'] = 'error'
    
    def get_stats(self, task_id: str) -> Optional[Dict]:
        """Получает статистику рассылки"""
        return self.mailing_stats.get(task_id)

# Класс для рандомизации поведения
class BehaviorRandomizer:
    def __init__(self):
        self.personalities = [
            {
                "name": "Болтливый",
                "speed": "fast",
                "emoji_usage": 0.8,
                "message_length": "long",
                "typing_speed": (2, 5),
                "reaction_chance": 0.3,
                "grammar": "good",
                "response_delay": (2, 8)
            },
            {
                "name": "Спокойный",
                "speed": "medium",
                "emoji_usage": 0.4,
                "message_length": "medium",
                "typing_speed": (5, 10),
                "reaction_chance": 0.2,
                "grammar": "good",
                "response_delay": (5, 15)
            },
            {
                "name": "Молчаливый",
                "speed": "slow",
                "emoji_usage": 0.2,
                "message_length": "short",
                "typing_speed": (8, 15),
                "reaction_chance": 0.1,
                "grammar": "medium",
                "response_delay": (10, 30)
            },
            {
                "name": "Эмоциональный",
                "speed": "fast",
                "emoji_usage": 0.9,
                "message_length": "medium",
                "typing_speed": (3, 6),
                "reaction_chance": 0.5,
                "grammar": "medium",
                "response_delay": (3, 10)
            },
            {
                "name": "Задумчивый",
                "speed": "slow",
                "emoji_usage": 0.1,
                "message_length": "long",
                "typing_speed": (10, 20),
                "reaction_chance": 0.15,
                "grammar": "excellent",
                "response_delay": (8, 25)
            }
        ]
        
        self.reactions = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "😮", "😂", "😎", "🤝", "💯"]
    
    def get_random_personality(self) -> Dict:
        return random.choice(self.personalities)
    
    def get_random_reaction(self) -> str:
        return random.choice(self.reactions)
    
    def should_react(self, personality: Dict, message_index: int) -> bool:
        if message_index % random.randint(10, 20) == 0:
            return random.random() < personality["reaction_chance"]
        return False
    
    def get_typing_delay(self, personality: Dict) -> float:
        min_delay, max_delay = personality["typing_speed"]
        return random.uniform(min_delay, max_delay)
    
    def get_response_delay(self, personality: Dict) -> float:
        min_delay, max_delay = personality["response_delay"]
        return random.uniform(min_delay, max_delay)

# Класс для управления фото
class PhotoManager:
    def __init__(self):
        self.photos = self.load_photos()
    
    def load_photos(self) -> List[str]:
        photos = []
        if os.path.exists(PHOTOS_DIR):
            for file in os.listdir(PHOTOS_DIR):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    photos.append(os.path.join(PHOTOS_DIR, file))
        
        if not photos:
            logger.warning(f"В папке {PHOTOS_DIR} нет фото")
        
        return photos
    
    def get_random_photo(self) -> Optional[str]:
        if self.photos:
            return random.choice(self.photos)
        return None
    
    def should_send_photo(self, message_index: int) -> bool:
        return message_index % random.randint(30, 50) == 0 and self.photos

# Класс для управления диалогами
class DialogueManager:
    def __init__(self):
        self.dialogues = self.load_dialogues()
        self.behavior_randomizer = BehaviorRandomizer()
        self.photo_manager = PhotoManager()
    
    def load_dialogues(self) -> List[List[Dict]]:
        """Загружает диалоги"""
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            dialogues = [
                [
                    {"from": "A", "text": "Привет! Как дела?"},
                    {"from": "B", "text": "Привет! Нормально, а у тебя?"},
                ]
            ]
            return dialogues
    
    def get_random_dialogue(self) -> List[Dict]:
        return random.choice(self.dialogues)

# Класс для управления аккаунтами
class AccountManager:
    def __init__(self):
        self.accounts: Dict[str, Client] = {}
        self.active_warmups: Dict[str, Dict] = {}
        self.pending_authorizations: Dict[int, Dict] = {}
        self.account_personalities: Dict[str, Dict] = {}
        self.account_spam_status: Dict[str, Dict] = {}
        self.load_accounts_data()
    
    def load_accounts_data(self):
        """Загружает данные аккаунтов из файла"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.accounts_data = json.load(f)
                logger.info(f"Загружено {len(self.accounts_data)} аккаунтов из {DATA_FILE}")
            except Exception as e:
                logger.error(f"Ошибка загрузки {DATA_FILE}: {e}")
                self.accounts_data = {}
        else:
            self.accounts_data = {}
            self.save_accounts_data()
    
    def save_accounts_data(self):
        """Сохраняет данные аккаунтов в файл"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.accounts_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.accounts_data)} аккаунтов в {DATA_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения {DATA_FILE}: {e}")
    
    def get_available_sessions(self) -> List[str]:
        """Возвращает список доступных session файлов и аккаунтов из данных"""
        # Получаем аккаунты из данных
        accounts_from_data = list(self.accounts_data.keys())
        
        # Получаем файлы сессий
        session_files = []
        for file in os.listdir(SESSIONS_DIR):
            if file.endswith('.session'):
                session_name = file.replace('.session', '')
                session_files.append(session_name)
        
        # Объединяем и удаляем дубликаты
        all_accounts = list(set(accounts_from_data + session_files))
        logger.info(f"Найдено аккаунтов: из данных {len(accounts_from_data)}, из файлов {len(session_files)}, всего {len(all_accounts)}")
        
        return all_accounts
    
    async def add_account_from_string(self, session_string: str, session_name: str = None) -> Tuple[bool, str, Optional[str]]:
        """Добавляет аккаунт из строки сессии"""
        try:
            if not session_name:
                session_name = f"session_{int(datetime.now().timestamp())}"
            
            session_path = os.path.join(SESSIONS_DIR, session_name)
            
            # Создаем клиента из строки сессии
            client = Client(session_name, api_id=API_ID, api_hash=API_HASH, session_string=session_string)
            await client.connect()
            
            me = await client.get_me()
            if not me:
                await client.disconnect()
                return False, "Не удалось получить данные аккаунта", None
            
            # Сохраняем сессию в файл
            await client.storage.save()
            
            # Отправляем простое приветствие
            try:
                await client.send_message(ADMIN_USERNAME, f"👋 Привет! Аккаунт {me.first_name} успешно добавлен!")
            except:
                pass
            
            await client.disconnect()
            
            # Сохраняем данные аккаунта
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'last_name': me.last_name or "",
                'bio': "",
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'string_session',
                'spam_checked': False
            }
            self.save_accounts_data()
            
            username_text = f" (@{me.username})" if me.username else ""
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен", session_name
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении аккаунта из строки: {e}")
            return False, f"❌ Ошибка: {str(e)}", None
    
    async def set_random_username(self, client: Client) -> Optional[str]:
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                new_username = ''.join(random.choices(string.ascii_lowercase, k=random.randint(8, 12)))
                await client.set_username(new_username)
                logger.info(f"Установлен username: {new_username}")
                return new_username
            except UsernameInvalid:
                continue
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                logger.error(f"Ошибка при установке username: {e}")
                return None
        return None
    
    async def set_account_profile(self, client: Client, first_name: str = None, 
                                 last_name: str = None, bio: str = None) -> bool:
        """Изменяет имя и описание аккаунта"""
        try:
            me = await client.get_me()
            await client.update_profile(
                first_name=first_name or me.first_name,
                last_name=last_name or me.last_name or "",
                bio=bio or ""
            )
            logger.info(f"Профиль обновлен: {first_name} {last_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления профиля: {e}")
            return False
    
    async def check_spam_status(self, session_name: str, client: Client = None) -> Tuple[bool, str]:
        """Проверяет статус спам-блока для аккаунта"""
        need_close = False
        if not client:
            if session_name not in self.accounts:
                # Добавляем аккаунт временно
                success = await self.add_account(session_name, BehaviorRandomizer())
                if not success:
                    return False, "❌ Не удалось активировать аккаунт"
            client = self.accounts.get(session_name)
            need_close = False  # Не закрываем, если это постоянный клиент
        
        try:
            success, message, status = await SpamBlockChecker.check_spam_block(client)
            
            if success:
                self.account_spam_status[session_name] = {
                    'status': 'clean',
                    'message': message,
                    'checked_at': datetime.now().isoformat()
                }
            else:
                self.account_spam_status[session_name] = {
                    'status': status,
                    'message': message,
                    'checked_at': datetime.now().isoformat()
                }
            
            return success, message
            
        except Exception as e:
            logger.error(f"Ошибка проверки спам-блока: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def send_test_message(self, client: Client, session_name: str) -> bool:
        """Отправляет простое приветствие"""
        try:
            me = await client.get_me()
            await client.send_message(
                ADMIN_USERNAME, 
                f"👋 Привет! Аккаунт {me.first_name} (@{me.username if me.username else 'без username'}) готов к работе!"
            )
            logger.info(f"Приветствие отправлено {ADMIN_USERNAME}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке приветствия: {e}")
            return False
    
    async def add_account_by_session_file(self, file_path: str, filename: str) -> Tuple[bool, str]:
        """Добавляет аккаунт через session файл или txt файл"""
        try:
            session_name = None
            client = None
            dest_path = None
            
            # Если это .session файл
            if filename.endswith('.session'):
                dest_path = os.path.join(SESSIONS_DIR, filename)
                shutil.copy2(file_path, dest_path)
                
                session_name = filename.replace('.session', '')
                client = Client(dest_path.replace('.session', ''), api_id=API_ID, api_hash=API_HASH)
                logger.info(f"Загрузка .session файла: {filename}, session_name: {session_name}")
            
            # Если это .txt файл со строкой сессии
            elif filename.endswith('.txt'):
                # Определяем кодировку файла
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
                    logger.info(f"Определена кодировка файла: {encoding}")
                
                # Читаем файл в правильной кодировке
                with open(file_path, 'r', encoding=encoding) as f:
                    session_string = f.read().strip()
                
                # Проверяем, что строка не пустая
                if not session_string:
                    return False, "❌ Файл пуст"
                
                # Пробуем декодировать если это base64
                try:
                    # Проверяем, похоже ли на base64
                    if len(session_string) % 4 == 0 and all(c in string.ascii_letters + string.digits + '+/=' for c in session_string):
                        decoded = base64.b64decode(session_string).decode('utf-8', errors='ignore')
                        logger.info("Строка сессии в base64, декодирована")
                        session_string = decoded
                except:
                    pass
                
                session_name = f"session_{int(datetime.now().timestamp())}"
                logger.info(f"Загрузка .txt файла, создаем сессию: {session_name}")
                
                try:
                    client = Client(session_name, api_id=API_ID, api_hash=API_HASH, session_string=session_string)
                except Exception as e:
                    logger.error(f"Ошибка создания клиента из строки: {e}")
                    return False, f"❌ Неверный формат строки сессии: {str(e)}"
            
            else:
                return False, "❌ Неподдерживаемый формат файла. Используйте .session или .txt"
            
            # Подключаемся
            logger.info(f"Подключение к аккаунту...")
            await client.connect()
            
            me = await client.get_me()
            if not me:
                await client.disconnect()
                return False, "❌ Не удалось получить данные аккаунта"
            
            logger.info(f"Успешное подключение: {me.first_name} (ID: {me.id})")
            
            if not me.username:
                logger.info(f"У аккаунта {me.first_name} нет username, устанавливаем случайный...")
                new_username = await self.set_random_username(client)
                if new_username:
                    me = await client.get_me()
            
            # Сохраняем сессию
            await client.storage.save()
            logger.info(f"Сессия сохранена")
            
            # Отправляем простое приветствие
            await self.send_test_message(client, session_name)
            
            await client.disconnect()
            logger.info(f"Клиент отключен")
            
            # Сохраняем данные аккаунта
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'last_name': me.last_name or "",
                'bio': "",
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'session_file' if filename.endswith('.session') else 'txt_file',
                'spam_checked': False
            }
            self.save_accounts_data()
            logger.info(f"Данные аккаунта сохранены, всего аккаунтов: {len(self.accounts_data)}")
            
            username_text = f" (@{me.username})" if me.username else ""
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен"
            
        except UnicodeDecodeError as e:
            logger.error(f"Ошибка кодировки файла: {e}")
            return False, f"❌ Ошибка кодировки файла. Убедитесь, что файл в правильной кодировке."
        except Exception as e:
            logger.error(f"Ошибка при добавлении файла: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def start_phone_authorization(self, user_id: int, phone_number: str) -> Tuple[bool, str]:
        """Начинает авторизацию по номеру телефона"""
        try:
            session_name = f"temp_{user_id}_{int(datetime.now().timestamp())}"
            temp_path = os.path.join(TEMP_DIR, session_name)
            
            client = Client(temp_path, api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await client.connect()
            
            sent_code = await client.send_code(phone_number)
            
            self.pending_authorizations[user_id] = {
                'client': client,
                'phone': phone_number,
                'phone_code_hash': sent_code.phone_code_hash,
                'session_name': session_name,
                'step': 'waiting_code',
                'temp_path': temp_path,
                'created_at': datetime.now().isoformat()
            }
            
            logger.info(f"Код отправлен пользователю {user_id}, hash: {sent_code.phone_code_hash}")
            return True, "✅ Код подтверждения отправлен на ваш телефон"
            
        except PhoneNumberInvalid:
            return False, "❌ Неверный номер телефона"
        except FloodWait as e:
            return False, f"❌ Слишком много попыток. Подождите {e.value} секунд"
        except Exception as e:
            logger.error(f"Ошибка при отправке кода: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def complete_phone_authorization(self, user_id: int, code: str = None, password: str = None) -> Tuple[bool, str]:
        """Завершает авторизацию по коду"""
        try:
            if user_id not in self.pending_authorizations:
                return False, "❌ Сессия авторизации не найдена. Начните заново."
            
            auth_data = self.pending_authorizations[user_id]
            client = auth_data['client']
            
            try:
                if password:
                    logger.info(f"Попытка входа с паролем для пользователя {user_id}")
                    await client.check_password(password)
                else:
                    logger.info(f"Попытка входа с кодом для пользователя {user_id}")
                    await client.sign_in(
                        phone_number=auth_data['phone'],
                        phone_code_hash=auth_data['phone_code_hash'],
                        phone_code=code
                    )
            except SessionPasswordNeeded:
                logger.info(f"Требуется 2FA для пользователя {user_id}")
                auth_data['step'] = 'waiting_password'
                return False, "password_needed"
            except PhoneCodeInvalid:
                return False, "❌ Неверный код подтверждения"
            except PhoneCodeExpired:
                return False, "❌ Код подтверждения истек. Запросите новый."
            except Exception as e:
                return False, f"❌ Ошибка при входе: {str(e)}"
            
            me = await client.get_me()
            logger.info(f"Успешный вход: {me.first_name} (ID: {me.id})")
            
            if not me.username:
                logger.info(f"У аккаунта {me.first_name} нет username, устанавливаем случайный...")
                new_username = await self.set_random_username(client)
                if new_username:
                    me = await client.get_me()
            
            # Сохраняем сессию
            session_name = f"{me.phone_number or me.id}"
            session_path = os.path.join(SESSIONS_DIR, session_name)
            
            await client.storage.save()
            
            # Копируем .session файл
            temp_session_file = f"{auth_data['temp_path']}.session"
            dest_session_file = f"{session_path}.session"
            
            if os.path.exists(temp_session_file):
                shutil.copy2(temp_session_file, dest_session_file)
                logger.info(f"Сессия сохранена в {dest_session_file}")
            
            # Отправляем простое приветствие
            await self.send_test_message(client, session_name)
            
            await client.disconnect()
            
            # Удаляем временные файлы
            if os.path.exists(temp_session_file):
                os.remove(temp_session_file)
            
            # Сохраняем данные аккаунта
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'last_name': me.last_name or "",
                'bio': "",
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'phone_auth',
                'spam_checked': False
            }
            self.save_accounts_data()
            logger.info(f"Аккаунт {session_name} сохранен, всего аккаунтов: {len(self.accounts_data)}")
            
            # Очищаем временные данные
            if user_id in self.pending_authorizations:
                del self.pending_authorizations[user_id]
            
            username_text = f" (@{me.username})" if me.username else ""
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен"
            
        except Exception as e:
            logger.error(f"Ошибка при завершении авторизации: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def add_account(self, session_name: str, behavior_randomizer: BehaviorRandomizer) -> bool:
        """Добавляет аккаунт в менеджер для использования"""
        if session_name in self.accounts:
            return True
        
        try:
            session_path = os.path.join(SESSIONS_DIR, session_name)
            session_file = f"{session_path}.session"
            
            # Проверяем, существует ли файл сессии
            if not os.path.exists(session_file):
                logger.error(f"Файл сессии {session_file} не найден")
                return False
            
            logger.info(f"Загрузка аккаунта {session_name} из файла {session_file}")
            
            client = Client(session_path, api_id=API_ID, api_hash=API_HASH)
            await client.connect()
            
            me = await client.get_me()
            if not me:
                await client.disconnect()
                return False
            
            logger.info(f"Аккаунт {session_name} загружен: {me.first_name}")
            
            # Присваиваем характер, если его нет
            if session_name not in self.account_personalities:
                self.account_personalities[session_name] = behavior_randomizer.get_random_personality()
                logger.info(f"Аккаунту {session_name} присвоен характер: {self.account_personalities[session_name]['name']}")
            
            self.accounts[session_name] = client
            
            # Обновляем данные, если их нет
            if session_name not in self.accounts_data:
                self.accounts_data[session_name] = {
                    'phone': me.phone_number if me.phone_number else 'unknown',
                    'first_name': me.first_name,
                    'last_name': me.last_name or "",
                    'bio': "",
                    'username': me.username,
                    'added_date': datetime.now().isoformat(),
                    'is_active': True
                }
                self.save_accounts_data()
                logger.info(f"Данные аккаунта {session_name} сохранены")
            else:
                # Обновляем информацию
                self.accounts_data[session_name]['first_name'] = me.first_name
                self.accounts_data[session_name]['username'] = me.username
                self.save_accounts_data()
                logger.info(f"Данные аккаунта {session_name} обновлены")
            
            logger.info(f"Аккаунт {session_name} ({self.account_personalities[session_name]['name']}) успешно добавлен в менеджер")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении аккаунта {session_name}: {e}")
            return False
    
    async def remove_account(self, session_name: str):
        """Удаляет аккаунт"""
        if session_name in self.accounts:
            client = self.accounts[session_name]
            await client.disconnect()
            del self.accounts[session_name]
        
        if session_name in self.account_personalities:
            del self.account_personalities[session_name]
        
        if session_name in self.account_spam_status:
            del self.account_spam_status[session_name]
        
        session_path = os.path.join(SESSIONS_DIR, f"{session_name}.session")
        if os.path.exists(session_path):
            os.remove(session_path)
        
        if session_name in self.accounts_data:
            del self.accounts_data[session_name]
            self.save_accounts_data()
            logger.info(f"Аккаунт {session_name} удален")
    
    def get_active_accounts(self) -> List[str]:
        """Возвращает список активных аккаунтов"""
        return [name for name, data in self.accounts_data.items() if data.get('is_active', True)]
    
    def get_account_display_name(self, session_name: str) -> str:
        """Возвращает отображаемое имя аккаунта"""
        if session_name in self.accounts_data:
            data = self.accounts_data[session_name]
            username = f"@{data.get('username', 'no_username')}" if data.get('username') else 'без username'
            personality = self.account_personalities.get(session_name, {}).get('name', '')
            spam_status = self.account_spam_status.get(session_name, {}).get('status', '')
            
            personality_text = f" [{personality}]" if personality else ""
            
            # Разные иконки для статуса спам-блока
            if spam_status == 'clean':
                spam_icon = " ✅"
            elif spam_status == 'restricted':
                spam_icon = " ⚠️"
            elif spam_status == 'error':
                spam_icon = " ❌"
            else:
                spam_icon = " ❓"
            
            # Иконка источника
            source = data.get('source', 'session_file')
            source_icon = {
                'session_file': '📁',
                'txt_file': '📄',
                'phone_auth': '📱',
                'string_session': '📄'
            }.get(source, '📁')
            
            return f"{source_icon} {data.get('first_name', session_name)} ({username}){personality_text}{spam_icon}"
        return session_name
    
    async def get_username_by_session(self, session_name: str) -> Optional[str]:
        """Получает username аккаунта"""
        if session_name in self.accounts:
            client = self.accounts[session_name]
            try:
                me = await client.get_me()
                return me.username or me.first_name
            except:
                if session_name in self.accounts_data:
                    return self.accounts_data[session_name].get('username') or self.accounts_data[session_name].get('first_name')
        elif session_name in self.accounts_data:
            return self.accounts_data[session_name].get('username') or self.accounts_data[session_name].get('first_name')
        return None
    
    def get_account_personality(self, session_name: str) -> Dict:
        """Возвращает характер аккаунта"""
        return self.account_personalities.get(session_name, {})

# Класс для прогрева аккаунтов
class WarmupManager:
    def __init__(self, account_manager: AccountManager, dialogue_manager: DialogueManager):
        self.account_manager = account_manager
        self.dialogue_manager = dialogue_manager
        self.warmup_tasks: Dict[str, asyncio.Task] = {}
    
    async def start_warmup(self, chat_id: int, selected_accounts: List[str]):
        warmup_id = f"{chat_id}_{datetime.now().timestamp()}"
        
        task = asyncio.create_task(
            self._warmup_process(chat_id, selected_accounts, warmup_id)
        )
        self.warmup_tasks[warmup_id] = task
        
        self.account_manager.active_warmups[warmup_id] = {
            'chat_id': chat_id,
            'accounts': selected_accounts,
            'start_time': datetime.now().isoformat(),
            'status': 'running',
            'message_count': 0,
            'dialogue_count': 0,
            'current_dialogue': 0,
            'reactions_count': 0,
            'photos_count': 0,
            'start_time_obj': datetime.now()
        }
        
        return warmup_id
    
    async def stop_warmup(self, warmup_id: str):
        if warmup_id in self.warmup_tasks:
            self.warmup_tasks[warmup_id].cancel()
            del self.warmup_tasks[warmup_id]
            
        if warmup_id in self.account_manager.active_warmups:
            self.account_manager.active_warmups[warmup_id]['status'] = 'stopped'
    
    async def stop_all_warmups_for_chat(self, chat_id: int):
        to_stop = []
        for warmup_id, data in self.account_manager.active_warmups.items():
            if data.get('chat_id') == chat_id and data.get('status') == 'running':
                to_stop.append(warmup_id)
        
        for warmup_id in to_stop:
            await self.stop_warmup(warmup_id)
    
    async def _warmup_process(self, chat_id: int, accounts: List[str], warmup_id: str):
        try:
            for account in accounts:
                await self.account_manager.add_account(account, self.dialogue_manager.behavior_randomizer)
            
            await asyncio.sleep(5)
            
            dialogue_count = 0
            total_messages = 0
            message_index = 0
            
            personality_a = self.account_manager.get_account_personality(accounts[0])
            personality_b = self.account_manager.get_account_personality(accounts[1])
            
            while warmup_id in self.warmup_tasks:
                dialogue = self.dialogue_manager.get_random_dialogue()
                dialogue_count += 1
                
                logger.info(f"[{warmup_id}] Начинаем диалог #{dialogue_count}")
                
                for msg_index, msg_data in enumerate(dialogue):
                    if warmup_id not in self.warmup_tasks:
                        break
                    
                    if msg_data["from"] == "A":
                        sender = accounts[0]
                        receiver = accounts[1]
                        sender_personality = personality_a
                    else:
                        sender = accounts[1]
                        receiver = accounts[0]
                        sender_personality = personality_b
                    
                    sender_client = self.account_manager.accounts.get(sender)
                    if not sender_client:
                        continue
                    
                    receiver_username = await self.account_manager.get_username_by_session(receiver)
                    if not receiver_username:
                        continue
                    
                    try:
                        message_index += 1
                        
                        typing_delay = self.dialogue_manager.behavior_randomizer.get_typing_delay(sender_personality)
                        async with sender_client.action(receiver_username, "typing"):
                            await asyncio.sleep(typing_delay)
                        
                        await sender_client.send_message(receiver_username, msg_data["text"])
                        
                        total_messages += 1
                        self.account_manager.active_warmups[warmup_id]['message_count'] = total_messages
                        self.account_manager.active_warmups[warmup_id]['current_dialogue'] = dialogue_count
                        
                        logger.info(f"[{warmup_id}] Диалог #{dialogue_count}, сообщение #{msg_index+1}")
                        
                        if self.dialogue_manager.photo_manager.should_send_photo(message_index):
                            photo_path = self.dialogue_manager.photo_manager.get_random_photo()
                            if photo_path:
                                await asyncio.sleep(random.uniform(2, 5))
                                await sender_client.send_photo(receiver_username, photo_path)
                                self.account_manager.active_warmups[warmup_id]['photos_count'] += 1
                        
                        if self.dialogue_manager.behavior_randomizer.should_react(sender_personality, message_index):
                            await asyncio.sleep(random.uniform(1, 3))
                            try:
                                async for history_message in sender_client.get_chat_history(receiver_username, limit=5):
                                    if history_message.from_user and history_message.from_user.username == receiver_username.replace('@', ''):
                                        reaction = self.dialogue_manager.behavior_randomizer.get_random_reaction()
                                        await history_message.react(reaction)
                                        self.account_manager.active_warmups[warmup_id]['reactions_count'] += 1
                                        break
                            except:
                                pass
                        
                        response_delay = self.dialogue_manager.behavior_randomizer.get_response_delay(sender_personality)
                        await asyncio.sleep(response_delay)
                        
                    except FloodWait as e:
                        logger.warning(f"Flood wait: {e.value} секунд")
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        logger.error(f"Ошибка: {e}")
                        continue
                
                if warmup_id in self.warmup_tasks:
                    pause = random.uniform(300, 600)
                    minutes = pause / 60
                    
                    logger.info(f"[{warmup_id}] Пауза {minutes:.1f} минут")
                    await asyncio.sleep(pause)
            
        except asyncio.CancelledError:
            logger.info(f"Прогрев {warmup_id} остановлен")
        except Exception as e:
            logger.error(f"Ошибка прогресса: {e}")
            if warmup_id in self.account_manager.active_warmups:
                self.account_manager.active_warmups[warmup_id]['status'] = 'error'

# Инициализация
app = Client(
    "warmup_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Создаем менеджеры
account_manager = AccountManager()
dialogue_manager = DialogueManager()
warmup_manager = WarmupManager(account_manager, dialogue_manager)
chat_manager = ChatManager()
mailing_manager = MailingManager(account_manager)
channel_manager = ChannelManager()

# Данные пользователей
user_data = {}
mailing_data = {}

# Главное меню
def get_main_menu():
    buttons = [
        [InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts")],
        [InlineKeyboardButton("➕ Добавить аккаунт", callback_data="menu_add")],
        [InlineKeyboardButton("🔍 Проверить спам-блок", callback_data="menu_spamcheck")],
        [InlineKeyboardButton("🚀 Запустить прогрев", callback_data="menu_warmup")],
        [InlineKeyboardButton("📨 Рассылка", callback_data="menu_mailing")],
        [InlineKeyboardButton("📢 Создать каналы", callback_data="menu_channels")],
        [InlineKeyboardButton("📊 Статус", callback_data="menu_status")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
    ]
    return InlineKeyboardMarkup(buttons)

# Команда старт
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    # Подсчет пользователей
    users = set()
    for account_data in account_manager.accounts_data.values():
        if account_data.get('phone'):
            users.add(account_data.get('phone'))
    
    photos_count = len(dialogue_manager.photo_manager.photos)
    photos_warning = f"\n⚠️ В папке photos {photos_count} фото. Добавьте фото!" if photos_count == 0 else f"\n📸 В папке photos {photos_count} фото"
    
    await message.reply_text(
        f"👋 **Добро пожаловать в бота для прогрева Telegram аккаунтов!**\n\n"
        f"👥 **Всего пользователей:** {len(users)}\n"
        f"📱 **Аккаунтов:** {len(account_manager.get_available_sessions())}\n"
        f"{photos_warning}\n\n"
        f"✨ **Новые функции:**\n"
        f"• Проверка спам-блока (@spambot) с подробным отчетом\n"
        f"• Поддержка .txt файлов со строкой сессии\n"
        f"• Рассылка по чатам (до 20 чатов)\n"
        f"• Создание каналов (1-50)\n"
        f"• Загрузка чатов аккаунта\n"
        f"• Изменение имени и описания\n\n"
        f"Выберите действие:",
        reply_markup=get_main_menu()
    )

# Обработка callback
@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    message = callback_query.message
    
    if data == "main_menu":
        await message.edit_text(
            "👋 **Главное меню**\n\nВыберите действие:",
            reply_markup=get_main_menu()
        )
        await callback_query.answer()
    
    elif data == "menu_help":
        # Подсчет пользователей
        users = set()
        for account_data in account_manager.accounts_data.values():
            if account_data.get('phone'):
                users.add(account_data.get('phone'))
        
        text = (
            f"❓ **Помощь**\n\n"
            f"👥 **Всего пользователей:** {len(users)}\n\n"
            f"🔹 **Добавление аккаунтов:**\n"
            f"• Отправьте .session файл боту\n"
            f"• Отправьте .txt файл со строкой сессии\n"
            f"• Или нажмите 'Добавить по номеру'\n\n"
            f"🔹 **Проверка спам-блока:**\n"
            f"• Отдельная функция для проверки\n"
            f"• Подробный отчет о статусе\n"
            f"• Сохраняется в информации об аккаунте\n\n"
            f"🔹 **Управление аккаунтом:**\n"
            f"• Изменить имя - в меню аккаунта\n"
            f"• Изменить описание - там же\n"
            f"• Загрузить чаты для рассылки\n\n"
            f"🔹 **Создание каналов:**\n"
            f"• От 1 до 50 каналов за раз\n"
            f"• Автоматическая нумерация\n"
            f"• Пауза между созданиями\n\n"
            f"🔹 **Рассылка:**\n"
            f"1. Загрузите чаты аккаунта\n"
            f"2. Выберите до 20 чатов\n"
            f"3. Введите сообщение\n"
            f"4. Укажите количество и задержку\n\n"
            f"🔹 **Прогрев:**\n"
            f"• Диалоги 120 сообщений\n"
            f"• Реакции раз в 10-20 сообщ\n"
            f"• Фото раз в 30-50 сообщ\n"
            f"• 5 характеров аккаунтов\n"
            f"• Пауза 5-10 мин между диалогами"
        )
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
            ]])
        )
        await callback_query.answer()
    
    elif data == "menu_spamcheck":
        available = account_manager.get_available_sessions()
        
        if not available:
            await callback_query.answer(
                "❌ У вас нет аккаунтов для проверки!",
                show_alert=True
            )
            return
        
        buttons = []
        for session in available:
            display_name = account_manager.get_account_display_name(session)
            buttons.append([InlineKeyboardButton(
                f"🔍 {display_name}", 
                callback_data=f"spamcheck_{session}"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await message.edit_text(
            "🔍 **Проверка спам-блока**\n\n"
            "Выберите аккаунт для проверки:\n"
            "Бот @spambot проверит статус аккаунта",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data.startswith("spamcheck_"):
        session = data.replace("spamcheck_", "")
        
        await message.edit_text(
            f"⏳ **Проверяю аккаунт**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(session)}\n"
            f"Отправляю запрос к @spambot...\n\n"
            f"Пожалуйста, подождите...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="menu_spamcheck")
            ]])
        )
        
        # Добавляем аккаунт если нужно
        if session not in account_manager.accounts:
            await account_manager.add_account(session, dialogue_manager.behavior_randomizer)
        
        client = account_manager.accounts.get(session)
        if not client:
            await message.edit_text(
                "❌ **Ошибка**\n\nНе удалось активировать аккаунт.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_spamcheck")
                ]])
            )
            await callback_query.answer()
            return
        
        # Проверяем спам-блок
        success, result = await account_manager.check_spam_status(session, client)
        
        # Обновляем отображение
        await message.edit_text(
            f"**Результат проверки аккаунта**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(session)}\n\n"
            f"{result}\n\n"
            f"Статус сохранен в информации об аккаунте.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить другой", callback_data="menu_spamcheck")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback_query.answer()
    
    elif data == "menu_add":
        buttons = [
            [InlineKeyboardButton("📁 Загрузить .session файл", callback_data="add_session")],
            [InlineKeyboardButton("📄 Загрузить .txt файл", callback_data="add_txt")],
            [InlineKeyboardButton("📱 Добавить по номеру", callback_data="add_phone")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        await message.edit_text(
            "📥 **Добавление аккаунта**\n\n"
            "Выберите способ:\n"
            "• .session - файл сессии Pyrogram\n"
            "• .txt - файл со строкой сессии\n"
            "• По номеру - вход через SMS\n\n"
            "После добавления аккаунт отправит простое приветствие",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data == "add_phone":
        if chat_id in account_manager.pending_authorizations:
            auth_data = account_manager.pending_authorizations[chat_id]
            created = datetime.fromisoformat(auth_data['created_at'])
            if datetime.now() - created > timedelta(minutes=5):
                del account_manager.pending_authorizations[chat_id]
            else:
                await callback_query.answer("Уже есть активная авторизация! Подождите или отправьте /cancel", show_alert=True)
                return
        
        await message.edit_text(
            "📱 **Введите номер телефона** в международном формате:\n"
            "Например: `+79001234567`\n\n"
            "Я отправлю код подтверждения на этот номер.\n"
            "Отправьте номер в чат (или /cancel для отмены):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
            ]])
        )
        
        user_data[chat_id] = {'state': 'waiting_phone'}
        await callback_query.answer()
    
    elif data == "add_session":
        await message.edit_text(
            "📁 **Загрузка .session файла**\n\n"
            "Просто отправьте .session файл в этот чат.\n\n"
            "После загрузки аккаунт автоматически:\n"
            "• Установит случайный username (если нет)\n"
            "• Отправит простое приветствие администратору",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="menu_add")
            ]])
        )
        await callback_query.answer()
    
    elif data == "add_txt":
        await message.edit_text(
            "📄 **Загрузка .txt файла со строкой сессии**\n\n"
            "Файл должен содержать только строку сессии (одна строка).\n\n"
            "Поддерживаются все кодировки (автоопределение).\n\n"
            "Отправьте .txt файл в этот чат:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="menu_add")
            ]])
        )
        await callback_query.answer()
    
    elif data == "menu_accounts":
        available = account_manager.get_available_sessions()
        
        if not available:
            text = "📱 **Мои аккаунты**\n\nУ вас пока нет добавленных аккаунтов."
            buttons = [[InlineKeyboardButton("➕ Добавить аккаунт", callback_data="menu_add")]]
        else:
            text = "📱 **Мои аккаунты**\n\n"
            for session in available:
                display_name = account_manager.get_account_display_name(session)
                text += f"{display_name}\n"
            
            buttons = [
                [InlineKeyboardButton("✏️ Изменить профиль", callback_data="menu_edit_profile")],
                [InlineKeyboardButton("🗑 Удалить аккаунт", callback_data="menu_remove")],
                [InlineKeyboardButton("🔍 Проверить спам", callback_data="menu_spamcheck")]
            ]
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer()
    
    elif data == "menu_edit_profile":
        available = account_manager.get_available_sessions()
        
        if not available:
            await callback_query.answer("Нет аккаунтов для редактирования!", show_alert=True)
            return
        
        buttons = []
        for session in available:
            display_name = account_manager.get_account_display_name(session)
            buttons.append([InlineKeyboardButton(
                f"✏️ {display_name}", 
                callback_data=f"edit_profile_{session}"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")])
        
        await message.edit_text(
            "✏️ **Выберите аккаунт для редактирования:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data.startswith("edit_profile_"):
        session = data.replace("edit_profile_", "")
        
        buttons = [
            [InlineKeyboardButton("📝 Изменить имя", callback_data=f"edit_name_{session}")],
            [InlineKeyboardButton("📄 Изменить описание", callback_data=f"edit_bio_{session}")],
            [InlineKeyboardButton("🔄 Назад", callback_data="menu_edit_profile")]
        ]
        
        await message.edit_text(
            f"✏️ **Редактирование профиля**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(session)}\n\n"
            f"Выберите что изменить:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data.startswith("edit_name_"):
        session = data.replace("edit_name_", "")
        
        user_data[chat_id] = {
            'state': 'editing_name',
            'session': session
        }
        
        await message.edit_text(
            f"📝 **Введите новое имя для аккаунта**\n\n"
            f"Текущее имя: {account_manager.accounts_data[session].get('first_name', 'Неизвестно')}\n\n"
            f"Отправьте новое имя в чат (или /cancel для отмены):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_edit_profile")
            ]])
        )
        await callback_query.answer()
    
    elif data.startswith("edit_bio_"):
        session = data.replace("edit_bio_", "")
        
        user_data[chat_id] = {
            'state': 'editing_bio',
            'session': session
        }
        
        current_bio = account_manager.accounts_data[session].get('bio', '')
        if not current_bio:
            current_bio = "не установлено"
        
        await message.edit_text(
            f"📄 **Введите новое описание для аккаунта**\n\n"
            f"Текущее описание: {current_bio}\n\n"
            f"Отправьте новое описание в чат (или /cancel для отмены):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_edit_profile")
            ]])
        )
        await callback_query.answer()
    
    elif data == "menu_remove":
        available = account_manager.get_available_sessions()
        
        if not available:
            await callback_query.answer("Нет аккаунтов для удаления!", show_alert=True)
            return
        
        buttons = []
        for session in available:
            display_name = account_manager.get_account_display_name(session)
            buttons.append([InlineKeyboardButton(
                f"❌ {display_name}", 
                callback_data=f"remove_{session}"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")])
        
        await message.edit_text(
            "🗑 **Выберите аккаунт для удаления:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data.startswith("remove_"):
        session = data.replace("remove_", "")
        await account_manager.remove_account(session)
        await callback_query.answer("✅ Аккаунт удален")
        
        available = account_manager.get_available_sessions()
        if available:
            text = "📱 **Мои аккаунты**\n\n"
            for s in available:
                display_name = account_manager.get_account_display_name(s)
                text += f"{display_name}\n"
            
            buttons = [
                [InlineKeyboardButton("✏️ Изменить профиль", callback_data="menu_edit_profile")],
                [InlineKeyboardButton("🗑 Удалить аккаунт", callback_data="menu_remove")],
                [InlineKeyboardButton("🔍 Проверить спам", callback_data="menu_spamcheck")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]
        else:
            text = "📱 **Мои аккаунты**\n\nУ вас пока нет добавленных аккаунтов."
            buttons = [
                [InlineKeyboardButton("➕ Добавить аккаунт", callback_data="menu_add")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "menu_mailing":
        available = account_manager.get_available_sessions()
        
        if not available:
            await callback_query.answer(
                "❌ У вас нет аккаунтов для рассылки!",
                show_alert=True
            )
            return
        
        buttons = []
        for session in available:
            display_name = account_manager.get_account_display_name(session)
            buttons.append([InlineKeyboardButton(
                f"📨 {display_name}", 
                callback_data=f"mailing_account_{session}"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await message.edit_text(
            "📨 **Рассылка сообщений**\n\n"
            "Выберите аккаунт для рассылки:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data.startswith("mailing_account_"):
        session = data.replace("mailing_account_", "")
        
        buttons = [
            [InlineKeyboardButton("📥 Загрузить чаты", callback_data=f"load_chats_{session}")],
            [InlineKeyboardButton("📤 Выбрать чаты", callback_data=f"select_chats_{session}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_mailing")]
        ]
        
        await message.edit_text(
            f"📨 **Рассылка с аккаунта**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(session)}\n\n"
            f"1. Сначала загрузите чаты\n"
            f"2. Затем выберите до 20 чатов\n"
            f"3. Настройте параметры рассылки",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        mailing_data[chat_id] = {'account': session}
        await callback_query.answer()
    
    elif data.startswith("load_chats_"):
        session = data.replace("load_chats_", "")
        
        await message.edit_text(
            f"⏳ **Загружаю чаты аккаунта**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(session)}\n"
            f"Пожалуйста, подождите...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="menu_mailing")
            ]])
        )
        
        # Добавляем аккаунт в менеджер если его нет
        if session not in account_manager.accounts:
            success = await account_manager.add_account(session, dialogue_manager.behavior_randomizer)
            if not success:
                await message.edit_text(
                    "❌ **Ошибка**\n\nНе удалось активировать аккаунт. Возможно, файл сессии поврежден.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад", callback_data="menu_mailing")
                    ]])
                )
                await callback_query.answer()
                return
        
        client = account_manager.accounts.get(session)
        if not client:
            await message.edit_text(
                "❌ **Ошибка**\n\nАккаунт не активирован.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_mailing")
                ]])
            )
            await callback_query.answer()
            return
        
        chats = await chat_manager.load_user_chats(client, chat_id, session)
        
        if not chats:
            await message.edit_text(
                "❌ **Ошибка**\n\nНе удалось загрузить чаты.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_mailing")
                ]])
            )
            await callback_query.answer()
            return
        
        await message.edit_text(
            f"✅ **Чаты загружены!**\n\n"
            f"Всего чатов: {len(chats)}\n"
            f"Теперь выберите чаты для рассылки.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Выбрать чаты", callback_data=f"select_chats_{session}_0")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_mailing")]
            ])
        )
        await callback_query.answer()
    
    elif data.startswith("select_chats_"):
        parts = data.split("_")
        if len(parts) == 4:
            session = parts[2]
            page = int(parts[3])
        else:
            session = parts[2]
            page = 0
        
        chats, total_pages = chat_manager.get_chats_page(chat_id, session, page)
        selected = chat_manager.get_selected_chats(chat_id)
        
        if not chats:
            await callback_query.answer("Сначала загрузите чаты!", show_alert=True)
            return
        
        text = f"📤 **Выбор чатов для рассылки**\n\n"
        text += f"Аккаунт: {account_manager.get_account_display_name(session)}\n"
        text += f"Выбрано: {len(selected)}/20 чатов\n"
        text += f"Страница {page + 1}/{total_pages}\n\n"
        
        buttons = []
        for chat in chats:
            chat_id_str = str(chat['id'])
            status = "✅" if chat['id'] in selected else "⬜"
            title = chat['title'][:30] + "..." if len(chat['title']) > 30 else chat['title']
            buttons.append([InlineKeyboardButton(
                f"{status} {title} ({chat['type']})",
                callback_data=f"toggle_chat_{chat['id']}"
            )])
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"select_chats_{session}_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"select_chats_{session}_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        if len(selected) >= 2:
            buttons.append([InlineKeyboardButton("✅ Начать рассылку", callback_data="start_mailing_config")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"mailing_account_{session}")])
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer()
    
    elif data.startswith("toggle_chat_"):
        chat_id_selected = int(data.replace("toggle_chat_", ""))
        
        selected = chat_manager.get_selected_chats(chat_id)
        
        if chat_id_selected in selected:
            chat_manager.unselect_chat(chat_id, chat_id_selected)
            await callback_query.answer("Чат убран")
        else:
            if len(selected) >= 20:
                await callback_query.answer("Максимум 20 чатов!", show_alert=True)
                return
            chat_manager.select_chat(chat_id, chat_id_selected)
            await callback_query.answer("Чат добавлен")
        
        parts = message.text.split("\n")
        for i, line in enumerate(parts):
            if "Выбрано:" in line:
                parts[i] = f"Выбрано: {len(chat_manager.get_selected_chats(chat_id))}/20 чатов"
                break
        
        await message.edit_text(
            "\n".join(parts),
            reply_markup=message.reply_markup
        )
    
    elif data == "start_mailing_config":
        selected = chat_manager.get_selected_chats(chat_id)
        
        if len(selected) < 2:
            await callback_query.answer("Выберите минимум 2 чата!", show_alert=True)
            return
        
        account = mailing_data.get(chat_id, {}).get('account', '')
        
        user_data[chat_id] = {
            'state': 'mailing_message',
            'account': account,
            'chats': selected
        }
        
        await message.edit_text(
            "📝 **Настройка рассылки**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(account)}\n"
            f"Выбрано чатов: {len(selected)}\n\n"
            "**Шаг 1/3:** Введите текст сообщения для рассылки\n\n"
            "Отправьте сообщение в чат (или /cancel для отмены):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_mailing")
            ]])
        )
        await callback_query.answer()
    
    elif data == "menu_channels":
        available = account_manager.get_available_sessions()
        
        if not available:
            await callback_query.answer(
                "❌ У вас нет аккаунтов для создания каналов!",
                show_alert=True
            )
            return
        
        buttons = []
        for session in available:
            display_name = account_manager.get_account_display_name(session)
            buttons.append([InlineKeyboardButton(
                f"📢 {display_name}", 
                callback_data=f"channels_account_{session}"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await message.edit_text(
            "📢 **Создание каналов**\n\n"
            "Выберите аккаунт для создания каналов:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    elif data.startswith("channels_account_"):
        session = data.replace("channels_account_", "")
        
        user_data[chat_id] = {
            'state': 'channels_count',
            'account': session
        }
        
        await message.edit_text(
            "📢 **Создание каналов**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(session)}\n\n"
            "Введите количество каналов для создания (от 1 до 50):\n"
            "Или /cancel для отмены:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_channels")
            ]])
        )
        await callback_query.answer()
    
    elif data == "menu_status":
        active_warmups = []
        for warmup_id, data in account_manager.active_warmups.items():
            if data.get('chat_id') == chat_id:
                active_warmups.append(data)
        
        active_mailings = []
        for task_id, data in mailing_manager.mailing_stats.items():
            if data.get('user_id') == chat_id:
                active_mailings.append(data)
        
        active_channels = []
        for task_id, task in channel_manager.creation_tasks.items():
            if task_id.startswith(str(chat_id)):
                active_channels.append(task_id)
        
        if not active_warmups and not active_mailings and not active_channels:
            await callback_query.answer("📊 Нет активных процессов", show_alert=True)
            return
        
        text = "📊 **Активные процессы**\n\n"
        
        if active_warmups:
            data = active_warmups[0]
            accounts_text = "\n".join([f"• {account_manager.get_account_display_name(a)}" for a in data['accounts']])
            elapsed = datetime.now() - data.get('start_time_obj', datetime.now())
            hours = elapsed.seconds // 3600
            minutes = (elapsed.seconds % 3600) // 60
            
            text += f"**🚀 Прогрев:**\n"
            text += f"{accounts_text}\n"
            text += f"Время: {hours}ч {minutes}м\n"
            text += f"Сообщений: {data.get('message_count', 0)}\n"
            text += f"Реакций: {data.get('reactions_count', 0)}\n"
            text += f"Фото: {data.get('photos_count', 0)}\n"
            text += f"Диалогов: {data.get('dialogue_count', 0)}\n\n"
        
        if active_mailings:
            for data in active_mailings:
                text += f"**📨 Рассылка ({data['account_name']}):**\n"
                text += f"Отправлено: {data['sent']}/{data['total_messages']}\n"
                text += f"Ошибок: {data['failed']}\n"
                text += f"Статус: {data['status']}\n\n"
        
        if active_channels:
            text += f"**📢 Создание каналов:**\n"
            text += f"Активных процессов: {len(active_channels)}\n\n"
        
        buttons = []
        if active_warmups:
            buttons.append([InlineKeyboardButton("🛑 Остановить прогрев", callback_data="stop_warmup")])
        if active_mailings:
            for task_id, data in mailing_manager.mailing_stats.items():
                if data.get('user_id') == chat_id and data.get('status') == 'running':
                    buttons.append([InlineKeyboardButton(f"🛑 Остановить рассылку", callback_data=f"stop_mailing_{task_id}")])
        if active_channels:
            for task_id in active_channels:
                buttons.append([InlineKeyboardButton(f"🛑 Остановить создание каналов", callback_data=f"stop_channels_{task_id}")])
        
        buttons.append([InlineKeyboardButton("🔄 Обновить", callback_data="menu_status")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer()
    
    elif data.startswith("stop_mailing_"):
        task_id = data.replace("stop_mailing_", "")
        await mailing_manager.stop_mailing(task_id)
        await callback_query.answer("✅ Рассылка остановлена")
        
        await handle_callback(client, CallbackQuery(
            message=message,
            data="menu_status",
            chat_instance=callback_query.chat_instance,
            from_user=callback_query.from_user
        ))
    
    elif data.startswith("stop_channels_"):
        task_id = data.replace("stop_channels_", "")
        channel_manager.stop_creation(task_id)
        await callback_query.answer("✅ Создание каналов остановлено")
        
        await handle_callback(client, CallbackQuery(
            message=message,
            data="menu_status",
            chat_instance=callback_query.chat_instance,
            from_user=callback_query.from_user
        ))
    
    elif data == "stop_warmup":
        await warmup_manager.stop_all_warmups_for_chat(chat_id)
        await callback_query.answer("✅ Прогрев остановлен")
        
        await message.edit_text(
            "🛑 **Прогрев остановлен**\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu()
        )
    
    elif data == "menu_warmup":
        available = account_manager.get_available_sessions()
        
        if len(available) < 2:
            await callback_query.answer(
                f"❌ Для прогрева нужно минимум 2 аккаунта!\nСейчас: {len(available)}",
                show_alert=True
            )
            return
        
        added_accounts = []
        for session in available:
            if await account_manager.add_account(session, dialogue_manager.behavior_randomizer):
                added_accounts.append(session)
        
        if len(added_accounts) < 2:
            await callback_query.answer(
                "❌ Не удалось активировать аккаунты!",
                show_alert=True
            )
            return
        
        buttons = []
        for session in added_accounts:
            display_name = account_manager.get_account_display_name(session)
            buttons.append([InlineKeyboardButton(
                f"⬜ {display_name}", 
                callback_data=f"select_{session}"
            )])
        
        buttons.append([
            InlineKeyboardButton("✅ Начать прогрев", callback_data="start_warmup"),
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        ])
        
        await message.edit_text(
            "📝 **Выберите аккаунты для прогрева (минимум 2):**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        user_data[chat_id] = {'selected_accounts': []}
        await callback_query.answer()
    
    elif data.startswith("select_"):
        session = data.replace("select_", "")
        
        if chat_id not in user_data:
            user_data[chat_id] = {'selected_accounts': []}
        
        selected = user_data[chat_id]['selected_accounts']
        
        if session in selected:
            selected.remove(session)
            await callback_query.answer(f"❌ Аккаунт убран")
        else:
            if len(selected) >= 2:
                await callback_query.answer("Максимум 2 аккаунта для прогрева!", show_alert=True)
                return
            selected.append(session)
            await callback_query.answer(f"✅ Аккаунт добавлен")
        
        available = account_manager.get_available_sessions()
        buttons = []
        for s in available:
            display_name = account_manager.get_account_display_name(s)
            status = "✅" if s in selected else "⬜"
            buttons.append([InlineKeyboardButton(
                f"{status} {display_name}", 
                callback_data=f"select_{s}"
            )])
        
        buttons.append([
            InlineKeyboardButton("✅ Начать прогрев", callback_data="start_warmup"),
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        ])
        
        await message.edit_reply_markup(InlineKeyboardMarkup(buttons))
    
    elif data == "start_warmup":
        if chat_id not in user_data or len(user_data[chat_id]['selected_accounts']) != 2:
            await callback_query.answer("❌ Выберите ровно 2 аккаунта!", show_alert=True)
            return
        
        selected = user_data[chat_id]['selected_accounts']
        warmup_id = await warmup_manager.start_warmup(chat_id, selected)
        
        await message.edit_text(
            f"🚀 **Прогрев запущен!**\n\n"
            f"**Аккаунты:** {len(selected)}\n"
            f"**Параметры:**\n"
            f"• Диалоги: 120 сообщений\n"
            f"• Реакции: раз в 10-20 сообщ\n"
            f"• Фото: раз в 30-50 сообщ\n"
            f"• Пауза: 5-10 мин между диалогами\n\n"
            f"Используйте /status для просмотра",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Статус", callback_data="menu_status"),
                 InlineKeyboardButton("🛑 Остановить", callback_data="stop_warmup")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        
        await callback_query.answer("✅ Прогрев запущен!")

# Обработка документов
@app.on_message(filters.document)
async def handle_document(client: Client, message: Message):
    file_name = message.document.file_name
    
    if not (file_name.endswith('.session') or file_name.endswith('.txt')):
        await message.reply_text(
            "❌ Пожалуйста, отправьте файл с расширением .session или .txt",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
        return
    
    status_msg = await message.reply_text("⏳ Загружаю файл...")
    
    file_path = await message.download(file_name=TEMP_DIR)
    success, result_text = await account_manager.add_account_by_session_file(
        file_path, 
        file_name
    )
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    await status_msg.delete()
    
    if success:
        await message.reply_text(
            f"✅ {result_text}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts"),
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
    else:
        await message.reply_text(
            f"❌ {result_text}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )

# Обработка текста
@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_text(client: Client, message: Message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Отмена
    if text.lower() == "/cancel":
        if chat_id in account_manager.pending_authorizations:
            auth_data = account_manager.pending_authorizations[chat_id]
            if 'client' in auth_data:
                try:
                    await auth_data['client'].disconnect()
                except:
                    pass
            del account_manager.pending_authorizations[chat_id]
            logger.info(f"Авторизация отменена пользователем {chat_id}")
        
        if chat_id in user_data:
            del user_data[chat_id]
        
        if chat_id in mailing_data:
            del mailing_data[chat_id]
        
        chat_manager.clear_selected(chat_id)
        
        await message.reply_text(
            "✅ Операция отменена",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
        return
    
    # Редактирование имени
    if chat_id in user_data and user_data[chat_id].get('state') == 'editing_name':
        session = user_data[chat_id]['session']
        
        if session not in account_manager.accounts:
            success = await account_manager.add_account(session, dialogue_manager.behavior_randomizer)
            if not success:
                await message.reply_text(
                    "❌ Не удалось активировать аккаунт",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")
                    ]])
                )
                del user_data[chat_id]
                return
        
        client = account_manager.accounts.get(session)
        if not client:
            await message.reply_text(
                "❌ Аккаунт не активирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")
                ]])
            )
            del user_data[chat_id]
            return
        
        success = await account_manager.set_account_profile(client, first_name=text)
        
        if success:
            me = await client.get_me()
            account_manager.accounts_data[session]['first_name'] = me.first_name
            account_manager.save_accounts_data()
            
            await message.reply_text(
                f"✅ Имя успешно изменено на: {text}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts"),
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
        else:
            await message.reply_text(
                "❌ Ошибка при изменении имени",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")
                ]])
            )
        
        del user_data[chat_id]
        return
    
    # Редактирование описания
    if chat_id in user_data and user_data[chat_id].get('state') == 'editing_bio':
        session = user_data[chat_id]['session']
        
        if session not in account_manager.accounts:
            success = await account_manager.add_account(session, dialogue_manager.behavior_randomizer)
            if not success:
                await message.reply_text(
                    "❌ Не удалось активировать аккаунт",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")
                    ]])
                )
                del user_data[chat_id]
                return
        
        client = account_manager.accounts.get(session)
        if not client:
            await message.reply_text(
                "❌ Аккаунт не активирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")
                ]])
            )
            del user_data[chat_id]
            return
        
        success = await account_manager.set_account_profile(client, bio=text)
        
        if success:
            account_manager.accounts_data[session]['bio'] = text
            account_manager.save_accounts_data()
            
            await message.reply_text(
                f"✅ Описание успешно изменено",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts"),
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
        else:
            await message.reply_text(
                "❌ Ошибка при изменении описания",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_accounts")
                ]])
            )
        
        del user_data[chat_id]
        return
    
    # Создание каналов - ввод количества
    if chat_id in user_data and user_data[chat_id].get('state') == 'channels_count':
        if not text.isdigit():
            await message.reply_text(
                "❌ Введите число от 1 до 50",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_channels")
                ]])
            )
            return
        
        count = int(text)
        if count < 1 or count > 50:
            await message.reply_text(
                "❌ Количество должно быть от 1 до 50",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_channels")
                ]])
            )
            return
        
        user_data[chat_id]['count'] = count
        user_data[chat_id]['state'] = 'channels_title'
        
        await message.reply_text(
            "📢 **Введите название для каналов**\n\n"
            f"Будет создано {count} каналов.\n"
            "Если каналов несколько, к названию добавится номер.\n\n"
            "Введите название (или /cancel для отмены):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_channels")
            ]])
        )
        return
    
    # Создание каналов - ввод названия
    if chat_id in user_data and user_data[chat_id].get('state') == 'channels_title':
        title = text
        count = user_data[chat_id]['count']
        account = user_data[chat_id]['account']
        
        user_data[chat_id]['title'] = title
        user_data[chat_id]['state'] = 'channels_description'
        
        await message.reply_text(
            "📢 **Введите описание для каналов** (или отправьте '-' чтобы пропустить)\n\n"
            "Описание будет одинаковым для всех каналов.\n"
            "Или /cancel для отмены:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_channels")
            ]])
        )
        return
    
    # Создание каналов - ввод описания
    if chat_id in user_data and user_data[chat_id].get('state') == 'channels_description':
        if text == '-':
            description = ""
        else:
            description = text
        
        account = user_data[chat_id]['account']
        count = user_data[chat_id]['count']
        title = user_data[chat_id]['title']
        
        # Добавляем аккаунт в менеджер если его нет
        if account not in account_manager.accounts:
            await account_manager.add_account(account, dialogue_manager.behavior_randomizer)
        
        await message.reply_text(
            f"⏳ **Запускаю создание {count} каналов...**\n\n"
            f"Аккаунт: {account_manager.get_account_display_name(account)}\n"
            f"Название: {title}\n"
            f"Описание: {description if description else 'без описания'}\n\n"
            f"Процесс может занять несколько минут.\n"
            f"Статус можно отслеживать в меню 📊 Статус",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Статус", callback_data="menu_status"),
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
        
        task_id = await channel_manager.create_multiple_channels(
            chat_id, account, count, title, description
        )
        
        del user_data[chat_id]
        return
    
    # Ввод сообщения для рассылки
    if chat_id in user_data and user_data[chat_id].get('state') == 'mailing_message':
        user_data[chat_id]['message'] = text
        user_data[chat_id]['state'] = 'mailing_count'
        
        await message.reply_text(
            "📝 **Шаг 2/3:** Введите количество сообщений в каждый чат\n\n"
            "(например: 5 - отправить 5 сообщений в каждый выбранный чат)\n"
            "Или /cancel для отмены:"
        )
        return
    
    # Ввод количества сообщений
    if chat_id in user_data and user_data[chat_id].get('state') == 'mailing_count':
        if not text.isdigit():
            await message.reply_text(
                "❌ Введите число (например: 5)",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_mailing")
                ]])
            )
            return
        
        count = int(text)
        if count < 1 or count > 100:
            await message.reply_text(
                "❌ Количество должно быть от 1 до 100",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_mailing")
                ]])
            )
            return
        
        user_data[chat_id]['count'] = count
        user_data[chat_id]['state'] = 'mailing_delay'
        
        await message.reply_text(
            "📝 **Шаг 3/3:** Введите задержку между сообщениями (в секундах)\n\n"
            "(например: 10 - пауза 10 секунд между сообщениями)\n"
            "Или /cancel для отмены:"
        )
        return
    
    # Ввод задержки
    if chat_id in user_data and user_data[chat_id].get('state') == 'mailing_delay':
        if not text.isdigit():
            await message.reply_text(
                "❌ Введите число (например: 10)",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_mailing")
                ]])
            )
            return
        
        delay = int(text)
        if delay < 1 or delay > 60:
            await message.reply_text(
                "❌ Задержка должна быть от 1 до 60 секунд",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_mailing")
                ]])
            )
            return
        
        account = user_data[chat_id]['account']
        chats = user_data[chat_id]['chats']
        message_text = user_data[chat_id]['message']
        count = user_data[chat_id]['count']
        
        # Добавляем аккаунт если нужно
        if account not in account_manager.accounts:
            await account_manager.add_account(account, dialogue_manager.behavior_randomizer)
        
        task_id = await mailing_manager.start_mailing(
            chat_id, account, chats, message_text, count, delay
        )
        
        await message.reply_text(
            f"✅ **Рассылка запущена!**\n\n"
            f"**Параметры:**\n"
            f"• Аккаунт: {account_manager.get_account_display_name(account)}\n"
            f"• Чатов: {len(chats)}\n"
            f"• Сообщений в чат: {count}\n"
            f"• Всего сообщений: {len(chats) * count}\n"
            f"• Задержка: {delay} сек\n\n"
            f"Используйте /status для отслеживания прогресса",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Статус", callback_data="menu_status"),
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
        
        del user_data[chat_id]
        return
    
    # Ввод номера телефона
    if chat_id in user_data and user_data[chat_id].get('state') == 'waiting_phone':
        if not text.startswith('+') or not text[1:].replace(' ', '').isdigit():
            await message.reply_text(
                "❌ Неверный формат. Введите номер в формате: +79001234567",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
                ]])
            )
            return
        
        phone = text.replace(' ', '')
        success, result = await account_manager.start_phone_authorization(chat_id, phone)
        
        if success:
            await message.reply_text(
                "✅ **Код подтверждения отправлен!**\n"
                "Введите код из SMS (или /cancel для отмены):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
                ]])
            )
            user_data[chat_id]['state'] = 'waiting_code'
        else:
            await message.reply_text(
                f"❌ {result}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                ]])
            )
            del user_data[chat_id]
        
        return
    
    # Ввод кода
    if chat_id in account_manager.pending_authorizations:
        auth_data = account_manager.pending_authorizations[chat_id]
        
        if auth_data.get('step') == 'waiting_code':
            if not text.isdigit():
                await message.reply_text(
                    "❌ Код должен содержать только цифры",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
                    ]])
                )
                return
            
            success, result = await account_manager.complete_phone_authorization(chat_id, code=text)
            
            if result == "password_needed":
                await message.reply_text(
                    "🔐 **Требуется двухфакторная аутентификация.**\n"
                    "Введите ваш пароль (или /cancel для отмены):",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
                    ]])
                )
                auth_data['step'] = 'waiting_password'
            elif success:
                await message.reply_text(
                    f"✅ {result}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts"),
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
                if chat_id in user_data:
                    del user_data[chat_id]
                if chat_id in account_manager.pending_authorizations:
                    del account_manager.pending_authorizations[chat_id]
            else:
                await message.reply_text(
                    f"❌ {result}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
                if chat_id in account_manager.pending_authorizations:
                    try:
                        await account_manager.pending_authorizations[chat_id]['client'].disconnect()
                    except:
                        pass
                    del account_manager.pending_authorizations[chat_id]
                if chat_id in user_data:
                    del user_data[chat_id]
        
        elif auth_data.get('step') == 'waiting_password':
            success, result = await account_manager.complete_phone_authorization(chat_id, password=text)
            
            if success:
                await message.reply_text(
                    f"✅ {result}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts"),
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
            else:
                await message.reply_text(
                    f"❌ {result}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
            
            if chat_id in account_manager.pending_authorizations:
                try:
                    await account_manager.pending_authorizations[chat_id]['client'].disconnect()
                except:
                    pass
                del account_manager.pending_authorizations[chat_id]
            if chat_id in user_data:
                del user_data[chat_id]

# Запуск
if __name__ == "__main__":
    # Проверяем наличие библиотеки chardet
    try:
        import chardet
    except ImportError:
        os.system("pip install chardet")
        import chardet
    
    print("🚀 Бот запущен...")
    print(f"API ID: {API_ID}")
    print(f"Папка sessions: {SESSIONS_DIR}")
    print(f"Папка temp: {TEMP_DIR}")
    print(f"Папка photos: {PHOTOS_DIR}")
    print(f"Администратор: @{ADMIN_USERNAME}")
    print(f"Проверка спам-блока: @{SPAM_BOT}")
    print("\n📱 Управление через кнопки в Telegram")
    print("Напишите /start для начала работы")
    print("\n✨ Исправленные проблемы:")
    print("• Аккаунты теперь правильно сохраняются в 'Мои аккаунты'")
    print("• Исправлена ошибка с ASCII символами в .txt файлах")
    print("• Добавлена поддержка base64 строк сессий")
    print("• Подробное логирование для отладки")
    app.run()

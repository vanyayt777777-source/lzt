# main.py
import os
import asyncio
import random
import json
import logging
import shutil
import string
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, SessionPasswordNeeded, UsernameInvalid
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
ADMIN_USERNAME = "v3estnikov"  # Администратор для тестового сообщения

# Создаем необходимые папки
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Класс для генерации случайных username
class UsernameGenerator:
    @staticmethod
    def generate_username() -> str:
        """Генерирует случайный username"""
        patterns = [
            lambda: ''.join(random.choices(string.ascii_lowercase, k=random.randint(8, 12))),
            lambda: ''.join(random.choices(string.ascii_lowercase, k=random.randint(6, 8)) + random.choices(string.digits, k=random.randint(2, 4))),
            lambda: random.choice(['cool_', 'awesome_', 'super_', 'mega_', 'ultra_']) + ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 6))),
            lambda: ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 7))) + random.choice(['123', '777', '999', '000']),
            lambda: random.choice(['mr_', 'ms_', 'dr_', 'prof_']) + ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 8))),
        ]
        
        pattern = random.choice(patterns)
        username = pattern()
        
        if username[0].isdigit():
            username = 'u' + username
        
        return username

# Класс для управления диалогами
class DialogueManager:
    def __init__(self):
        self.dialogues = self.load_dialogues()
    
    def load_dialogues(self) -> List[List[Dict]]:
        """Загружает длинные диалоги из файла"""
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем 20 диалогов по 120 сообщений каждый (60 реплик с каждой стороны)
            dialogues = []
            
            # Темы для диалогов
            topics = [
                "путешествия и страны",
                "работа и карьера", 
                "фильмы и сериалы",
                "музыка и концерты",
                "спорт и здоровье",
                "технологии и гаджеты",
                "еда и рестораны",
                "книги и литература",
                "образование и учеба",
                "отношения и дружба",
                "хобби и увлечения",
                "автомобили",
                "животные",
                "погода и природа",
                "психология и саморазвитие",
                "бизнес и стартапы",
                "искусство и творчество",
                "наука и открытия",
                "мода и стиль",
                "компьютерные игры"
            ]
            
            # Фразы для построения диалогов
            phrases = {
                "greetings": [
                    "Привет! Давно не общались!",
                    "Здорово! Как жизнь?",
                    "Хай! Рад тебя слышать!",
                    "Добрый вечер!",
                    "Приветствую!"
                ],
                "how_are_you": [
                    "Как твои дела?",
                    "Что нового?",
                    "Как настроение?",
                    "Чем занимаешься?",
                    "Как успехи?"
                ],
                "answers_good": [
                    "Отлично, спасибо!",
                    "Нормально, потихоньку",
                    "Хорошо, работаю",
                    "Все супер!",
                    "Лучше всех!"
                ],
                "questions": [
                    "А у тебя как?",
                    "А ты как?",
                    "А у тебя что нового?",
                    "А твои как дела?",
                    "А ты чем занят?"
                ],
                "agreements": [
                    "Согласен!",
                    "Да, точно!",
                    "И не говори!",
                    "Вот именно!",
                    "Абсолютно верно!"
                ],
                "surprises": [
                    "Да ладно?!",
                    "Серьезно?",
                    "Ничего себе!",
                    "Ого!",
                    "Не может быть!"
                ],
                "interests": [
                    "Это интересно!",
                    "Расскажи подробнее",
                    "А что именно?",
                    "И как тебе?",
                    "А давно этим занимаешься?"
                ],
                "opinions": [
                    "Я считаю, что это круто",
                    "Мне кажется, это перспективно",
                    "По-моему, это отличная идея",
                    "Я думаю, стоит попробовать",
                    "На мой взгляд, это важно"
                ],
                "experiences": [
                    "У меня тоже такой опыт был",
                    "Я как-то пробовал",
                    "В прошлом году тоже так делал",
                    "Мы с друзьями тоже так делали",
                    "Помню, было дело"
                ],
                "advice": [
                    "Попробуй, не пожалеешь",
                    "Советую обратить внимание",
                    "Лучше уточни заранее",
                    "Главное не торопись",
                    "Действуй по плану"
                ],
                "plans": [
                    "В планах съездить отдохнуть",
                    "Хочу научиться новому",
                    "Планирую сменить работу",
                    "Думаю над переездом",
                    "Хочу купить машину"
                ],
                "memories": [
                    "А помнишь, как мы...",
                    "Классное было время",
                    "Да, было здорово",
                    "Надо бы повторить",
                    "Вспомнил тот случай"
                ],
                "jokes": [
                    "Анекдот в тему...",
                    "Кстати, смешная история",
                    "Такая ситуация приключилась",
                    "Представляешь, а я...",
                    "Засмеялся просто"
                ],
                "farewells": [
                    "Ладно, побегу",
                    "Надо работать",
                    "Давай позже спишемся",
                    "Удачи тебе!",
                    "Пока, до связи!"
                ]
            }
            
            for topic_idx, topic in enumerate(topics):
                dialogue = []
                current_topic = topic
                
                # Начало диалога (приветствие)
                dialogue.append({"from": "A", "text": f"Привет! Как насчет {current_topic} обсудить?"})
                dialogue.append({"from": "B", "text": f"Привет! С удовольствием. Что именно интересует?"})
                
                # Генерируем 58 пар сообщений (всего 116 + 4 = 120)
                for i in range(58):
                    if i % 5 == 0:
                        # Смена подтемы
                        subtopics = [
                            f"А что думаешь о последних событиях в {current_topic}?",
                            f"У тебя есть опыт в {current_topic}?",
                            f"Какие планы в сфере {current_topic}?",
                            f"Что нового в мире {current_topic}?",
                            f"Как относишься к развитию {current_topic}?"
                        ]
                        dialogue.append({"from": "A" if i % 2 == 0 else "B", "text": random.choice(subtopics)})
                    
                    elif i % 7 == 0:
                        # Вопрос о мнении
                        dialogue.append({"from": "A" if i % 2 == 0 else "B", "text": random.choice(phrases["opinions"])})
                    
                    elif i % 11 == 0:
                        # Шутка или история
                        dialogue.append({"from": "A" if i % 2 == 0 else "B", "text": random.choice(phrases["jokes"])})
                    
                    elif i % 13 == 0:
                        # Воспоминания
                        dialogue.append({"from": "A" if i % 2 == 0 else "B", "text": random.choice(phrases["memories"])})
                    
                    else:
                        # Обычный обмен мнениями
                        message_types = ["interests", "experiences", "advice", "plans"]
                        msg_type = random.choice(message_types)
                        dialogue.append({"from": "A" if i % 2 == 0 else "B", "text": random.choice(phrases[msg_type])})
                
                # Завершение диалога
                dialogue.append({"from": "A", "text": random.choice(phrases["farewells"])})
                dialogue.append({"from": "B", "text": random.choice(phrases["farewells"])})
                
                dialogues.append(dialogue)
            
            # Сохраняем в файл
            with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=2)
            
            return dialogues
    
    def get_random_dialogue(self) -> List[Dict]:
        """Возвращает случайный диалог"""
        return random.choice(self.dialogues)
    
    def get_dialogue_by_index(self, index: int) -> List[Dict]:
        """Возвращает диалог по индексу"""
        return self.dialogues[index % len(self.dialogues)]

# Класс для управления аккаунтами
class AccountManager:
    def __init__(self):
        self.accounts: Dict[str, Client] = {}
        self.active_warmups: Dict[str, Dict] = {}
        self.pending_authorizations: Dict[int, Dict] = {}
        self.load_accounts_data()
    
    def load_accounts_data(self):
        """Загружает данные аккаунтов из файла"""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                self.accounts_data = json.load(f)
        else:
            self.accounts_data = {}
            self.save_accounts_data()
    
    def save_accounts_data(self):
        """Сохраняет данные аккаунтов в файл"""
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.accounts_data, f, ensure_ascii=False, indent=2)
    
    def get_available_sessions(self) -> List[str]:
        """Возвращает список доступных session файлов"""
        sessions = []
        for file in os.listdir(SESSIONS_DIR):
            if file.endswith('.session'):
                session_name = file.replace('.session', '')
                sessions.append(session_name)
        return sessions
    
    async def set_random_username(self, client: Client) -> Optional[str]:
        """Устанавливает случайный username для аккаунта"""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                new_username = UsernameGenerator.generate_username()
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
    
    async def send_test_message(self, client: Client) -> bool:
        """Отправляет тестовое сообщение администратору"""
        try:
            await client.send_message(ADMIN_USERNAME, "Привет! Аккаунт успешно добавлен и готов к работе!")
            logger.info(f"Тестовое сообщение отправлено {ADMIN_USERNAME}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке тестового сообщения: {e}")
            return False
    
    async def add_account_by_session_file(self, file_path: str, filename: str) -> Tuple[bool, str]:
        """Добавляет аккаунт через session файл"""
        try:
            dest_path = os.path.join(SESSIONS_DIR, filename)
            shutil.copy2(file_path, dest_path)
            
            session_name = filename.replace('.session', '')
            client = Client(dest_path.replace('.session', ''), api_id=API_ID, api_hash=API_HASH)
            await client.connect()
            
            me = await client.get_me()
            if not me:
                await client.disconnect()
                os.remove(dest_path)
                return False, "Не удалось получить данные аккаунта"
            
            if not me.username:
                logger.info(f"У аккаунта {me.first_name} нет username, устанавливаем случайный...")
                new_username = await self.set_random_username(client)
                if new_username:
                    me = await client.get_me()
            
            # Отправляем тестовое сообщение
            await self.send_test_message(client)
            
            await client.disconnect()
            
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'session_file'
            }
            self.save_accounts_data()
            
            username_text = f" (@{me.username})" if me.username else ""
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен и отправил приветствие @{ADMIN_USERNAME}"
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении session файла: {e}")
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
                'temp_path': temp_path
            }
            
            return True, "✅ Код подтверждения отправлен на ваш телефон"
            
        except Exception as e:
            logger.error(f"Ошибка при отправке кода: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def complete_phone_authorization(self, user_id: int, code: str = None, password: str = None) -> Tuple[bool, str]:
        """Завершает авторизацию по коду"""
        try:
            if user_id not in self.pending_authorizations:
                return False, "Сессия авторизации не найдена"
            
            auth_data = self.pending_authorizations[user_id]
            client = auth_data['client']
            
            try:
                if password:
                    await client.check_password(password)
                else:
                    await client.sign_in(
                        phone_number=auth_data['phone'],
                        phone_code_hash=auth_data['phone_code_hash'],
                        phone_code=code
                    )
            except SessionPasswordNeeded:
                auth_data['step'] = 'waiting_password'
                return False, "password_needed"
            except Exception as e:
                return False, f"Ошибка при входе: {str(e)}"
            
            me = await client.get_me()
            
            if not me.username:
                logger.info(f"У аккаунта {me.first_name} нет username, устанавливаем случайный...")
                new_username = await self.set_random_username(client)
                if new_username:
                    me = await client.get_me()
            
            # Отправляем тестовое сообщение
            await self.send_test_message(client)
            
            session_name = f"{me.phone_number or me.id}"
            session_path = os.path.join(SESSIONS_DIR, session_name)
            
            await client.storage.save()
            
            temp_session_file = f"{auth_data['temp_path']}.session"
            dest_session_file = f"{session_path}.session"
            
            if os.path.exists(temp_session_file):
                shutil.copy2(temp_session_file, dest_session_file)
            
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'phone_auth'
            }
            self.save_accounts_data()
            
            await client.disconnect()
            
            if os.path.exists(temp_session_file):
                os.remove(temp_session_file)
            
            if user_id in self.pending_authorizations:
                del self.pending_authorizations[user_id]
            
            username_text = f" (@{me.username})" if me.username else ""
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен и отправил приветствие @{ADMIN_USERNAME}"
            
        except Exception as e:
            logger.error(f"Ошибка при завершении авторизации: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def add_account(self, session_name: str) -> bool:
        """Добавляет аккаунт в менеджер для использования"""
        if session_name in self.accounts:
            return True
        
        try:
            session_path = os.path.join(SESSIONS_DIR, session_name)
            client = Client(session_path, api_id=API_ID, api_hash=API_HASH)
            await client.connect()
            
            me = await client.get_me()
            if not me:
                await client.disconnect()
                return False
            
            self.accounts[session_name] = client
            
            if session_name not in self.accounts_data:
                self.accounts_data[session_name] = {
                    'phone': me.phone_number if me.phone_number else 'unknown',
                    'first_name': me.first_name,
                    'username': me.username,
                    'added_date': datetime.now().isoformat(),
                    'is_active': True
                }
                self.save_accounts_data()
            
            logger.info(f"Аккаунт {session_name} успешно добавлен в менеджер")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении аккаунта {session_name}: {e}")
            return False
    
    async def remove_account(self, session_name: str):
        """Удаляет аккаунт из менеджера"""
        if session_name in self.accounts:
            client = self.accounts[session_name]
            await client.disconnect()
            del self.accounts[session_name]
        
        session_path = os.path.join(SESSIONS_DIR, f"{session_name}.session")
        if os.path.exists(session_path):
            os.remove(session_path)
        
        if session_name in self.accounts_data:
            del self.accounts_data[session_name]
            self.save_accounts_data()
    
    def get_active_accounts(self) -> List[str]:
        """Возвращает список активных аккаунтов"""
        return [name for name, data in self.accounts_data.items() if data.get('is_active', True)]
    
    def get_account_display_name(self, session_name: str) -> str:
        """Возвращает отображаемое имя аккаунта"""
        if session_name in self.accounts_data:
            data = self.accounts_data[session_name]
            username = f"@{data.get('username', 'no_username')}" if data.get('username') else 'без username'
            return f"{data.get('first_name', session_name)} ({username})"
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

# Класс для прогрева аккаунтов
class WarmupManager:
    def __init__(self, account_manager: AccountManager, dialogue_manager: DialogueManager):
        self.account_manager = account_manager
        self.dialogue_manager = dialogue_manager
        self.warmup_tasks: Dict[str, asyncio.Task] = {}
    
    async def start_warmup(self, chat_id: int, selected_accounts: List[str]):
        """Запускает прогрев аккаунтов"""
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
            'current_dialogue': 0
        }
        
        return warmup_id
    
    async def stop_warmup(self, warmup_id: str):
        """Останавливает прогрев"""
        if warmup_id in self.warmup_tasks:
            self.warmup_tasks[warmup_id].cancel()
            del self.warmup_tasks[warmup_id]
            
        if warmup_id in self.account_manager.active_warmups:
            self.account_manager.active_warmups[warmup_id]['status'] = 'stopped'
    
    async def stop_all_warmups_for_chat(self, chat_id: int):
        """Останавливает все прогревы для конкретного чата"""
        to_stop = []
        for warmup_id, data in self.account_manager.active_warmups.items():
            if data.get('chat_id') == chat_id and data.get('status') == 'running':
                to_stop.append(warmup_id)
        
        for warmup_id in to_stop:
            await self.stop_warmup(warmup_id)
    
    async def _warmup_process(self, chat_id: int, accounts: List[str], warmup_id: str):
        """Процесс прогрева аккаунтов"""
        try:
            # Добавляем аккаунты в менеджер
            for account in accounts:
                await self.account_manager.add_account(account)
            
            await asyncio.sleep(5)
            
            dialogue_count = 0
            total_messages = 0
            
            # Бесконечный цикл прогрева (пока не остановят)
            while warmup_id in self.warmup_tasks:
                # Получаем случайный диалог
                dialogue = self.dialogue_manager.get_random_dialogue()
                dialogue_count += 1
                
                logger.info(f"[{warmup_id}] Начинаем диалог #{dialogue_count} из {len(dialogue)} сообщений")
                
                # Проигрываем диалог
                for msg_index, msg_data in enumerate(dialogue):
                    if warmup_id not in self.warmup_tasks:
                        break
                    
                    # Определяем отправителя и получателя
                    if msg_data["from"] == "A":
                        sender_idx = 0
                        receiver_idx = 1
                    else:
                        sender_idx = 1
                        receiver_idx = 0
                    
                    sender = accounts[sender_idx % len(accounts)]
                    receiver = accounts[receiver_idx % len(accounts)]
                    
                    sender_client = self.account_manager.accounts.get(sender)
                    if not sender_client:
                        continue
                    
                    receiver_username = await self.account_manager.get_username_by_session(receiver)
                    if not receiver_username:
                        continue
                    
                    try:
                        # Отправляем сообщение
                        await sender_client.send_message(receiver_username, msg_data["text"])
                        
                        total_messages += 1
                        self.account_manager.active_warmups[warmup_id]['message_count'] = total_messages
                        self.account_manager.active_warmups[warmup_id]['current_dialogue'] = dialogue_count
                        self.account_manager.active_warmups[warmup_id]['dialogue_count'] = dialogue_count
                        
                        logger.info(f"[{warmup_id}] Диалог #{dialogue_count}, сообщение #{msg_index+1}: {sender} -> {receiver}")
                        
                        # Случайная задержка между сообщениями 5-40 секунд
                        delay = random.uniform(5, 40)
                        await asyncio.sleep(delay)
                        
                    except FloodWait as e:
                        logger.warning(f"Flood wait: {e.value} секунд")
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        logger.error(f"Ошибка при отправке сообщения: {e}")
                        continue
                
                # Пауза между диалогами 5-10 минут (300-600 секунд)
                if warmup_id in self.warmup_tasks:
                    pause = random.uniform(300, 600)
                    minutes = pause / 60
                    logger.info(f"[{warmup_id}] Диалог #{dialogue_count} завершен. Пауза {minutes:.1f} минут перед следующим диалогом")
                    
                    # Отправляем уведомление о паузе
                    try:
                        bot_client = next(iter(self.account_manager.accounts.values()))
                        if bot_client:
                            await bot_client.send_message(
                                chat_id,
                                f"⏸ Диалог #{dialogue_count} завершен. Следующий диалог через {minutes:.1f} минут. Отправлено сообщений: {total_messages}"
                            )
                    except:
                        pass
                    
                    await asyncio.sleep(pause)
            
        except asyncio.CancelledError:
            logger.info(f"Прогрев {warmup_id} остановлен. Всего диалогов: {dialogue_count}, сообщений: {total_messages}")
        except Exception as e:
            logger.error(f"Ошибка в процессе прогрева: {e}")
            if warmup_id in self.account_manager.active_warmups:
                self.account_manager.active_warmups[warmup_id]['status'] = 'error'

# Инициализация бота
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

# Хранение временных данных пользователей
user_data = {}

# Функция для создания главного меню
def get_main_menu():
    """Возвращает главное меню"""
    buttons = [
        [InlineKeyboardButton("📱 Мои аккаунты", callback_data="menu_accounts")],
        [InlineKeyboardButton("➕ Добавить аккаунт", callback_data="menu_add")],
        [InlineKeyboardButton("🚀 Запустить прогрев", callback_data="menu_warmup")],
        [InlineKeyboardButton("📊 Статус прогрева", callback_data="menu_status")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
    ]
    return InlineKeyboardMarkup(buttons)

# Команда старт
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 **Добро пожаловать в бота для прогрева Telegram аккаунтов!**\n\n"
        "✨ **Новые возможности:**\n"
        "• Диалоги по 120 сообщений каждый\n"
        "• Задержка 5-40 секунд между сообщениями\n"
        "• Пауза 5-10 минут между диалогами\n"
        "• 20 уникальных длинных диалогов\n"
        "• Тестовое приветствие @v3estnikov при добавлении\n\n"
        "Выберите действие в меню ниже:",
        reply_markup=get_main_menu()
    )

# Обработка callback запросов
@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    message = callback_query.message
    
    # Главное меню
    if data == "main_menu":
        await message.edit_text(
            "👋 **Главное меню**\n\nВыберите действие:",
            reply_markup=get_main_menu()
        )
        await callback_query.answer()
    
    # Меню помощи
    elif data == "menu_help":
        text = (
            "❓ **Помощь по использованию**\n\n"
            "🔹 **Добавление аккаунтов:**\n"
            "• Отправьте .session файл боту\n"
            "• Или нажмите 'Добавить по номеру'\n"
            "• После добавления аккаунт отправит приветствие @v3estnikov\n\n"
            "🔹 **Запуск прогрева:**\n"
            "1. Добавьте минимум 2 аккаунта\n"
            "2. Нажмите 'Запустить прогрев'\n"
            "3. Выберите аккаунты для диалога\n"
            "4. Аккаунты начнут общаться\n\n"
            "🔹 **Параметры прогрева:**\n"
            "• Диалоги: 120 сообщений каждый\n"
            "• Задержка: 5-40 секунд между сообщениями\n"
            "• Пауза: 5-10 минут между диалогами\n"
            "• Всего диалогов: 20 уникальных\n\n"
            "🔹 **Управление:**\n"
            "• Прогрев можно остановить в любой момент\n"
            "• Статус показывает прогресс\n"
            "• Аккаунты можно удалять"
        )
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
            ]])
        )
        await callback_query.answer()
    
    # Меню добавления аккаунта
    elif data == "menu_add":
        buttons = [
            [InlineKeyboardButton("📁 Загрузить .session файл", callback_data="add_session")],
            [InlineKeyboardButton("📱 Добавить по номеру", callback_data="add_phone")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        await message.edit_text(
            "📥 **Добавление аккаунта**\n\n"
            "Выберите способ добавления:\n"
            "После добавления аккаунт отправит приветствие @v3estnikov",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    # Добавление по номеру
    elif data == "add_phone":
        if chat_id in account_manager.pending_authorizations:
            await callback_query.answer("Уже есть активная авторизация!", show_alert=True)
            return
        
        await message.edit_text(
            "📱 **Введите номер телефона** в международном формате:\n"
            "Например: `+79001234567`\n\n"
            "Отправьте номер в чат (или /cancel для отмены)",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
            ]])
        )
        
        user_data[chat_id] = {'state': 'waiting_phone'}
        await callback_query.answer()
    
    # Добавление session файла - инструкция
    elif data == "add_session":
        await message.edit_text(
            "📁 **Загрузка .session файла**\n\n"
            "Просто отправьте .session файл в этот чат.\n\n"
            "После загрузки аккаунт автоматически:\n"
            "• Проверит наличие username (установит случайный при необходимости)\n"
            "• Отправит приветствие @v3estnikov\n"
            "• Сохранится в базу аккаунтов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="menu_add")
            ]])
        )
        await callback_query.answer()
    
    # Просмотр аккаунтов
    elif data == "menu_accounts":
        available = account_manager.get_available_sessions()
        
        if not available:
            text = "📱 **Мои аккаунты**\n\nУ вас пока нет добавленных аккаунтов."
            buttons = [[InlineKeyboardButton("➕ Добавить аккаунт", callback_data="menu_add")]]
        else:
            text = "📱 **Мои аккаунты**\n\n"
            for session in available:
                display_name = account_manager.get_account_display_name(session)
                source = account_manager.accounts_data.get(session, {}).get('source', 'session_file')
                source_text = "📁" if source == 'session_file' else "📱"
                text += f"{source_text} {display_name}\n"
            
            buttons = [[InlineKeyboardButton("🗑 Удалить аккаунт", callback_data="menu_remove")]]
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer()
    
    # Меню удаления аккаунтов
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
    
    # Удаление конкретного аккаунта
    elif data.startswith("remove_"):
        session = data.replace("remove_", "")
        await account_manager.remove_account(session)
        await callback_query.answer("✅ Аккаунт удален")
        
        # Возвращаемся к списку аккаунтов
        available = account_manager.get_available_sessions()
        if available:
            text = "📱 **Мои аккаунты**\n\n"
            for s in available:
                display_name = account_manager.get_account_display_name(s)
                source = account_manager.accounts_data.get(s, {}).get('source', 'session_file')
                source_text = "📁" if source == 'session_file' else "📱"
                text += f"{source_text} {display_name}\n"
            
            buttons = [
                [InlineKeyboardButton("🗑 Удалить аккаунт", callback_data="menu_remove")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]
        else:
            text = "📱 **Мои аккаунты**\n\nУ вас пока нет добавленных аккаунтов."
            buttons = [
                [InlineKeyboardButton("➕ Добавить аккаунт", callback_data="menu_add")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    # Меню запуска прогрева
    elif data == "menu_warmup":
        available = account_manager.get_available_sessions()
        
        if len(available) < 2:
            await callback_query.answer(
                "❌ Для прогрева нужно минимум 2 аккаунта!\nСейчас: " + str(len(available)),
                show_alert=True
            )
            return
        
        # Добавляем аккаунты в менеджер
        added_accounts = []
        for session in available:
            if await account_manager.add_account(session):
                added_accounts.append(session)
        
        if len(added_accounts) < 2:
            await callback_query.answer(
                "❌ Не удалось активировать аккаунты!\nПроверьте session файлы",
                show_alert=True
            )
            return
        
        # Создаем клавиатуру для выбора
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
            "📝 **Выберите аккаунты для прогрева (минимум 2):**\n"
            "Нажимайте на аккаунты для выбора",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        user_data[chat_id] = {'selected_accounts': []}
        await callback_query.answer()
    
    # Выбор аккаунта
    elif data.startswith("select_"):
        session = data.replace("select_", "")
        
        if chat_id not in user_data:
            user_data[chat_id] = {'selected_accounts': []}
        
        selected = user_data[chat_id]['selected_accounts']
        
        if session in selected:
            selected.remove(session)
            await callback_query.answer(f"❌ Аккаунт убран")
        else:
            selected.append(session)
            await callback_query.answer(f"✅ Аккаунт добавлен")
        
        # Обновляем клавиатуру
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
    
    # Запуск прогрева
    elif data == "start_warmup":
        if chat_id not in user_data or len(user_data[chat_id]['selected_accounts']) < 2:
            await callback_query.answer("❌ Выберите минимум 2 аккаунта!", show_alert=True)
            return
        
        selected = user_data[chat_id]['selected_accounts']
        warmup_id = await warmup_manager.start_warmup(chat_id, selected)
        
        await message.edit_text(
            f"🚀 **Прогрев запущен!**\n\n"
            f"**Аккаунты:** {len(selected)}\n"
            f"**Параметры:**\n"
            f"• Сообщений в диалоге: 120\n"
            f"• Задержка: 5-40 секунд\n"
            f"• Пауза между диалогами: 5-10 минут\n\n"
            f"Используйте кнопки ниже для управления:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Статус", callback_data="menu_status"),
                 InlineKeyboardButton("🛑 Остановить", callback_data="stop_warmup")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        
        await callback_query.answer("✅ Прогрев запущен!")
    
    # Остановка прогрева
    elif data == "stop_warmup":
        await warmup_manager.stop_all_warmups_for_chat(chat_id)
        await message.edit_text(
            "🛑 **Прогрев остановлен**\n\n"
            "Выберите действие в меню:",
            reply_markup=get_main_menu()
        )
        await callback_query.answer("✅ Прогрев остановлен")
    
    # Статус прогрева
    elif data == "menu_status":
        active = []
        for warmup_id, data in account_manager.active_warmups.items():
            if data.get('chat_id') == chat_id:
                active.append(data)
        
        if not active:
            await callback_query.answer("📊 Нет активных прогревов", show_alert=True)
            return
        
        data = active[0]
        accounts_text = "\n".join([f"• {account_manager.get_account_display_name(a)}" for a in data['accounts']])
        
        # Рассчитываем прогресс
        messages_per_dialogue = 120
        current_dialogue = data.get('dialogue_count', 0)
        current_messages = data.get('message_count', 0)
        messages_in_current = current_messages % messages_per_dialogue if current_messages > 0 else 0
        
        text = (
            f"📊 **Статус прогрева**\n\n"
            f"**Аккаунты:**\n{accounts_text}\n"
            f"**Всего сообщений:** {current_messages}\n"
            f"**Текущий диалог:** {current_dialogue}\n"
            f"**Сообщений в диалоге:** {messages_in_current}/120\n"
            f"**Статус:** {data['status']}\n\n"
            f"**Параметры:**\n"
            f"• Задержка: 5-40 сек\n"
            f"• Пауза между диалогами: 5-10 мин\n\n"
            f"Используйте кнопки ниже:"
        )
        
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 Остановить", callback_data="stop_warmup")],
                [InlineKeyboardButton("🔄 Обновить", callback_data="menu_status"),
                 InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ])
        )
        await callback_query.answer()

# Обработка документов (session файлов)
@app.on_message(filters.document)
async def handle_document(client: Client, message: Message):
    if not message.document.file_name.endswith('.session'):
        await message.reply_text(
            "❌ Пожалуйста, отправьте файл с расширением .session",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
        return
    
    status_msg = await message.reply_text("⏳ Загружаю файл...")
    
    file_path = await message.download(file_name=TEMP_DIR)
    success, result_text = await account_manager.add_account_by_session_file(
        file_path, 
        message.document.file_name
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

# Обработка текстовых сообщений
@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_text(client: Client, message: Message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Обработка отмены
    if text.lower() == "/cancel":
        if chat_id in account_manager.pending_authorizations:
            auth_data = account_manager.pending_authorizations[chat_id]
            if 'client' in auth_data:
                await auth_data['client'].disconnect()
            del account_manager.pending_authorizations[chat_id]
        
        if chat_id in user_data:
            del user_data[chat_id]
        
        await message.reply_text(
            "✅ Авторизация отменена",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]])
        )
        return
    
    # Обработка ввода номера телефона
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
                "Введите код из SMS:\n"
                "(или /cancel для отмены)",
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
    
    # Обработка ввода кода
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
                    "Введите ваш пароль:",
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
            else:
                await message.reply_text(
                    f"❌ {result}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
                    ]])
                )
                if chat_id in account_manager.pending_authorizations:
                    await account_manager.pending_authorizations[chat_id]['client'].disconnect()
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

# Запуск бота
if __name__ == "__main__":
    print("🚀 Бот запущен...")
    print(f"API ID: {API_ID}")
    print(f"Папка sessions: {SESSIONS_DIR}")
    print(f"Папка temp: {TEMP_DIR}")
    print(f"Администратор: @{ADMIN_USERNAME}")
    print("\n📱 Управление через кнопки в Telegram")
    print("Напишите /start для начала работы")
    print("\n✨ Новые функции:")
    print("• Приветствие @v3estnikov при добавлении аккаунта")
    print("• Диалоги по 120 сообщений")
    print("• Задержка 5-40 секунд между сообщениями")
    print("• Пауза 5-10 минут между диалогами")
    print("• 20 уникальных длинных диалогов")
    app.run()

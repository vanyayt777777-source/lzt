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
from pyrogram.errors import FloodWait, SessionPasswordNeeded, UsernameInvalid, UsernameNotOccupied
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
        """Загружает готовые диалоги из файла"""
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем 20 готовых естественных диалогов
            dialogues = [
                # Диалог 1: О погоде и планах
                [
                    {"from": "A", "text": "Привет! Как погода у вас?"},
                    {"from": "B", "text": "Привет! Солнечно, тепло. А у вас?"},
                    {"from": "A", "text": "Тоже хорошо, +20. Планируешь на выходные куда-то?"},
                    {"from": "B", "text": "Да, хочу на природу выбраться. А ты?"},
                    {"from": "A", "text": "Отлично! Я тоже думаю шашлыки пожарить"},
                    {"from": "B", "text": "Класс! Может вместе? Я шашлык хорошо делаю"},
                    {"from": "A", "text": "С удовольствием! Давай созвонимся ближе к выходным"},
                    {"from": "B", "text": "Договорились! Хорошего дня"}
                ],
                # Диалог 2: О работе и IT
                [
                    {"from": "A", "text": "Привет! Как работа?"},
                    {"from": "B", "text": "Привет! Нормально, проект сдаем. А у тебя?"},
                    {"from": "A", "text": "Тоже работаю, новый проект на Python начали"},
                    {"from": "B", "text": "Ого, интересно! Что за проект?"},
                    {"from": "A", "text": "Чат-бот для автоматизации продаж"},
                    {"from": "B", "text": "Круто! Я тоже недавно бота писал"},
                    {"from": "A", "text": "Можем опытом обменяться"},
                    {"from": "B", "text": "Давай, скинь свой код в обед"},
                    {"from": "A", "text": "Ок, договорились!"}
                ],
                # Диалог 3: О фильмах
                [
                    {"from": "A", "text": "Привет! Смотрел новый фильм с Ди Каприо?"},
                    {"from": "B", "text": "Привет! Да, 'Убийцы цветочной луны'? Отличный фильм!"},
                    {"from": "A", "text": "Да, очень понравился. А тебе как?"},
                    {"from": "B", "text": "Тоже зашел, хотя длинноват немного"},
                    {"from": "A", "text": "Согласен, 3.5 часа многовато. Но игра актеров шикарная"},
                    {"from": "B", "text": "Да, Ди Каприо как всегда на высоте. Что еще посоветуешь?"},
                    {"from": "A", "text": "Посмотри 'Оппенгеймер', если еще не видел"},
                    {"from": "B", "text": "О, спасибо! Как раз собирался"},
                    {"from": "A", "text": "Не за что, приятного просмотра!"}
                ],
                # Диалог 4: О спорте
                [
                    {"from": "A", "text": "Привет! В спортзал ходишь?"},
                    {"from": "B", "text": "Привет! Да, три раза в неделю. А ты?"},
                    {"from": "A", "text": "Я бегаю по утрам, в зал пока не хожу"},
                    {"from": "B", "text": "Бег тоже отлично. Сколько километров?"},
                    {"from": "A", "text": "Обычно 5-7 км, по настроению"},
                    {"from": "B", "text": "Молодец! Я тоже хочу начать бегать, но лень"},
                    {"from": "A", "text": "Главное начать, потом втянешься. Давай вместе начнем?"},
                    {"from": "B", "text": "Хорошая идея! Завтра с утра?"},
                    {"from": "A", "text": "Давай в 7 утра, напишу тебе"},
                    {"from": "B", "text": "Ок, жду!"}
                ],
                # Диалог 5: О путешествиях
                [
                    {"from": "A", "text": "Привет! Куда планируешь в отпуск?"},
                    {"from": "B", "text": "Привет! Думаю в Сочи съездить. А ты?"},
                    {"from": "A", "text": "Я в Турцию хочу, море хочется"},
                    {"from": "B", "text": "Класс! Когда летишь?"},
                    {"from": "A", "text": "В июне, как раз сезон начинается"},
                    {"from": "B", "text": "Отлично. Я был в Турции в прошлом году, понравилось"},
                    {"from": "A", "text": "А какой отель посоветуешь?"},
                    {"from": "B", "text": "Я был в Rixos, очень достойно. Все включено супер"},
                    {"from": "A", "text": "Спасибо, посмотрю! А ты в Сочи где остановишься?"},
                    {"from": "B", "text": "Думаю в центре, чтобы близко к морю и развлечениям"},
                    {"from": "A", "text": "Отличный выбор! Хорошего отдыха!"}
                ],
                # Диалог 6: О еде и ресторанах
                [
                    {"from": "A", "text": "Привет! Не знаешь хороший ресторан итальянской кухни?"},
                    {"from": "B", "text": "Привет! Есть отличный - 'La Trattoria' на Пушкина"},
                    {"from": "A", "text": "О, слышал о нем. Дорого?"},
                    {"from": "B", "text": "Нормально, средний ценник. Зато паста божественная"},
                    {"from": "A", "text": "Отлично, спасибо! А сам там давно был?"},
                    {"from": "B", "text": "На прошлой неделе, с женой ходили. Тирамису советую"},
                    {"from": "A", "text": "Обожаю тирамису! Забронирую столик"},
                    {"from": "B", "text": "Да, лучше забронировать, вечером всегда полно"},
                    {"from": "A", "text": "Спасибо за совет! Может сходим вместе как-нибудь?"},
                    {"from": "B", "text": "С удовольствием! Давай на следующей неделе"},
                    {"from": "A", "text": "Договорились!"}
                ],
                # Диалог 7: О книгах
                [
                    {"from": "A", "text": "Привет! Что читаешь сейчас?"},
                    {"from": "B", "text": "Привет! '1984' Оруэлла перечитываю, классика"},
                    {"from": "A", "text": "Отличная книга! Я тоже недавно перечитал"},
                    {"from": "B", "text": "Актуально до сих пор, удивительно"},
                    {"from": "A", "text": "Да, Оруэлл будто предвидел будущее. А что еще нравится?"},
                    {"from": "B", "text": "Из последнего - 'Метро 2033' Глуховского зашло"},
                    {"from": "A", "text": "О, постапокалипсис. Я больше фантастику люблю"},
                    {"from": "B", "text": "Стругацких читал? 'Пикник на обочине' шедевр"},
                    {"from": "A", "text": "Да, конечно! 'Сталкер' по ней снят"},
                    {"from": "B", "text": "Тарковский гений. Можем обменяться книгами"},
                    {"from": "A", "text": "Давай! У меня есть что тебе предложить"}
                ],
                # Диалог 8: О машинах
                [
                    {"from": "A", "text": "Привет! Слышал, ты новую машину купил?"},
                    {"from": "B", "text": "Привет! Да, Toyota Camry, доволен как слон"},
                    {"from": "A", "text": "Поздравляю! Отличный выбор. Какая комплектация?"},
                    {"from": "B", "text": "Спасибо! Люкс, с панорамой. Очень комфортная"},
                    {"from": "A", "text": "Класс! А расход какой?"},
                    {"from": "B", "text": "В городе около 10, по трассе 7. Нормально для такого объема"},
                    {"from": "A", "text": "Да, вполне. Я на механике езжу, экономнее"},
                    {"from": "B", "text": "В пробках тяжело на механике? Я в Москве замучился"},
                    {"from": "A", "text": "Привык уже, но автомат конечно удобнее. Может прокатишь?"},
                    {"from": "B", "text": "Легко! Давай в выходные?"},
                    {"from": "A", "text": "Договорились!"}
                ],
                # Диалог 9: О хобби
                [
                    {"from": "A", "text": "Привет! Чем увлекаешься в свободное время?"},
                    {"from": "B", "text": "Привет! Фотографией занимаюсь, пейзажи снимаю"},
                    {"from": "A", "text": "Ого, интересно! Покажешь свои работы?"},
                    {"from": "B", "text": "Да, конечно. Могу ссылку на инстаграм скинуть"},
                    {"from": "A", "text": "Буду благодарен. А на какую камеру снимаешь?"},
                    {"from": "B", "text": "На Sony A7 III, отличная камера. А ты чем увлекаешься?"},
                    {"from": "A", "text": "Я гитару осваиваю, пока на начальном уровне"},
                    {"from": "B", "text": "Круто! Я тоже когда-то пробовал, но забросил"},
                    {"from": "A", "text": "Главное регулярно заниматься. Может научишь фоткать?"},
                    {"from": "B", "text": "С удовольствием! Могу мастер-класс провести"},
                    {"from": "A", "text": "Супер! Буду ждать"}
                ],
                # Диалог 10: О технологиях
                [
                    {"from": "A", "text": "Привет! Пользуешься нейросетями?"},
                    {"from": "B", "text": "Привет! Да, постоянно ChatGPT помогает с работой"},
                    {"from": "A", "text": "А я для картинок Midjourney использую. Видел?"},
                    {"from": "B", "text": "Да, крутые вещи генерит. Но платная же?"},
                    {"from": "A", "text": "Да, но качество стоит того. Для дизайна отлично"},
                    {"from": "B", "text": "А я пробовал Kandinsky, бесплатно и неплохо"},
                    {"from": "A", "text": "Тоже вариант. Главное, что прогресс не стоит на месте"},
                    {"from": "B", "text": "Согласен. Думаю, через год еще круче будет"},
                    {"from": "A", "text": "Да уж, интересное время. Может вместе проект запилим на ИИ?"},
                    {"from": "B", "text": "Хорошая идея! Давай подумаем"},
                    {"from": "A", "text": "Ок, накидаю идей, скину потом"}
                ]
            ]
            
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
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен"
            
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
            return True, f"✅ Аккаунт {me.first_name}{username_text} успешно добавлен"
            
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
            'dialogue_index': 0
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
            
            await asyncio.sleep(2)
            
            # Бесконечный цикл прогрева (пока не остановят)
            dialogue_index = 0
            while warmup_id in self.warmup_tasks:
                # Получаем случайный диалог
                dialogue = self.dialogue_manager.get_dialogue_by_index(dialogue_index)
                dialogue_index += 1
                
                logger.info(f"[{warmup_id}] Начинаем новый диалог из {len(dialogue)} сообщений")
                
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
                        await sender_client.send_message(receiver_username, msg_data["text"])
                        
                        self.account_manager.active_warmups[warmup_id]['message_count'] += 1
                        self.account_manager.active_warmups[warmup_id]['dialogue_index'] = dialogue_index
                        
                        logger.info(f"[{warmup_id}] {sender} -> {receiver}: {msg_data['text'][:50]}...")
                        
                        # Задержка между сообщениями 5-10 секунд
                        delay = random.uniform(5, 10)
                        await asyncio.sleep(delay)
                        
                    except FloodWait as e:
                        logger.warning(f"Flood wait: {e.value} секунд")
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        logger.error(f"Ошибка при отправке сообщения: {e}")
                        continue
                
                # Пауза между диалогами 30-60 секунд
                if warmup_id in self.warmup_tasks:
                    pause = random.uniform(30, 60)
                    logger.info(f"[{warmup_id}] Пауза между диалогами: {pause:.0f} сек")
                    await asyncio.sleep(pause)
            
        except asyncio.CancelledError:
            logger.info(f"Прогрев {warmup_id} остановлен")
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
        "Я помогу вам прогреть ваши аккаунты, создавая естественные диалоги между ними.\n\n"
        "Выберите действие в меню ниже:",
        reply_markup=get_main_menu()
    )

# Обработка callback запросов
@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    
    # Главное меню
    if data == "main_menu":
        await callback_query.message.edit_text(
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
            "• Или нажмите 'Добавить по номеру'\n\n"
            "🔹 **Запуск прогрева:**\n"
            "1. Добавьте минимум 2 аккаунта\n"
            "2. Нажмите 'Запустить прогрев'\n"
            "3. Выберите аккаунты для диалога\n"
            "4. Аккаунты начнут общаться\n\n"
            "🔹 **Управление:**\n"
            "• Прогрев можно остановить в любой момент\n"
            "• Статус показывает количество сообщений\n"
            "• Аккаунты можно удалять\n\n"
            "⚡️ **Особенности:**\n"
            "• 20+ готовых естественных диалогов\n"
            "• Задержка 5-10 сек между сообщениями\n"
            "• Пауза 30-60 сек между диалогами\n"
            "• Автоматическая установка username"
        )
        await callback_query.message.edit_text(
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
        await callback_query.message.edit_text(
            "📥 **Добавление аккаунта**\n\n"
            "Выберите способ добавления:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
    
    # Добавление по номеру
    elif data == "add_phone":
        if chat_id in account_manager.pending_authorizations:
            await callback_query.answer("Уже есть активная авторизация!", show_alert=True)
            return
        
        await callback_query.message.edit_text(
            "📱 **Введите номер телефона** в международном формате:\n"
            "Например: `+79001234567`\n\n"
            "Отправьте номер в чат (или /cancel для отмены)",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="menu_add")
            ]])
        )
        
        user_data[chat_id] = {'state': 'waiting_phone'}
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
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
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
        
        await callback_query.message.edit_text(
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
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
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
        
        await callback_query.message.edit_text(
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
        
        await callback_query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
    
    # Запуск прогрева
    elif data == "start_warmup":
        if chat_id not in user_data or len(user_data[chat_id]['selected_accounts']) < 2:
            await callback_query.answer("❌ Выберите минимум 2 аккаунта!", show_alert=True)
            return
        
        selected = user_data[chat_id]['selected_accounts']
        warmup_id = await warmup_manager.start_warmup(chat_id, selected)
        
        await callback_query.message.edit_text(
            f"🚀 **Прогрев запущен!**\n\n"
            f"**Аккаунты:** {len(selected)}\n"
            f"**Сообщений:** 0\n\n"
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
        await callback_query.message.edit_text(
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
        text = (
            f"📊 **Статус прогрева**\n\n"
            f"**Аккаунты:**\n{accounts_text}\n"
            f"**Сообщений:** {data.get('message_count', 0)}\n"
            f"**Статус:** {data['status']}\n"
            f"**Диалогов:** {data.get('dialogue_index', 0)}\n\n"
            f"Используйте кнопки ниже:"
        )
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 Остановить", callback_data="stop_warmup")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
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
    print("\n📱 Управление через кнопки в Telegram")
    print("Напишите /start для начала работы")
    app.run()

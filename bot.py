# main.py
import os
import asyncio
import random
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, PeerIdInvalid, UsernameNotOccupied, SessionPasswordNeeded
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

# Класс для управления парами вопрос-ответ
class ConversationManager:
    def __init__(self):
        self.conversations = self.load_conversations()
    
    def load_conversations(self) -> List[Dict[str, str]]:
        """Загружает пары вопрос-ответ из файла"""
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем 100+ пар вопрос-ответ
            conversations = [
                # Приветствия
                {"question": "Привет! Как твои дела?", "answer": "Привет! Отлично, а у тебя как?"},
                {"question": "Здорово! Чем занимаешься?", "answer": "Да вот, по дому делаю, а ты?"},
                {"question": "Хай! Давно не виделись!", "answer": "Привет! Да, давно не общались. Как жизнь?"},
                {"question": "Добрый вечер! Как настроение?", "answer": "Вечер в самом деле добрый! Настроение супер, спасибо!"},
                {"question": "Салют! Как жизнь молодая?", "answer": "Жизнь кипит! Работа, дом, всё как обычно"},
                
                # Погода
                {"question": "Как погода за окном?", "answer": "Солнечно и тепло, отличная погода!"},
                {"question": "Любишь дождливую погоду?", "answer": "Обожаю дождь, особенно сидеть с чашкой кофе и смотреть в окно"},
                {"question": "Какое время года тебе нравится?", "answer": "Больше всего люблю весну, когда всё расцветает"},
                {"question": "У нас снег выпал!", "answer": "Ого, здорово! А у нас пока только дожди"},
                {"question": "Тепло у вас?", "answer": "Да, градусов 20, комфортно"},
                
                # Работа и учеба
                {"question": "Как работа?", "answer": "Нормально, проект интересный делаем. А у тебя?"},
                {"question": "На работе как дела?", "answer": "Всё отлично, начальник хвалит) А ты как?"},
                {"question": "Учёба как?", "answer": "Сессия скоро, готовлюсь потихоньку"},
                {"question": "Кем работаешь?", "answer": "Программистом, пишу на Python. А ты?"},
                {"question": "Зарплату уже дали?", "answer": "На днях обещали, ждём-с"},
                
                # Еда
                {"question": "Что ел сегодня?", "answer": "Пельмени сварил, быстро и вкусно"},
                {"question": "Любишь готовить?", "answer": "Обожаю! Особенно экспериментировать с новыми рецептами"},
                {"question": "Кофе или чай предпочитаешь?", "answer": "Кофе, обязательно с утра, чтобы проснуться"},
                {"question": "Что на ужин сегодня?", "answer": "Думаю пасту сделать с грибами"},
                {"question": "Какой ресторан посоветуешь?", "answer": "Недавно открыли новый итальянский, очень вкусно!"},
                
                # Хобби
                {"question": "Смотрел новый сериал?", "answer": "Да, 'Последний из нас' очень зашёл, советую!"},
                {"question": "Во что играешь?", "answer": "В Cyberpunk 2077 прохожу, понравилось после обновлений"},
                {"question": "Какая музыка в плейлисте?", "answer": "Сейчас залипаю на инди-рок, а ты что слушаешь?"},
                {"question": "Книги читаешь?", "answer": "Да, сейчас '1984' Оруэлла перечитываю"},
                {"question": "Спортом занимаешься?", "answer": "В тренажёрку хожу три раза в неделю"},
                
                # Планы
                {"question": "Какие планы на выходные?", "answer": "Хочу на природу выбраться, шашлыки пожарить"},
                {"question": "Куда хочешь съездить?", "answer": "Мечтаю в Японию, очень культура нравится"},
                {"question": "Чем хочешь научиться?", "answer": "Хочу английский подтянуть и на гитаре научиться"},
                {"question": "Путешествие мечты?", "answer": "Объехать всю Европу на машине"},
                {"question": "Где видишь себя через 5 лет?", "answer": "Своё дело хочу открыть, работаю над этим"},
                
                # Технологии
                {"question": "Какой телефон у тебя?", "answer": "Айфон 13, доволен как слон"},
                {"question": "За игровой ПК или консоль?", "answer": "За ПК, конечно! Модернизировать можно"},
                {"question": "Нейросетями пользуешься?", "answer": "Да, ChatGPT постоянно помогает с работой"},
                {"question": "Как относишься к криптовалюте?", "answer": "С осторожностью, но наблюдаю"},
                {"question": "YouTube смотришь часто?", "answer": "Каждый день, блогеров разных смотрю"},
                
                # Семья
                {"question": "С семьёй виделся?", "answer": "На выходных ездил к родителям, хорошо посидели"},
                {"question": "Есть домашний питомец?", "answer": "Кот есть, рыжий бандит, всё время проказничает"},
                {"question": "Братья/сёстры есть?", "answer": "Да, сестра младшая, учится в школе"},
                {"question": "Как родители поживают?", "answer": "Нормально, на даче сейчас, грядки сажают"},
                {"question": "С кем дружишь с детства?", "answer": "С соседом по парте, до сих пор общаемся"},
                
                # Развлечения
                {"question": "В кино ходил недавно?", "answer": "Да, на 'Дюну 2' ходил, шикарно снято!"},
                {"question": "На концерты ходишь?", "answer": "Люблю живую музыку, недавно на рок-фесте был"},
                {"question": "В клубы ходишь?", "answer": "Редко, больше по душе тихие бары с друзьями"},
                {"question": "Настольные игры любишь?", "answer": "Обожаем с друзьями в 'Мафию' играть"},
                {"question": "Квесты проходил?", "answer": "Да, в хоррор квесте были, очень атмосферно"},
                
                # Здоровье
                {"question": "Как сон?", "answer": "Стараюсь ложиться пораньше, режим соблюдать"},
                {"question": "Медитируешь?", "answer": "Пробую, по утрам 10 минут, помогает сосредоточиться"},
                {"question": "Йогой занимаешься?", "answer": "Начинал, но пока не регулярно"},
                {"question": "Как самочувствие?", "answer": "Бодрячком, спасибо что интересуешься!"},
                {"question": "Витамины пьёшь?", "answer": "Да, комплекс, особенно зимой"},
                
                # Друзья
                {"question": "С друзьями видишься?", "answer": "Планируем встретиться на выходных"},
                {"question": "Есть лучший друг?", "answer": "Да, с ним ещё в садик вместе ходили"},
                {"question": "Коллеги как?", "answer": "Отличный коллектив, с некоторыми вне работы общаемся"},
                {"question": "Новых друзей находишь?", "answer": "Стараюсь быть открытым к новым знакомствам"},
                {"question": "Как обычно отдыхаете с друзьями?", "answer": "Шашлыки, настолки, иногда в боулинг ходим"},
                
                # Фильмы
                {"question": "Какой фильм посоветуешь?", "answer": "Недавно 'Бедные-несчастные' смотрел, необычно"},
                {"question": "Любимый актёр?", "answer": "Ди Каприо, все его фильмы нравятся"},
                {"question": "Сериалы смотришь?", "answer": "Да, сейчас 'Фоллаут' начал, интересно"},
                {"question": "Комедии любишь?", "answer": "Хорошую комедию всегда посмотрю с удовольствием"},
                {"question": "Ужасы смотришь?", "answer": "Нет, не люблю пугаться, лучше что-то позитивное"},
                
                # Путешествия
                {"question": "Где отдыхал недавно?", "answer": "В Сочи был, понравилось очень"},
                {"question": "Любишь море?", "answer": "Обожаю, каждый год стараюсь выбраться"},
                {"question": "В горах был?", "answer": "Да, на Алтае, красота невероятная"},
                {"question": "За границей бывал?", "answer": "В Турции, Египте, планирую Европу посмотреть"},
                {"question": "Страна мечты?", "answer": "Италия, хочу по всем городам проехать"},
                
                # Авто
                {"question": "Машина есть?", "answer": "Да, Тойота, надёжный друг"},
                {"question": "Какая машина нравится?", "answer": "Мечтаю о BMW X5"},
                {"question": "Давно за рулём?", "answer": "Пять лет уже, с 18 лет"},
                {"question": "Любишь быструю езду?", "answer": "По настроению, но правила стараюсь соблюдать"},
                {"question": "На дачу часто ездишь?", "answer": "Каждые выходные летом, помогаю родителям"},
                
                # Спорт
                {"question": "Футбол смотришь?", "answer": "Только чемпионат мира, за наших болею"},
                {"question": "Хоккей нравится?", "answer": "Да, динамичный вид спорта"},
                {"question": "Баскетбол любишь?", "answer": "Сам играю по выходным с друзьями"},
                {"question": "Бегаешь по утрам?", "answer": "Пытаюсь, но не всегда получается встать"},
                {"question": "В спортзал ходишь?", "answer": "Три раза в неделю, стараюсь не пропускать"},
                
                # Компьютеры
                {"question": "За чем сидишь?", "answer": "За ноутбуком, работаю над проектом"},
                {"question": "Какой софт используешь?", "answer": "VS Code, Figma, Photoshop"},
                {"question": "Игры на компе есть?", "answer": "Да, пара игрушек для расслабления"},
                {"question": "Сколько экранов используешь?", "answer": "Два, так удобнее работать"},
                {"question": "Механическая клавиатура?", "answer": "Да, brown switches, очень нравится"},
                
                # Животные
                {"question": "Животных любишь?", "answer": "Обожаю, особенно котиков"},
                {"question": "Собака есть?", "answer": "Лабрадор, весёлый очень"},
                {"question": "Как питомца зовут?", "answer": "Барсик, хитрый как лиса"},
                {"question": "С кошкой играешь?", "answer": "Каждый вечер, она требует внимания"},
                {"question": "Рыбок держал?", "answer": "В детстве были, интересно наблюдать"},
                
                # Еда (продолжение)
                {"question": "Суши любишь?", "answer": "Обожаю, особенно с лососем"},
                {"question": "Пицца с чем?", "answer": "Пепперони, классика"},
                {"question": "Десерт любимый?", "answer": "Тирамису, тает во рту"},
                {"question": "Что пьёшь?", "answer": "Зелёный чай с жасмином"},
                {"question": "Готовить умеешь?", "answer": "Базовые вещи, учусь новому"},
                
                # Психология
                {"question": "Как настроение?", "answer": "Боевое, готов к новым свершениям"},
                {"question": "Что думаешь о жизни?", "answer": "Жизнь прекрасна и удивительна"},
                {"question": "Есть мечта?", "answer": "Конечно, и я к ней иду"},
                {"question": "Что тебя вдохновляет?", "answer": "Люди, которые достигают целей"},
                {"question": "Как справляешься со стрессом?", "answer": "Спорт и музыка помогают"},
                
                # Интернет
                {"question": "В каких соцсетях сидишь?", "answer": "Telegram, VK, иногда Instagram"},
                {"question": "ТикТок смотришь?", "answer": "Залипаю иногда, много полезного"},
                {"question": "Каналы читаешь?", "answer": "Новостные и про IT"},
                {"question": "Блогеров смотришь?", "answer": "Пару штук, про путешествия"},
                {"question": "В Discord сидишь?", "answer": "Да, с друзьями общаемся"},
                
                # Вопросы собеседнику
                {"question": "А у тебя как дела?", "answer": "У меня всё отлично, спасибо!"},
                {"question": "Что сам думаешь?", "answer": "Согласен с тобой полностью"},
                {"question": "А ты как считаешь?", "answer": "Интересная точка зрения"},
                {"question": "Что посоветуешь?", "answer": "Попробуй, не пожалеешь!"},
                {"question": "Как твоё настроение?", "answer": "Рад, что общаемся!"}
            ]
            
            # Сохраняем в файл
            with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
            
            return conversations
    
    def get_random_conversation(self) -> Tuple[str, str]:
        """Возвращает случайную пару вопрос-ответ"""
        pair = random.choice(self.conversations)
        return pair["question"], pair["answer"]
    
    def get_conversation_chain(self, count: int = 10) -> List[Tuple[str, str]]:
        """Возвращает цепочку пар вопрос-ответ"""
        return random.sample(self.conversations, min(count, len(self.conversations)))

# Класс для управления аккаунтами
class AccountManager:
    def __init__(self):
        self.accounts: Dict[str, Client] = {}
        self.active_warmups: Dict[str, Dict] = {}
        self.pending_authorizations: Dict[int, Dict] = {}  # Временные данные для авторизации
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
    
    async def add_account_by_session_file(self, file_path: str, filename: str) -> Tuple[bool, str]:
        """Добавляет аккаунт через session файл"""
        try:
            # Копируем файл в папку sessions
            dest_path = os.path.join(SESSIONS_DIR, filename)
            shutil.copy2(file_path, dest_path)
            
            # Пробуем подключиться
            session_name = filename.replace('.session', '')
            client = Client(dest_path.replace('.session', ''), api_id=API_ID, api_hash=API_HASH)
            await client.connect()
            
            me = await client.get_me()
            if not me:
                await client.disconnect()
                os.remove(dest_path)
                return False, "Не удалось получить данные аккаунта"
            
            await client.disconnect()
            
            # Сохраняем данные
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'session_file'
            }
            self.save_accounts_data()
            
            return True, f"Аккаунт {me.first_name} успешно добавлен"
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении session файла: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def start_phone_authorization(self, user_id: int, phone_number: str) -> Tuple[bool, str]:
        """Начинает авторизацию по номеру телефона"""
        try:
            # Создаем временный клиент
            session_name = f"temp_{user_id}_{int(datetime.now().timestamp())}"
            temp_path = os.path.join(TEMP_DIR, session_name)
            
            client = Client(temp_path, api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await client.connect()
            
            # Отправляем код
            sent_code = await client.send_code(phone_number)
            
            # Сохраняем данные для продолжения авторизации
            self.pending_authorizations[user_id] = {
                'client': client,
                'phone': phone_number,
                'phone_code_hash': sent_code.phone_code_hash,
                'session_name': session_name,
                'step': 'waiting_code'
            }
            
            return True, "Код подтверждения отправлен на ваш телефон"
            
        except Exception as e:
            logger.error(f"Ошибка при отправке кода: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def complete_phone_authorization(self, user_id: int, code: str, password: str = None) -> Tuple[bool, str]:
        """Завершает авторизацию по коду"""
        try:
            if user_id not in self.pending_authorizations:
                return False, "Сессия авторизации не найдена"
            
            auth_data = self.pending_authorizations[user_id]
            client = auth_data['client']
            
            try:
                # Пробуем войти с кодом
                await client.sign_in(
                    phone_number=auth_data['phone'],
                    phone_code_hash=auth_data['phone_code_hash'],
                    phone_code=code
                )
            except SessionPasswordNeeded:
                # Требуется двухфакторная аутентификация
                if password:
                    await client.check_password(password)
                else:
                    auth_data['step'] = 'waiting_password'
                    return False, "password_needed"
            except Exception as e:
                return False, f"Ошибка при входе: {str(e)}"
            
            # Получаем информацию об аккаунте
            me = await client.get_me()
            
            # Сохраняем сессию
            session_name = f"{me.phone_number or me.id}"
            session_path = os.path.join(SESSIONS_DIR, session_name)
            
            # Экспортируем сессию в файл
            await client.export_session_string()
            await client.storage.save()
            
            # Копируем .session файл
            shutil.copy2(f"{auth_data['session_name']}.session", f"{session_path}.session")
            
            # Сохраняем данные
            self.accounts_data[session_name] = {
                'phone': me.phone_number if me.phone_number else 'unknown',
                'first_name': me.first_name,
                'username': me.username,
                'added_date': datetime.now().isoformat(),
                'is_active': True,
                'source': 'phone_auth'
            }
            self.save_accounts_data()
            
            # Закрываем временный клиент
            await client.disconnect()
            
            # Очищаем временные данные
            del self.pending_authorizations[user_id]
            
            return True, f"Аккаунт {me.first_name} успешно добавлен"
            
        except Exception as e:
            logger.error(f"Ошибка при завершении авторизации: {e}")
            return False, f"Ошибка: {str(e)}"
    
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
            
            logger.info(f"Аккаунт {session_name} успешно добавлен")
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
        
        # Удаляем файл сессии
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
            return f"{data.get('first_name', session_name)} (@{data.get('username', 'no_username')})"
        return session_name
    
    async def get_username_by_session(self, session_name: str) -> Optional[str]:
        """Получает username аккаунта"""
        if session_name in self.accounts:
            client = self.accounts[session_name]
            me = await client.get_me()
            return me.username or me.first_name
        return None

# Класс для прогрева аккаунтов
class WarmupManager:
    def __init__(self, account_manager: AccountManager, conversation_manager: ConversationManager):
        self.account_manager = account_manager
        self.conversation_manager = conversation_manager
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
            'message_count': 0
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
            # Получаем список сообщений для разговора
            conversation_chain = self.conversation_manager.get_conversation_chain(20)
            
            # Сначала добавляем все аккаунты в менеджер
            for account in accounts:
                await self.account_manager.add_account(account)
            
            for i, (question, answer) in enumerate(conversation_chain):
                if warmup_id not in self.warmup_tasks:
                    break
                
                # Определяем кто пишет (чередуем аккаунты)
                sender_idx = i % len(accounts)
                receiver_idx = (i + 1) % len(accounts)
                
                sender = accounts[sender_idx]
                receiver = accounts[receiver_idx]
                
                # Получаем клиента отправителя
                sender_client = self.account_manager.accounts.get(sender)
                if not sender_client:
                    continue
                
                # Получаем username получателя
                receiver_username = await self.account_manager.get_username_by_session(receiver)
                if not receiver_username:
                    continue
                
                try:
                    # Отправляем вопрос или ответ
                    message_text = question if i % 2 == 0 else answer
                    await sender_client.send_message(receiver_username, message_text)
                    
                    # Обновляем счетчик сообщений
                    self.account_manager.active_warmups[warmup_id]['message_count'] += 1
                    
                    # Логируем
                    logger.info(f"[{warmup_id}] {sender} -> {receiver}: {message_text[:50]}...")
                    
                    # Случайная задержка 5-10 секунд
                    delay = random.uniform(5, 10)
                    await asyncio.sleep(delay)
                    
                except FloodWait as e:
                    logger.warning(f"Flood wait: {e.value} секунд")
                    await asyncio.sleep(e.value)
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения: {e}")
                    continue
            
            # Завершаем прогрев
            if warmup_id in self.account_manager.active_warmups:
                self.account_manager.active_warmups[warmup_id]['status'] = 'completed'
            
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
conversation_manager = ConversationManager()
warmup_manager = WarmupManager(account_manager, conversation_manager)

# Хранение временных данных пользователей
user_data = {}

# Команда старт
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Добро пожаловать в бота для прогрева Telegram аккаунтов!\n\n"
        "📱 Доступные действия:\n"
        "• Отправьте .session файл для добавления аккаунта\n"
        "• Используйте /add_phone для добавления по номеру телефона\n"
        "• /accounts - Показать добавленные аккаунты\n"
        "• /warmup - Запустить прогрев аккаунтов\n"
        "• /stop - Остановить прогрев\n"
        "• /status - Статус текущего прогрева\n"
        "• /help - Помощь"
    )

# Команда помощи
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "📚 Как пользоваться ботом:\n\n"
        "🔹 **Добавление аккаунтов:**\n"
        "• Отправьте .session файл боту\n"
        "• Или используйте /add_phone для входа по номеру\n\n"
        "🔹 **Запуск прогрева:**\n"
        "1. Используйте /accounts чтобы увидеть доступные аккаунты\n"
        "2. Используйте /warmup для запуска прогрева\n"
        "3. Выберите минимум 2 аккаунта\n"
        "4. Аккаунты начнут переписываться друг с другом\n\n"
        "🔹 **Управление:**\n"
        "• /stop - остановить текущий прогрев\n"
        "• /status - проверить статус\n"
        "• /remove_account - удалить аккаунт\n\n"
        "⚡️ Особенности:\n"
        "• База из 100+ пар вопрос-ответ\n"
        "• Задержка между сообщениями 5-10 секунд\n"
        "• Возможность остановки в любой момент"
    )

# Команда добавления по номеру телефона
@app.on_message(filters.command("add_phone"))
async def add_phone_command(client: Client, message: Message):
    chat_id = message.chat.id
    
    # Проверяем, нет ли уже активной авторизации
    if chat_id in account_manager.pending_authorizations:
        await message.reply_text(
            "⚠️ У вас уже есть активная авторизация.\n"
            "Введите код подтверждения или /cancel для отмены."
        )
        return
    
    await message.reply_text(
        "📱 Введите номер телефона в международном формате:\n"
        "Например: +79001234567"
    )
    
    # Устанавливаем состояние ожидания номера
    user_data[chat_id] = {'state': 'waiting_phone'}

# Команда удаления аккаунта
@app.on_message(filters.command("remove_account"))
async def remove_account_command(client: Client, message: Message):
    available = account_manager.get_available_sessions()
    
    if not available:
        await message.reply_text("❌ Нет добавленных аккаунтов")
        return
    
    # Создаем клавиатуру для выбора аккаунта
    keyboard = []
    for session in available:
        display_name = account_manager.get_account_display_name(session)
        keyboard.append([InlineKeyboardButton(
            f"❌ {display_name}", 
            callback_data=f"remove_{session}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="cancel")])
    
    await message.reply_text(
        "Выберите аккаунт для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команда просмотра аккаунтов
@app.on_message(filters.command("accounts"))
async def accounts_command(client: Client, message: Message):
    available = account_manager.get_available_sessions()
    active = account_manager.get_active_accounts()
    
    if not available:
        await message.reply_text(
            "❌ Нет добавленных аккаунтов!\n"
            "Отправьте .session файл или используйте /add_phone"
        )
        return
    
    text = "📱 **Добавленные аккаунты:**\n\n"
    for session in available:
        status = "✅" if session in active else "❌"
        display_name = account_manager.get_account_display_name(session)
        source = account_manager.accounts_data.get(session, {}).get('source', 'session_file')
        source_text = "📁" if source == 'session_file' else "📱"
        text += f"{status} {source_text} {display_name}\n"
    
    await message.reply_text(text)

# Команда запуска прогрева
@app.on_message(filters.command("warmup"))
async def warmup_command(client: Client, message: Message):
    chat_id = message.chat.id
    
    # Проверяем доступные аккаунты
    available = account_manager.get_available_sessions()
    if len(available) < 2:
        await message.reply_text(
            "❌ Для прогрева нужно минимум 2 аккаунта!\n"
            f"Сейчас добавлено: {len(available)}\n"
            "Добавьте аккаунты через /add_phone или отправкой .session файла"
        )
        return
    
    # Добавляем аккаунты в менеджер
    added_accounts = []
    for session in available:
        if await account_manager.add_account(session):
            added_accounts.append(session)
    
    if len(added_accounts) < 2:
        await message.reply_text(
            "❌ Не удалось активировать минимум 2 аккаунта!\n"
            "Проверьте session файлы"
        )
        return
    
    # Создаем клавиатуру для выбора аккаунтов
    keyboard = []
    for i, session in enumerate(added_accounts):
        display_name = account_manager.get_account_display_name(session)
        callback_data = f"select_{session}"
        keyboard.append([InlineKeyboardButton(f"⬜ {display_name}", callback_data=callback_data)])
    
    # Добавляем кнопки управления
    keyboard.append([
        InlineKeyboardButton("✅ Начать прогрев", callback_data="start_warmup"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])
    
    await message.reply_text(
        "📝 **Выберите аккаунты для прогрева (минимум 2):**\n"
        "Нажимайте на аккаунты для выбора, затем 'Начать прогрев'",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Инициализируем данные пользователя
    user_data[chat_id] = {
        'selected_accounts': [],
        'message_id': message.id
    }

# Команда остановки прогрева
@app.on_message(filters.command("stop"))
async def stop_command(client: Client, message: Message):
    chat_id = message.chat.id
    await warmup_manager.stop_all_warmups_for_chat(chat_id)
    await message.reply_text("🛑 Прогрев остановлен")

# Команда статуса
@app.on_message(filters.command("status"))
async def status_command(client: Client, message: Message):
    chat_id = message.chat.id
    
    active = []
    for warmup_id, data in account_manager.active_warmups.items():
        if data.get('chat_id') == chat_id:
            active.append(data)
    
    if not active:
        await message.reply_text("📊 Нет активных прогревов")
        return
    
    text = "📊 **Статус прогрева:**\n\n"
    for data in active:
        accounts_text = "\n".join([f"  • {account_manager.get_account_display_name(a)}" for a in data['accounts']])
        text += f"**Аккаунты:**\n{accounts_text}\n"
        text += f"**Сообщений:** {data.get('message_count', 0)}\n"
        text += f"**Статус:** {data['status']}\n"
        text += f"**Начало:** {data['start_time'][:19]}\n\n"
    
    await message.reply_text(text)

# Обработка документов (session файлов)
@app.on_message(filters.document)
async def handle_document(client: Client, message: Message):
    chat_id = message.chat.id
    
    # Проверяем расширение файла
    if not message.document.file_name.endswith('.session'):
        await message.reply_text("❌ Пожалуйста, отправьте файл с расширением .session")
        return
    
    # Скачиваем файл
    file_path = await message.download(file_name=TEMP_DIR)
    
    # Добавляем аккаунт
    success, result_text = await account_manager.add_account_by_session_file(
        file_path, 
        message.document.file_name
    )
    
    # Удаляем временный файл
    if os.path.exists(file_path):
        os.remove(file_path)
    
    if success:
        await message.reply_text(f"✅ {result_text}")
    else:
        await message.reply_text(f"❌ {result_text}")

# Обработка текстовых сообщений (для ввода номера и кода)
@app.on_message(filters.text & ~filters.command(["start", "help", "add_phone", "accounts", "warmup", "stop", "status", "remove_account"]))
async def handle_text(client: Client, message: Message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Обработка ввода номера телефона
    if chat_id in user_data and user_data[chat_id].get('state') == 'waiting_phone':
        # Проверяем формат номера
        if not text.startswith('+') or not text[1:].isdigit():
            await message.reply_text("❌ Неверный формат. Введите номер в формате: +79001234567")
            return
        
        # Начинаем авторизацию
        success, result = await account_manager.start_phone_authorization(chat_id, text)
        
        if success:
            await message.reply_text(
                "✅ Код подтверждения отправлен!\n"
                "Введите код из SMS:"
            )
            user_data[chat_id]['state'] = 'waiting_code'
        else:
            await message.reply_text(f"❌ {result}")
            del user_data[chat_id]
        
        return
    
    # Обработка ввода кода подтверждения
    if chat_id in account_manager.pending_authorizations:
        auth_data = account_manager.pending_authorizations[chat_id]
        
        if auth_data.get('step') == 'waiting_code':
            # Проверяем, что введен код (только цифры)
            if not text.isdigit():
                await message.reply_text("❌ Код должен содержать только цифры")
                return
            
            # Завершаем авторизацию
            success, result = await account_manager.complete_phone_authorization(chat_id, text)
            
            if result == "password_needed":
                await message.reply_text(
                    "🔐 Требуется двухфакторная аутентификация.\n"
                    "Введите ваш пароль:"
                )
                auth_data['step'] = 'waiting_password'
            elif success:
                await message.reply_text(f"✅ {result}")
                if chat_id in user_data:
                    del user_data[chat_id]
            else:
                await message.reply_text(f"❌ {result}")
                if chat_id in account_manager.pending_authorizations:
                    del account_manager.pending_authorizations[chat_id]
                if chat_id in user_data:
                    del user_data[chat_id]
        
        elif auth_data.get('step') == 'waiting_password':
            # Завершаем авторизацию с паролем
            success, result = await account_manager.complete_phone_authorization(chat_id, code=None, password=text)
            
            if success:
                await message.reply_text(f"✅ {result}")
            else:
                await message.reply_text(f"❌ {result}")
            
            # Очищаем данные
            if chat_id in account_manager.pending_authorizations:
                del account_manager.pending_authorizations[chat_id]
            if chat_id in user_data:
                del user_data[chat_id]

# Обработка callback запросов
@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    
    if data == "cancel":
        await callback_query.message.delete()
        await callback_query.answer("Отменено")
        return
    
    if data.startswith("remove_"):
        session = data.replace("remove_", "")
        await account_manager.remove_account(session)
        await callback_query.answer(f"Аккаунт удален")
        await callback_query.message.delete()
        await callback_query.message.reply_text(f"✅ Аккаунт удален")
        return
    
    if data.startswith("select_"):
        session = data.replace("select_", "")
        
        if chat_id not in user_data:
            user_data[chat_id] = {'selected_accounts': []}
        
        selected = user_data[chat_id]['selected_accounts']
        
        if session in selected:
            selected.remove(session)
            await callback_query.answer(f"Аккаунт убран из выбора")
        else:
            selected.append(session)
            await callback_query.answer(f"Аккаунт добавлен в выбор")
        
        # Обновляем сообщение
        available = account_manager.get_available_sessions()
        text = "📝 **Выберите аккаунты для прогрева (минимум 2):**\n"
        text += f"Выбрано: {len(selected)} из {len(available)}\n\n"
        
        # Создаем клавиатуру заново с обновленными статусами
        keyboard = []
        for s in available:
            display_name = account_manager.get_account_display_name(s)
            status = "✅" if s in selected else "⬜"
            keyboard.append([InlineKeyboardButton(
                f"{status} {display_name}", 
                callback_data=f"select_{s}"
            )])
        
        keyboard.append([
            InlineKeyboardButton("✅ Начать прогрев", callback_data="start_warmup"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ])
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "start_warmup":
        if chat_id not in user_data or len(user_data[chat_id]['selected_accounts']) < 2:
            await callback_query.answer("❌ Выберите минимум 2 аккаунта!", show_alert=True)
            return
        
        selected = user_data[chat_id]['selected_accounts']
        
        # Запускаем прогрев
        warmup_id = await warmup_manager.start_warmup(chat_id, selected)
        
        await callback_query.message.delete()
        await callback_query.message.reply_text(
            f"🚀 **Прогрев запущен!**\n\n"
            f"**Аккаунты:** {len(selected)}\n"
            f"**ID прогрева:** `{warmup_id}`\n\n"
            f"Используйте /stop для остановки\n"
            f"/status для просмотра статуса"
        )
        
        await callback_query.answer("Прогрев запущен!")

# Запуск бота
if __name__ == "__main__":
    print("🚀 Бот запущен...")
    print(f"API ID: {API_ID}")
    print(f"Папка sessions: {SESSIONS_DIR}")
    print(f"Папка temp: {TEMP_DIR}")
    print("\nДоступные команды:")
    print("• Отправьте .session файл для добавления аккаунта")
    print("• /add_phone - добавить по номеру телефона")
    print("• /accounts - список аккаунтов")
    print("• /warmup - запустить прогрев")
    print("• /stop - остановить прогрев")
    print("• /status - статус прогрева")
    app.run()

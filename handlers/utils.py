# -*- coding: utf-8 -*-
"""
Допоміжний модуль (утиліти).

Містить різноманітні інструменти, що використовуються в різних частинах коду:
- Декоратори для перевірки прав доступу.
- Функції для роботи з повідомленнями (напр., планування видалення).
- Інші допоміжні функції (напр., отримання факту).
"""

import logging
import random
from httpx import AsyncClient, RequestError
from json import JSONDecodeError
from telegram import Message, Update
from telegram.ext import ContextTypes
from functools import wraps
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

# A simple list of facts
facts = [
    "Перший комп'ютерний програміст - жінка, Ада Лавлейс.",
    "Python був названий на честь комедійної групи 'Monty Python'.",
    "Перший комп'ютерний вірус був створений у 1983 році.",
    "Щодня створюється близько 5000 нових комп'ютерних вірусів.",
    "Перший гігабайтний жорсткий диск важив понад 250 кг.",
    "Всесвітня павутина (WWW) та Інтернет - це не одне й те саме.",
    "Людське око могло б бути цифровою камерою на 576 мегапікселів.",
    "В середньому, людина моргає 20 разів на хвилину.",
    "Близько 70% нашого тіла складається з води.",
    "Найвища гора в Сонячній системі - Олімп на Марсі."
]

def get_fact() -> str:
    """Returns a random fact from the list."""
    return random.choice(facts)

def admin_only(func):
    """
    Декоратор для обмеження доступу до команди тільки для адміністраторів.
    
    Перевіряє `user_id` користувача, що викликав команду. Якщо ID немає у списку
    `ADMIN_IDS` з конфігурації, команда не виконується, а користувач отримує
    попередження.
    """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            logger.warning(f"Відмова у несанкціонованому доступі для {user_id}.")
            message = await update.message.reply_text("⚠️ Ця команда доступна лише адміністратору бота.")
            # Повідомлення про відмову автоматично видаляється через 30 секунд
            schedule_message_deletion(message, context, 30)
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

async def delete_message_callback(context: ContextTypes.DEFAULT_TYPE):
    """
    Callback-функція, що виконується `JobQueue` для видалення повідомлення.
    
    Отримує `chat_id` та `message_id` із даних завдання (`context.job.data`)
    і намагається видалити відповідне повідомлення.
    """
    try:
        chat_id = context.job.data["chat_id"]
        message_id = context.job.data["message_id"]
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Успішно видалено повідомлення {message_id} в чаті {chat_id}")
    except Exception as e:
        logger.warning(f"Не вдалося видалити повідомлення {context.job.data.get('message_id')} в чаті {context.job.data.get('chat_id')}: {e}")

def schedule_message_deletion(message: Message, context: ContextTypes.DEFAULT_TYPE, delay_seconds: int = 20 * 60):
    """
    Планує видалення повідомлення через вказаний проміжок часу.
    
    Створює унікальне завдання в `JobQueue` для кожного повідомлення.
    Якщо для повідомлення вже існує завдання (напр., після редагування),
    старе завдання видаляється, щоб уникнути конфліктів.
    Це дозволяє тримати чат чистим від тимчасових повідомлень.
    
    Args:
        message: Об'єкт повідомлення, яке потрібно видалити.
        context: Контекст обробника.
        delay_seconds: Затримка в секундах до видалення.
    """
    if message and context.job_queue:
        job_name = f"delete_{message.chat_id}_{message.message_id}"
        # Видалення старих завдань з тим самим іменем для уникнення дублювання
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
            
        context.job_queue.run_once(
            delete_message_callback,
            delay_seconds,
            data={"chat_id": message.chat_id, "message_id": message.message_id},
            name=job_name
        )

async def get_fact() -> str:
    """
    Асинхронно отримує випадковий факт з зовнішнього API.
    
    Використовує httpx для асинхронних HTTP-запитів.
    Має обробку помилок на випадок недоступності сервісу.
    """
    try:
        async with AsyncClient() as client:
            # Запит до API для отримання факту українською мовою
            response = await client.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=uk")
            response.raise_for_status() # Викине виняток для кодів 4xx/5xx
            fact = response.json().get("text", "Не вдалося отримати факт. 😥")
    except (RequestError, JSONDecodeError) as e:
        logger.error(f"Помилка при отриманні факту: {e}")
        fact = "Виникла помилка при отриманні факту."
    return fact 
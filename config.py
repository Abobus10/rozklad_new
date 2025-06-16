"""
Модуль конфігурації додатка.

Використовує Pydantic Settings для валідації та керування конфігурацією.
Підтримує завантаження зі змінних середовища та .env файлів.
"""

import os
from typing import Dict, List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Конфігурація додатка з валідацією."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Основні налаштування бота
    telegram_token: str = Field(
        description="Токен Telegram-бота",
        min_length=1
    )
    
    admin_ids: Union[str, List[int], int] = Field(
        default=[6051391474],
        description="Список ID адміністраторів"
    )
    
    # Налаштування часу та локалізації
    timezone: str = Field(
        default="Europe/Kiev",
        description="Часовий пояс"
    )
    
    # Файли даних
    users_file: str = Field(
        default="users.json",
        description="Файл даних користувачів"
    )
    
    schedule_file: str = Field(
        default="schedule.json", 
        description="Файл розкладу"
    )
    
    group_chats_file: str = Field(
        default="group_chats.json",
        description="Файл даних групових чатів"
    )
    
    # Налаштування сповіщень
    daily_reminder_time: str = Field(
        default="08:00",
        pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        description="Час щоденних нагадувань"
    )
    
    morning_schedule_time: str = Field(
        default="07:00",
        pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        description="Час ранкової розсилки розкладу"
    )
    
    # Налаштування логування
    log_level: str = Field(
        default="INFO",
        description="Рівень логування"
    )
    
    log_file: str = Field(
        default="bot.log",
        description="Файл логів"
    )
    
    # Налаштування продуктивності
    max_concurrent_notifications: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Максимальна кількість одночасних сповіщень"
    )
    
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Таймаут запитів у секундах"
    )
    
    @field_validator('admin_ids')
    @classmethod  
    def validate_admin_ids(cls, v) -> List[int]:
        """Валідація списку ID адміністраторів."""
        if isinstance(v, str):
            # Обробка рядка зі змінних середовища (формат: "123,456,789")
            try:
                result = [int(admin_id.strip()) for admin_id in v.split(',') if admin_id.strip()]
            except ValueError:
                raise ValueError("Неправильний формат ADMIN_IDS у змінних середовища")
        elif isinstance(v, list):
            # Вже список
            result = [admin_id for admin_id in v if admin_id > 0]
        elif isinstance(v, int):
            # Обробка одного числа
            result = [v]
        else:
            raise ValueError("ADMIN_IDS має бути рядком, списком або числом")
        
        if not result:
            raise ValueError("Має бути вказаний хоча б один адміністратор")
        return result
    
    @field_validator('telegram_token')
    @classmethod
    def validate_telegram_token(cls, v: str) -> str:
        """Валідація токена Telegram."""
        if not v:
            raise ValueError("Токен Telegram не може бути порожнім")
        # Базова перевірка формату токена
        if not (len(v) > 40 and ':' in v):
            raise ValueError("Неправильний формат токена Telegram")
        return v


# Створюємо екземпляр конфігурації
try:
    config = AppConfig()
except Exception as e:
    print(f"Помилка завантаження конфігурації: {e}")
    raise


# Константи для зворотної сумісності
TELEGRAM_TOKEN = config.telegram_token
ADMIN_IDS = config.admin_ids
KYIV_TZ = config.timezone
TIMEZONE = config.timezone

# Файли даних
USERS_FILE = config.users_file
SCHEDULE_FILE = config.schedule_file
GROUP_CHATS_FILE = config.group_chats_file

# Час сповіщень
DAILY_REMINDER_TIME = config.daily_reminder_time

# Словник днів тижня українською
DAYS_UA: Dict[int, str] = {
    0: "понеділок", 
    1: "вівторок", 
    2: "середа", 
    3: "четвер", 
    4: "п'ятниця", 
    5: "субота", 
    6: "неділя"
}

# Розклад дзвінків
LESSON_TIMES: Dict[int, tuple[str, str]] = {
    1: ("08:00", "09:20"), 
    2: ("09:30", "10:50"), 
    3: ("11:10", "12:30"),
    4: ("12:40", "14:00"), 
    5: ("14:10", "15:30"), 
    6: ("15:40", "17:00"),
    7: ("17:10", "18:30"), 
    8: ("18:40", "20:00")
}


def get_lesson_time_display(pair_number: int) -> str:
    """
    Повертає форматований час пари.
    
    Args:
        pair_number: Номер пари (1-8)
        
    Returns:
        Рядок з часом пари або "??:??" якщо пара не знайдена
    """
    time_range = LESSON_TIMES.get(pair_number, ("??:??", "??:??"))
    return f"{time_range[0]} - {time_range[1]}"


def is_valid_day(day: str) -> bool:
    """
    Перевіряє, чи є день валідним.
    
    Args:
        day: Назва дня
        
    Returns:
        True, якщо день валідний
    """
    return day in DAYS_UA.values()


def get_day_number(day: str) -> int:
    """
    Повертає номер дня тижня за назвою.
    
    Args:
        day: Назва дня українською
        
    Returns:
        Номер дня (0-6) або -1, якщо день не знайдено
    """
    for number, name in DAYS_UA.items():
        if name == day:
            return number
    return -1


# Функція для перевірки, чи є користувач адміністратором
def is_admin(user_id: int) -> bool:
    """
    Перевіряє, чи є користувач адміністратором.
    
    Args:
        user_id: ID користувача
        
    Returns:
        True, якщо користувач є адміністратором
    """
    return user_id in ADMIN_IDS


# Експорт основних налаштувань для зручності
__all__ = [
    'config',
    'TELEGRAM_TOKEN',
    'ADMIN_IDS', 
    'KYIV_TZ',
    'TIMEZONE',
    'USERS_FILE',
    'SCHEDULE_FILE',
    'GROUP_CHATS_FILE',
    'DAILY_REMINDER_TIME',
    'DAYS_UA',
    'LESSON_TIMES',
    'get_lesson_time_display',
    'is_valid_day',
    'get_day_number',
    'is_admin'
]
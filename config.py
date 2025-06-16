"""
Модуль конфигурации приложения.

Использует Pydantic Settings для валидации и управления конфигурацией.
Поддерживает загрузку из переменных окружения и .env файлов.
"""

import os
from typing import Dict, List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Конфигурация приложения с валидацией."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Основные настройки бота
    telegram_token: str = Field(
        description="Токен Telegram бота",
        min_length=1
    )
    
    admin_ids: Union[str, List[int]] = Field(
        default=[6051391474],
        description="Список ID администраторов"
    )
    
    # Настройки времени и локализации
    timezone: str = Field(
        default="Europe/Kiev",
        description="Часовая зона"
    )
    
    # Файлы данных
    users_file: str = Field(
        default="users.json",
        description="Файл данных пользователей"
    )
    
    schedule_file: str = Field(
        default="schedule.json", 
        description="Файл расписания"
    )
    
    group_chats_file: str = Field(
        default="group_chats.json",
        description="Файл данных групповых чатов"
    )
    
    # Настройки уведомлений
    daily_reminder_time: str = Field(
        default="08:00",
        pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        description="Время ежедневных напоминаний"
    )
    
    morning_schedule_time: str = Field(
        default="07:00",
        pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        description="Время утренней рассылки расписания"
    )
    
    # Настройки логирования
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования"
    )
    
    log_file: str = Field(
        default="bot.log",
        description="Файл логов"
    )
    
    # Настройки производительности
    max_concurrent_notifications: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Максимальное количество одновременных уведомлений"
    )
    
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Таймаут запросов в секундах"
    )
    
    @field_validator('admin_ids')
    @classmethod  
    def validate_admin_ids(cls, v) -> List[int]:
        """Валидация списка ID администраторов."""
        if isinstance(v, str):
            # Обработка строки из переменных окружения (формат: "123,456,789")
            try:
                result = [int(admin_id.strip()) for admin_id in v.split(',') if admin_id.strip()]
            except ValueError:
                raise ValueError("Неверный формат ADMIN_IDS в переменных окружения")
        elif isinstance(v, list):
            # Уже список
            result = [admin_id for admin_id in v if admin_id > 0]
        else:
            raise ValueError("ADMIN_IDS должен быть строкой или списком")
        
        if not result:
            raise ValueError("Должен быть указан хотя бы один администратор")
        return result
    
    @field_validator('telegram_token')
    @classmethod
    def validate_telegram_token(cls, v: str) -> str:
        """Валидация токена Telegram."""
        if not v:
            raise ValueError("Токен Telegram не может быть пустым")
        # Базовая проверка формата токена
        if not (len(v) > 40 and ':' in v):
            raise ValueError("Неверный формат токена Telegram")
        return v


# Создаем экземпляр конфигурации
try:
    config = AppConfig()
except Exception as e:
    print(f"Ошибка загрузки конфигурации: {e}")
    raise


# Константы для обратной совместимости
TELEGRAM_TOKEN = config.telegram_token
ADMIN_IDS = config.admin_ids
KYIV_TZ = config.timezone
TIMEZONE = config.timezone

# Файлы данных
USERS_FILE = config.users_file
SCHEDULE_FILE = config.schedule_file
GROUP_CHATS_FILE = config.group_chats_file

# Время уведомлений
DAILY_REMINDER_TIME = config.daily_reminder_time

# Словарь дней недели на украинском
DAYS_UA: Dict[int, str] = {
    0: "понеділок", 
    1: "вівторок", 
    2: "середа", 
    3: "четвер", 
    4: "п'ятниця", 
    5: "субота", 
    6: "неділя"
}

# Расписание звонков
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
    Возвращает форматированное время пары.
    
    Args:
        pair_number: Номер пары (1-8)
        
    Returns:
        Строка с временем пары или "??:??" если пара не найдена
    """
    time_range = LESSON_TIMES.get(pair_number, ("??:??", "??:??"))
    return f"{time_range[0]} - {time_range[1]}"


def is_valid_day(day: str) -> bool:
    """
    Проверяет, является ли день валидным.
    
    Args:
        day: Название дня
        
    Returns:
        True если день валидный
    """
    return day in DAYS_UA.values()


def get_day_number(day: str) -> int:
    """
    Возвращает номер дня недели по названию.
    
    Args:
        day: Название дня на украинском
        
    Returns:
        Номер дня (0-6) или -1 если день не найден
    """
    for number, name in DAYS_UA.items():
        if name == day:
            return number
    return -1


# Функция для проверки, является ли пользователь администратором
def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True если пользователь администратор
    """
    return user_id in ADMIN_IDS


# Экспорт основных настроек для удобства
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
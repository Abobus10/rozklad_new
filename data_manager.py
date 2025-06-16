# -*- coding: utf-8 -*-
"""
Модуль для управления данными бота.

Использует Pydantic модели для типизации и валидации данных.
Предоставляет thread-safe операции с файлами и кешированием данных.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from pydantic import ValidationError

from config import USERS_FILE, SCHEDULE_FILE, GROUP_CHATS_FILE
from models import (
    UserModel, 
    ScheduleDataModel, 
    GroupChatModel, 
    GroupScheduleModel,
    LessonModel
)

logger = logging.getLogger(__name__)

# Thread-safe locks для операций с файлами
_file_locks = {
    'users': Lock(),
    'schedule': Lock(),
    'group_chats': Lock()
}


class DataManager:
    """Класс для управления данными бота с типизацией и валидацией."""
    
    def __init__(self):
        """Инициализация менеджера данных."""
        self._users_data: Dict[str, UserModel] = {}
        self._schedule_data: Optional[ScheduleDataModel] = None
        self._group_chats_data: Dict[str, GroupChatModel] = {}
        self._schedule_start_date: Optional[datetime] = None
        
        self._load_all_data()
    
    def _load_json_file(self, filepath: str, default_data=None) -> dict:
        """
        Загружает JSON файл с обработкой ошибок.
        
        Args:
            filepath: Путь к файлу
            default_data: Данные по умолчанию при ошибке
            
        Returns:
            Загруженные данные или данные по умолчанию
        """
        file_path = Path(filepath)
        
        if not file_path.exists():
            logger.warning(f"Файл {filepath} не найден. Создаю с данными по умолчанию.")
            return default_data or {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в файле {filepath}: {e}")
            # Создаем резервную копию поврежденного файла
            backup_path = file_path.with_suffix(f'.backup_{int(datetime.now().timestamp())}')
            file_path.rename(backup_path)
            logger.info(f"Создана резервная копия: {backup_path}")
            return default_data or {}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при чтении {filepath}: {e}")
            return default_data or {}
    
    def _save_json_file(self, filepath: str, data: dict) -> bool:
        """
        Сохраняет данные в JSON файл с обработкой ошибок.
        
        Args:
            filepath: Путь к файлу
            data: Данные для сохранения
            
        Returns:
            True если сохранение успешно, False в противном случае
        """
        try:
            file_path = Path(filepath)
            # Создаем директорию если не существует
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сначала сохраняем во временный файл
            temp_path = file_path.with_suffix('.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Если сохранение успешно, заменяем основной файл
            temp_path.replace(file_path)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения {filepath}: {e}")
            return False
    
    def _load_all_data(self) -> None:
        """Загружает все данные при инициализации."""
        self._load_users_data()
        self._load_schedule_data()
        self._load_group_chats_data()
    
    def _load_users_data(self) -> None:
        """Загружает данные пользователей с валидацией."""
        with _file_locks['users']:
            raw_data = self._load_json_file(USERS_FILE, {})
            
            self._users_data = {}
            for user_id, user_data in raw_data.items():
                try:
                    self._users_data[user_id] = UserModel.model_validate(user_data)
                except ValidationError as e:
                    logger.warning(f"Невалидные данные пользователя {user_id}: {e}")
                    # Используем модель по умолчанию для невалидных данных
                    self._users_data[user_id] = UserModel()
    
    def _load_schedule_data(self) -> None:
        """Загружает данные расписания с валидацией."""
        with _file_locks['schedule']:
            raw_data = self._load_json_file(SCHEDULE_FILE, {"groups": {}})
            
            try:
                self._schedule_data = ScheduleDataModel.model_validate(raw_data)
                
                # Устанавливаем дату начала семестра
                if self._schedule_data.startDate:
                    self._schedule_start_date = datetime.strptime(
                        self._schedule_data.startDate, "%Y-%m-%d"
                    )
                    
            except ValidationError as e:
                logger.error(f"Ошибка валидации данных расписания: {e}")
                self._schedule_data = ScheduleDataModel()
    
    def _load_group_chats_data(self) -> None:
        """Загружает данные групповых чатов с валидацией."""
        with _file_locks['group_chats']:
            raw_data = self._load_json_file(GROUP_CHATS_FILE, {})
            
            self._group_chats_data = {}
            for chat_id, chat_data in raw_data.items():
                try:
                    self._group_chats_data[chat_id] = GroupChatModel.model_validate(chat_data)
                except ValidationError as e:
                    logger.warning(f"Невалидные данные чата {chat_id}: {e}")
                    self._group_chats_data[chat_id] = GroupChatModel()
    
    # Методы для работы с пользователями
    def get_user(self, user_id: str) -> Optional[UserModel]:
        """
        Получает модель пользователя по ID.
        
        Returns:
            UserModel если пользователь найден, иначе None.
        """
        return self._users_data.get(user_id)
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """
        Обновляет данные пользователя.
        
        Args:
            user_id: ID пользователя
            **kwargs: Поля для обновления
            
        Returns:
            True если обновление успешно
        """
        try:
            current_user = self.get_user(user_id)
            # Если пользователя нет, создаем новую модель
            if current_user is None:
                current_user = UserModel()
            
            updated_data = current_user.model_dump()
            updated_data.update(kwargs)
            updated_data['last_activity'] = datetime.now()
            
            self._users_data[user_id] = UserModel.model_validate(updated_data)
            return self.save_users_data()
            
        except ValidationError as e:
            logger.error(f"Ошибка валидации при обновлении пользователя {user_id}: {e}")
            return False
    
    def save_users_data(self) -> bool:
        """Сохраняет данные пользователей."""
        with _file_locks['users']:
            data = {
                user_id: user.model_dump(mode='json') 
                for user_id, user in self._users_data.items()
            }
            return self._save_json_file(USERS_FILE, data)
    
    # Методы для работы с расписанием
    @property
    def schedule_data(self) -> ScheduleDataModel:
        """Возвращает данные расписания."""
        return self._schedule_data or ScheduleDataModel()
    
    @property
    def schedule_start_date(self) -> Optional[datetime]:
        """Возвращает дату начала семестра."""
        return self._schedule_start_date
    
    def get_group_schedule(self, group: str) -> Optional[GroupScheduleModel]:
        """Получает расписание группы."""
        return self._schedule_data.groups.get(group) if self._schedule_data else None
    
    def get_day_lessons(self, group: str, day: str) -> list[LessonModel]:
        """Получает список пар для группы и дня."""
        group_schedule = self.get_group_schedule(group)
        if not group_schedule:
            return []
        
        return group_schedule.schedule.get(day, [])
    
    # Методы для работы с групповыми чатами
    def get_group_chat(self, chat_id: str) -> GroupChatModel:
        """Получает модель группового чата."""
        return self._group_chats_data.get(chat_id, GroupChatModel())
    
    def update_group_chat(self, chat_id: str, **kwargs) -> bool:
        """Обновляет данные группового чата."""
        try:
            current_chat = self.get_group_chat(chat_id)
            updated_data = current_chat.model_dump()
            updated_data.update(kwargs)
            
            self._group_chats_data[chat_id] = GroupChatModel.model_validate(updated_data)
            return self.save_group_chats_data()
            
        except ValidationError as e:
            logger.error(f"Ошибка валидации при обновлении чата {chat_id}: {e}")
            return False
    
    def save_group_chats_data(self) -> bool:
        """Сохраняет данные групповых чатов."""
        with _file_locks['group_chats']:
            data = {
                chat_id: chat.model_dump(mode='json') 
                for chat_id, chat in self._group_chats_data.items()
            }
            return self._save_json_file(GROUP_CHATS_FILE, data)
    
    def get_all_users_data(self) -> Dict[str, dict]:
        """Возвращает все данные пользователей в виде словаря."""
        return {
            user_id: user.model_dump() 
            for user_id, user in self._users_data.items()
        }
    
    def get_all_group_chats(self) -> Dict[str, dict]:
        """Возвращает все данные групповых чатов в виде словаря."""
        return {
            chat_id: chat.model_dump() 
            for chat_id, chat in self._group_chats_data.items()
        }
    
    # Статистические методы
    def get_users_count(self) -> int:
        """Возвращает количество пользователей."""
        return len(self._users_data)
    
    def get_active_users_today(self) -> int:
        """Возвращает количество активных пользователей сегодня."""
        today = datetime.now().date()
        return sum(
            1 for user in self._users_data.values()
            if user.last_activity and user.last_activity.date() == today
        )
    
    def get_groups_count(self) -> int:
        """Возвращает количество групп в расписании."""
        return len(self._schedule_data.groups) if self._schedule_data else 0


# Создаем глобальный экземпляр менеджера данных
data_manager = DataManager()

# Обратная совместимость - экспорт старых переменных
users_data = data_manager._users_data
schedule_data = data_manager.schedule_data
group_chats_data = data_manager._group_chats_data
schedule_start_date = data_manager.schedule_start_date

# Экспорт старых функций для обратной совместимости
def save_users_data():
    """Сохраняет данные пользователей (для обратной совместимости)."""
    return data_manager.save_users_data()

def save_group_chat_data():
    """Сохраняет данные групповых чатов (для обратной совместимости)."""
    return data_manager.save_group_chats_data() 
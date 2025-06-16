# -*- coding: utf-8 -*-
"""
Модуль для керування даними бота.

Використовує Pydantic моделі для типізації та валідації даних.
Надає thread-safe операції з файлами та кешуванням даних.
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

# Thread-safe замки для операцій з файлами
_file_locks = {
    'users': Lock(),
    'schedule': Lock(),
    'group_chats': Lock()
}


class DataManager:
    """Клас для керування даними бота з типізацією та валідацією."""
    
    def __init__(self):
        """Ініціалізація менеджера даних."""
        self._users_data: Dict[str, UserModel] = {}
        self._schedule_data: Optional[ScheduleDataModel] = None
        self._group_chats_data: Dict[str, GroupChatModel] = {}
        self._schedule_start_date: Optional[datetime] = None
        
        self._load_all_data()
    
    def _load_json_file(self, filepath: str, default_data=None) -> dict:
        """
        Завантажує JSON файл з обробкою помилок.
        
        Args:
            filepath: Шлях до файлу
            default_data: Дані за замовчуванням у разі помилки
            
        Returns:
            Завантажені дані або дані за замовчуванням
        """
        file_path = Path(filepath)
        
        if not file_path.exists():
            logger.warning(f"Файл {filepath} не знайдено. Створюю з даними за замовчуванням.")
            return default_data or {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Помилка парсингу JSON у файлі {filepath}: {e}")
            # Створюємо резервну копію пошкодженого файлу
            backup_path = file_path.with_suffix(f'.backup_{int(datetime.now().timestamp())}')
            file_path.rename(backup_path)
            logger.info(f"Створено резервну копію: {backup_path}")
            return default_data or {}
        except Exception as e:
            logger.error(f"Неочікувана помилка при читанні {filepath}: {e}")
            return default_data or {}
    
    def _save_json_file(self, filepath: str, data: dict) -> bool:
        """
        Зберігає дані в JSON файл з обробкою помилок.
        
        Args:
            filepath: Шлях до файлу
            data: Дані для збереження
            
        Returns:
            True, якщо збереження успішне, False в іншому випадку
        """
        try:
            file_path = Path(filepath)
            # Створюємо директорію, якщо не існує
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Спочатку зберігаємо у тимчасовий файл
            temp_path = file_path.with_suffix('.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Якщо збереження успішне, замінюємо основний файл
            temp_path.replace(file_path)
            return True
            
        except Exception as e:
            logger.error(f"Помилка збереження {filepath}: {e}")
            return False
    
    def _load_all_data(self) -> None:
        """Завантажує всі дані при ініціалізації."""
        self._load_users_data()
        self._load_schedule_data()
        self._load_group_chats_data()
    
    def _load_users_data(self) -> None:
        """Завантажує дані користувачів з валідацією."""
        with _file_locks['users']:
            raw_data = self._load_json_file(USERS_FILE, {})
            
            self._users_data = {}
            for user_id, user_data in raw_data.items():
                try:
                    self._users_data[user_id] = UserModel.model_validate(user_data)
                except ValidationError as e:
                    logger.warning(f"Невалідні дані користувача {user_id}: {e}")
                    # Використовуємо модель за замовчуванням для невалідних даних
                    self._users_data[user_id] = UserModel()
    
    def _load_schedule_data(self) -> None:
        """Завантажує дані розкладу з валідацією."""
        with _file_locks['schedule']:
            raw_data = self._load_json_file(SCHEDULE_FILE, {"groups": {}})
            
            try:
                self._schedule_data = ScheduleDataModel.model_validate(raw_data)
                
                # Встановлюємо дату початку семестру
                if self._schedule_data.startDate:
                    self._schedule_start_date = datetime.strptime(
                        self._schedule_data.startDate, "%Y-%m-%d"
                    )
                    
            except ValidationError as e:
                logger.error(f"Помилка валідації даних розкладу: {e}")
                self._schedule_data = ScheduleDataModel()
    
    def _load_group_chats_data(self) -> None:
        """Завантажує дані групових чатів з валідацією."""
        with _file_locks['group_chats']:
            raw_data = self._load_json_file(GROUP_CHATS_FILE, {})
            
            self._group_chats_data = {}
            for chat_id, chat_data in raw_data.items():
                try:
                    self._group_chats_data[chat_id] = GroupChatModel.model_validate(chat_data)
                except ValidationError as e:
                    logger.warning(f"Невалідні дані чату {chat_id}: {e}")
                    self._group_chats_data[chat_id] = GroupChatModel()
    
    # Методи для роботи з користувачами
    def get_user(self, user_id: str) -> Optional[UserModel]:
        """
        Отримує модель користувача за ID.
        
        Returns:
            UserModel, якщо користувач знайдений, інакше None.
        """
        return self._users_data.get(user_id)
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """
        Оновлює дані користувача.
        
        Args:
            user_id: ID користувача
            **kwargs: Поля для оновлення
            
        Returns:
            True, якщо оновлення успішне
        """
        try:
            current_user = self.get_user(user_id)
            # Якщо користувача немає, створюємо нову модель
            if current_user is None:
                current_user = UserModel()
            
            updated_data = current_user.model_dump()
            updated_data.update(kwargs)
            updated_data['last_activity'] = datetime.now()
            
            self._users_data[user_id] = UserModel.model_validate(updated_data)
            return self.save_users_data()
            
        except ValidationError as e:
            logger.error(f"Помилка валідації при оновленні користувача {user_id}: {e}")
            return False
    
    def save_users_data(self) -> bool:
        """Зберігає дані користувачів."""
        with _file_locks['users']:
            data = {
                user_id: user.model_dump(mode='json') 
                for user_id, user in self._users_data.items()
            }
            return self._save_json_file(USERS_FILE, data)
    
    # Методи для роботи з розкладом
    @property
    def schedule_data(self) -> ScheduleDataModel:
        """Повертає дані розкладу."""
        return self._schedule_data or ScheduleDataModel()
    
    @property
    def schedule_start_date(self) -> Optional[datetime]:
        """Повертає дату початку семестру."""
        return self._schedule_start_date
    
    def get_group_schedule(self, group: str) -> Optional[GroupScheduleModel]:
        """Отримує розклад групи."""
        return self._schedule_data.groups.get(group) if self._schedule_data else None
    
    def get_day_lessons(self, group: str, day: str) -> list[LessonModel]:
        """Отримує список пар для групи та дня."""
        group_schedule = self.get_group_schedule(group)
        if not group_schedule:
            return []
        
        return group_schedule.schedule.get(day, [])
    
    # Методи для роботи з груповими чатами
    def get_group_chat(self, chat_id: str) -> GroupChatModel:
        """Отримує модель групового чату."""
        return self._group_chats_data.get(chat_id, GroupChatModel())
    
    def update_group_chat(self, chat_id: str, **kwargs) -> bool:
        """Оновлює дані групового чату."""
        try:
            current_chat = self.get_group_chat(chat_id)
            updated_data = current_chat.model_dump()
            updated_data.update(kwargs)
            
            self._group_chats_data[chat_id] = GroupChatModel.model_validate(updated_data)
            return self.save_group_chats_data()
            
        except ValidationError as e:
            logger.error(f"Помилка валідації при оновленні чату {chat_id}: {e}")
            return False
    
    def save_group_chats_data(self) -> bool:
        """Зберігає дані групових чатів."""
        with _file_locks['group_chats']:
            data = {
                chat_id: chat.model_dump(mode='json') 
                for chat_id, chat in self._group_chats_data.items()
            }
            return self._save_json_file(GROUP_CHATS_FILE, data)
    
    def get_all_users_data(self) -> Dict[str, dict]:
        """Повертає всі дані користувачів у вигляді словника."""
        return {
            user_id: user.model_dump() 
            for user_id, user in self._users_data.items()
        }
    
    def get_all_group_chats(self) -> Dict[str, dict]:
        """Повертає всі дані групових чатів у вигляді словника."""
        return {
            chat_id: chat.model_dump() 
            for chat_id, chat in self._group_chats_data.items()
        }
    
    # Статистичні методи
    def get_users_count(self) -> int:
        """Повертає кількість користувачів."""
        return len(self._users_data)
    
    def get_active_users_today(self) -> int:
        """Повертає кількість активних користувачів сьогодні."""
        today = datetime.now().date()
        return sum(
            1 for user in self._users_data.values()
            if user.last_activity and user.last_activity.date() == today
        )
    
    def get_groups_count(self) -> int:
        """Повертає кількість груп у розкладі."""
        return len(self._schedule_data.groups) if self._schedule_data else 0


# Створюємо глобальний екземпляр менеджера даних
data_manager = DataManager()

# Обернена сумісність - експорт старих змінних
users_data = data_manager._users_data
schedule_data = data_manager.schedule_data
group_chats_data = data_manager._group_chats_data
schedule_start_date = data_manager.schedule_start_date

# Експорт старих функцій для оберненої сумісності
def save_users_data():
    """Зберігає дані користувачів (для оберненої сумісності)."""
    return data_manager.save_users_data()

def save_group_chat_data():
    """Зберігає дані групових чатів (для оберненої сумісності)."""
    return data_manager.save_group_chats_data() 
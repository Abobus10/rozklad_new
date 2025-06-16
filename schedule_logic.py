# -*- coding: utf-8 -*-
"""
Модуль бізнес-логіки для роботи з розкладом.

Містить функції для визначення навчального тижня, отримання розкладу,
форматування тексту та роботи з часом занять.
"""

import pytz
from datetime import datetime, time
from typing import Optional, List, Union

from telegram import Update

from config import DAYS_UA, LESSON_TIMES, TIMEZONE, get_lesson_time_display
from data_manager import data_manager
from models import LessonModel, UserModel
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class ScheduleService:
    """Сервіс для роботи з розкладом."""
    
    def __init__(self):
        """Ініціалізація сервісу розкладу."""
        self._timezone = pytz.timezone(TIMEZONE)
    
    def get_current_week(self, target_date: Optional[datetime] = None) -> int:
        """
        Визначає номер навчального тижня (1 або 2).
        
        Args:
            target_date: Дата для розрахунку. Якщо None, використовується поточна дата.
            
        Returns:
            Номер тижня (1 або 2)
        """
        start_date = data_manager.schedule_start_date
        if not start_date:
            logger.warning("Дата початку семестру не встановлена, повертаю тиждень 1")
            return 1
        
        if target_date is None:
            target_date = datetime.now(self._timezone)
        
        try:
            # Приводимо до одного типу (naive datetime)
            if target_date.tzinfo is not None:
                target_date = target_date.replace(tzinfo=None)
                
            # Розраховуємо різницю в днях
            delta_days = (target_date.date() - start_date.date()).days
            
            # Визначаємо тиждень (0 -> тиждень 1, 1 -> тиждень 2, 2 -> тиждень 1, ...)
            week_number = (delta_days // 7) % 2 + 1
            
            logger.debug(f"Тиждень для дати {target_date.date()}: {week_number}")
            return week_number
            
        except Exception as e:
            logger.error(f"Помилка при розрахунку тижня: {e}")
            return 1
    
    def is_group_chat(self, update: Update) -> bool:
        """
        Перевіряє, чи є чат груповим.
        
        Args:
            update: Telegram update об'єкт
            
        Returns:
            True якщо це груповий чат
        """
        return update.effective_chat.type in ['group', 'supergroup']
    
    def get_user_group(self, user_id: Union[str, int], chat_id: Optional[Union[str, int]] = None) -> Optional[str]:
        """
        Отримує групу користувача з урахуванням контексту.
        
        Args:
            user_id: ID користувача
            chat_id: ID чату (опціонально)
            
        Returns:
            Назва групи або None
        """
        user_id_str = str(user_id)
        chat_id_str = str(chat_id) if chat_id else None
        
        # Пріоритет у налаштування групового чату
        if chat_id_str:
            group_chat = data_manager.get_group_chat(chat_id_str)
            if group_chat.default_group:
                logger.debug(f"Знайдено групу {group_chat.default_group} для чату {chat_id_str}")
                return group_chat.default_group
        
        # Перевіряємо особисті налаштування користувача
        user = data_manager.get_user(user_id_str)
        if user and user.group:
            logger.debug(f"Знайдено групу {user.group} для користувача {user_id_str}")
            return user.group
        
        logger.debug(f"Групу не знайдено для користувача {user_id_str}")
        return None
    
    def get_day_lessons(
        self, 
        group: str, 
        day: str, 
        week: Optional[int] = None,
        sort_by_pair: bool = True
    ) -> List[LessonModel]:
        """
        Отримує список занять для групи, дня та тижня.
        
        Args:
            group: Назва групи
            day: День тижня
            week: Номер тижня (якщо None, використовується поточний)
            sort_by_pair: Чи сортувати за номером пари
            
        Returns:
            Список занять
        """
        if week is None:
            week = self.get_current_week()
        
        lessons = data_manager.get_day_lessons(group, day)
        
        # Фільтруємо за тижнем
        filtered_lessons = [
            lesson for lesson in lessons 
            if week in lesson.weeks
        ]
        
        # Сортуємо за номером пари, якщо потрібно
        if sort_by_pair:
            filtered_lessons.sort(key=lambda x: x.pair)
        
        logger.debug(f"Знайдено {len(filtered_lessons)} занять для {group}, {day}, тиждень {week}")
        return filtered_lessons
    
    def format_schedule_text(
        self, 
        group: str, 
        day: str, 
        lessons: List[LessonModel], 
        week: int,
        include_week_info: bool = True
    ) -> str:
        """
        Форматує розклад для відправки в Telegram.
        
        Args:
            group: Назва групи
            day: День тижня  
            lessons: Список занять
            week: Номер тижня
            include_week_info: Чи включати інформацію про тиждень
            
        Returns:
            Відформатований текст розкладу
        """
        if not lessons:
            week_text = f" ({week} тиждень)" if include_week_info else ""
            return f"📅 На {day.capitalize()}{week_text} пар немає 😴"
        
        lines = [f"📅 *Розклад для групи {group}*"]
        
        if include_week_info:
            lines.append(f"🗓 {day.capitalize()} ({week} тиждень):")
        else:
            lines.append(f"🗓 {day.capitalize()}:")
        
        lines.append("")
        
        for lesson in lessons:
            time_display = get_lesson_time_display(lesson.pair)
            
            lesson_text = [
                f"*{lesson.pair} пара* ({time_display}):",
                f"📚 {lesson.name}"
            ]
            
            if lesson.teacher:
                lesson_text.append(f"👨‍🏫 {lesson.teacher}")
            
            if lesson.room:
                lesson_text.append(f"🏠 Кабінет: {lesson.room}")
            
            lines.append("\n".join(lesson_text))
            lines.append("")
        
        formatted_text = "\n".join(lines).rstrip()
        logger.debug(f"Відформатовано текст розкладу: {len(formatted_text)} символів")
        
        return formatted_text
    
    def get_next_lesson(self, group: str, target_time: Optional[datetime] = None) -> Optional[LessonModel]:
        """
        Знаходить наступне заняття для групи.
        
        Args:
            group: Назва групи
            target_time: Час для пошуку (якщо None, використовується поточний)
            
        Returns:
            Наступне заняття або None
        """
        if target_time is None:
            target_time = datetime.now(self._timezone)
        
        # Отримуємо день тижня
        weekday = target_time.weekday()
        day_name = DAYS_UA.get(weekday)
        
        if not day_name:
            logger.debug("Сьогодні вихідний день")
            return None
        
        # Отримуємо заняття на сьогодні
        lessons_today = self.get_day_lessons(group, day_name)
        
        if not lessons_today:
            logger.debug(f"На {day_name} немає занять для групи {group}")
            return None
        
        # Поточний час у форматі HH:MM
        current_time = target_time.strftime("%H:%M")
        
        # Шукаємо наступне заняття
        for lesson in lessons_today:
            lesson_start_time, _ = LESSON_TIMES.get(lesson.pair, ("00:00", "00:00"))
            if lesson_start_time > current_time:
                logger.debug(f"Знайдено наступне заняття: {lesson.name} о {lesson_start_time}")
                return lesson
        
        logger.debug("Більше занять на сьогодні немає")
        return None
    
    def get_current_lesson(self, group: str, target_time: Optional[datetime] = None) -> Optional[LessonModel]:
        """
        Знаходить поточне заняття для групи.
        
        Args:
            group: Назва групи
            target_time: Час для перевірки (якщо None, використовується поточний)
            
        Returns:
            Поточне заняття або None
        """
        if target_time is None:
            target_time = datetime.now(self._timezone)
            
        weekday = target_time.weekday()
        day_name = DAYS_UA.get(weekday)
        
        if not day_name:
            return None
        
        lessons_today = self.get_day_lessons(group, day_name)
        current_time_str = target_time.strftime("%H:%M")
        
        for lesson in lessons_today:
            start_time, end_time = LESSON_TIMES.get(lesson.pair, ("00:00", "00:00"))
            if start_time <= current_time_str <= end_time:
                logger.debug(f"Знайдено поточне заняття: {lesson.name}")
                return lesson
        
        return None
    
    def get_week_schedule(self, group: str, week: Optional[int] = None) -> dict[str, List[LessonModel]]:
        """
        Отримує розклад на весь тиждень.
        
        Args:
            group: Назва групи
            week: Номер тижня (якщо None, поточний)
            
        Returns:
            Словник, де ключ - день, значення - список занять.
        """
        if week is None:
            week = self.get_current_week()
        
        week_schedule = {}
        for day_name in DAYS_UA.values():
            lessons = self.get_day_lessons(group, day_name, week)
            if lessons:
                week_schedule[day_name] = lessons
                
        return week_schedule
    
    def time_until_lesson(self, lesson: LessonModel, target_time: Optional[datetime] = None) -> str:
        """
        Розраховує час до початку заняття.
        
        Args:
            lesson: Модель заняття
            target_time: Час для розрахунку (якщо None, поточний)
            
        Returns:
            Відформатований рядок (напр., "через 1 год 20 хв" або "через 30 хв").
        """
        if target_time is None:
            target_time = datetime.now(self._timezone)
        
        lesson_start_str = LESSON_TIMES.get(lesson.pair)[0]
        hour, minute = map(int, lesson_start_str.split(':'))
        
        lesson_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        delta = lesson_time - target_time
        
        if delta.total_seconds() < 0:
            return "вже почалося"
        
        total_minutes = int(delta.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours > 0 and minutes > 0:
            return f"через {hours} год {minutes} хв"
        elif hours > 0:
            return f"через {hours} год"
        else:
            return f"через {minutes} хв"


# Створюємо глобальний екземпляр сервісу
schedule_service = ScheduleService()

# Залишаємо старі функції для можливої зворотної сумісності
# (краще поступово їх рефакторити і видалити)
def get_current_week(target_date: Optional[datetime] = None) -> int:
    return schedule_service.get_current_week(target_date)

def is_group_chat(update: Update) -> bool:
    return schedule_service.is_group_chat(update)

def get_user_group(user_id: str, chat_id: str = None) -> str:
    return schedule_service.get_user_group(user_id, chat_id)

def get_day_schedule(group: str, day: str, week: int = None) -> list:
    return schedule_service.get_day_lessons(group, day, week)

def format_schedule_text(group: str, day: str, lessons: list, week: int) -> str:
    return schedule_service.format_schedule_text(group, day, lessons, week)

def get_next_lesson(user_group: str):
    return schedule_service.get_next_lesson(user_group) 
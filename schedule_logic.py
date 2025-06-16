# -*- coding: utf-8 -*-
"""
Модуль бизнес-логики для работы с расписанием.

Содержит функции для определения учебной недели, получения расписания,
форматирования текста и работы с временем занятий.
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
    """Сервис для работы с расписанием."""
    
    def __init__(self):
        """Инициализация сервиса расписания."""
        self._timezone = pytz.timezone(TIMEZONE)
    
    def get_current_week(self, target_date: Optional[datetime] = None) -> int:
        """
        Определяет номер учебной недели (1 или 2).
        
        Args:
            target_date: Дата для расчета. Если None, используется текущая дата.
            
        Returns:
            Номер недели (1 или 2)
        """
        start_date = data_manager.schedule_start_date
        if not start_date:
            logger.warning("Дата начала семестра не установлена, возвращаю неделю 1")
            return 1
        
        if target_date is None:
            target_date = datetime.now(self._timezone)
        
        try:
            # Приводим к одному типу (naive datetime)
            if target_date.tzinfo is not None:
                target_date = target_date.replace(tzinfo=None)
                
            # Рассчитываем разность в днях
            delta_days = (target_date.date() - start_date.date()).days
            
            # Определяем неделю (0 -> неделя 1, 1 -> неделя 2, 2 -> неделя 1, ...)
            week_number = (delta_days // 7) % 2 + 1
            
            logger.debug(f"Неделя для даты {target_date.date()}: {week_number}")
            return week_number
            
        except Exception as e:
            logger.error(f"Ошибка при расчете недели: {e}")
            return 1
    
    def is_group_chat(self, update: Update) -> bool:
        """
        Проверяет, является ли чат групповым.
        
        Args:
            update: Telegram update объект
            
        Returns:
            True если это групповой чат
        """
        return update.effective_chat.type in ['group', 'supergroup']
    
    def get_user_group(self, user_id: Union[str, int], chat_id: Optional[Union[str, int]] = None) -> Optional[str]:
        """
        Получает группу пользователя с учетом контекста.
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата (опционально)
            
        Returns:
            Название группы или None
        """
        user_id_str = str(user_id)
        chat_id_str = str(chat_id) if chat_id else None
        
        # Приоритет у настройки группового чата
        if chat_id_str:
            group_chat = data_manager.get_group_chat(chat_id_str)
            if group_chat.default_group:
                logger.debug(f"Найдена группа {group_chat.default_group} для чата {chat_id_str}")
                return group_chat.default_group
        
        # Проверяем личные настройки пользователя
        user = data_manager.get_user(user_id_str)
        if user.group:
            logger.debug(f"Найдена группа {user.group} для пользователя {user_id_str}")
            return user.group
        
        logger.debug(f"Группа не найдена для пользователя {user_id_str}")
        return None
    
    def get_day_lessons(
        self, 
        group: str, 
        day: str, 
        week: Optional[int] = None,
        sort_by_pair: bool = True
    ) -> List[LessonModel]:
        """
        Получает список занятий для группы, дня и недели.
        
        Args:
            group: Название группы
            day: День недели
            week: Номер недели (если None, используется текущая)
            sort_by_pair: Сортировать ли по номеру пары
            
        Returns:
            Список занятий
        """
        if week is None:
            week = self.get_current_week()
        
        lessons = data_manager.get_day_lessons(group, day)
        
        # Фильтруем по неделе
        filtered_lessons = [
            lesson for lesson in lessons 
            if week in lesson.weeks
        ]
        
        # Сортируем по номеру пары если требуется
        if sort_by_pair:
            filtered_lessons.sort(key=lambda x: x.pair)
        
        logger.debug(f"Найдено {len(filtered_lessons)} занятий для {group}, {day}, неделя {week}")
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
        Форматирует расписание для отправки в Telegram.
        
        Args:
            group: Название группы
            day: День недели  
            lessons: Список занятий
            week: Номер недели
            include_week_info: Включать ли информацию о неделе
            
        Returns:
            Отформатированный текст расписания
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
        logger.debug(f"Отформатирован текст расписания: {len(formatted_text)} символов")
        
        return formatted_text
    
    def get_next_lesson(self, group: str, target_time: Optional[datetime] = None) -> Optional[LessonModel]:
        """
        Находит следующее занятие для группы.
        
        Args:
            group: Название группы
            target_time: Время для поиска (если None, используется текущее)
            
        Returns:
            Следующее занятие или None
        """
        if target_time is None:
            target_time = datetime.now(self._timezone)
        
        # Получаем день недели
        weekday = target_time.weekday()
        day_name = DAYS_UA.get(weekday)
        
        if not day_name:
            logger.debug("Сегодня выходной день")
            return None
        
        # Получаем занятия на сегодня
        lessons_today = self.get_day_lessons(group, day_name)
        
        if not lessons_today:
            logger.debug(f"На {day_name} нет занятий для группы {group}")
            return None
        
        # Текущее время в формате HH:MM
        current_time = target_time.strftime("%H:%M")
        
        # Ищем следующее занятие
        for lesson in lessons_today:
            lesson_start_time = LESSON_TIMES.get(lesson.pair, ("00:00", "00:00"))[0]
            if lesson_start_time > current_time:
                logger.debug(f"Найдено следующее занятие: {lesson.name} в {lesson_start_time}")
                return lesson
        
        logger.debug("Больше занятий на сегодня нет")
        return None
    
    def get_current_lesson(self, group: str, target_time: Optional[datetime] = None) -> Optional[LessonModel]:
        """
        Находит текущее занятие для группы.
        
        Args:
            group: Название группы
            target_time: Время для проверки (если None, используется текущее)
            
        Returns:
            Текущее занятие или None
        """
        if target_time is None:
            target_time = datetime.now(self._timezone)
        
        weekday = target_time.weekday()
        day_name = DAYS_UA.get(weekday)
        
        if not day_name:
            return None
        
        lessons_today = self.get_day_lessons(group, day_name)
        current_time = target_time.strftime("%H:%M")
        
        # Ищем занятие, которое идет сейчас
        for lesson in lessons_today:
            start_time, end_time = LESSON_TIMES.get(lesson.pair, ("00:00", "00:00"))
            if start_time <= current_time <= end_time:
                logger.debug(f"Найдено текущее занятие: {lesson.name}")
                return lesson
        
        return None
    
    def get_week_schedule(self, group: str, week: Optional[int] = None) -> dict[str, List[LessonModel]]:
        """
        Получает расписание на всю неделю.
        
        Args:
            group: Название группы
            week: Номер недели (если None, используется текущая)
            
        Returns:
            Словарь с расписанием по дням
        """
        if week is None:
            week = self.get_current_week()
        
        week_schedule = {}
        for day_num, day_name in DAYS_UA.items():
            if day_num < 6:  # Только учебные дни (пн-сб)
                lessons = self.get_day_lessons(group, day_name, week)
                if lessons:  # Добавляем только дни с занятиями
                    week_schedule[day_name] = lessons
        
        logger.debug(f"Получено расписание на неделю для группы {group}: {len(week_schedule)} дней с занятиями")
        return week_schedule
    
    def time_until_lesson(self, lesson: LessonModel, target_time: Optional[datetime] = None) -> str:
        """
        Вычисляет время до начала занятия.
        
        Args:
            lesson: Занятие
            target_time: Время для расчета (если None, используется текущее)
            
        Returns:
            Строка с описанием времени до занятия
        """
        if target_time is None:
            target_time = datetime.now(self._timezone)
        
        lesson_start_time_str = LESSON_TIMES.get(lesson.pair, ("00:00", "00:00"))[0]
        
        # Создаем datetime объект для времени занятия
        lesson_time = datetime.strptime(lesson_start_time_str, "%H:%M").time()
        lesson_datetime = datetime.combine(target_time.date(), lesson_time)
        
        if target_time.tzinfo:
            lesson_datetime = self._timezone.localize(lesson_datetime)
        
        time_diff = lesson_datetime - target_time
        
        if time_diff.total_seconds() <= 0:
            return "Занятие уже началось"
        
        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
        minutes = remainder // 60
        
        if hours > 0:
            return f"Через {hours} ч {minutes} мин"
        else:
            return f"Через {minutes} мин"


# Создаем глобальный экземпляр сервиса
schedule_service = ScheduleService()

# Экспорт функций для обратной совместимости
def get_current_week(target_date: Optional[datetime] = None) -> int:
    """Получает текущую неделю (обратная совместимость)."""
    return schedule_service.get_current_week(target_date)

def is_group_chat(update: Update) -> bool:
    """Проверяет групповой чат (обратная совместимость)."""
    return schedule_service.is_group_chat(update)

def get_user_group(user_id: str, chat_id: str = None) -> str:
    """Получает группу пользователя (обратная совместимость)."""
    return schedule_service.get_user_group(user_id, chat_id)

def get_day_schedule(group: str, day: str, week: int = None) -> list:
    """Получает расписание дня (обратная совместимость)."""
    lessons = schedule_service.get_day_lessons(group, day, week)
    # Конвертируем в старый формат для совместимости
    return [lesson.model_dump() for lesson in lessons]

def format_schedule_text(group: str, day: str, lessons: list, week: int) -> str:
    """Форматирует текст расписания (обратная совместимость).""" 
    # Конвертируем из старого формата
    lesson_models = [LessonModel.model_validate(lesson) for lesson in lessons]
    return schedule_service.format_schedule_text(group, day, lesson_models, week)

def get_next_lesson(user_group: str):
    """Получает следующее занятие (обратная совместимость)."""
    lesson = schedule_service.get_next_lesson(user_group)
    return lesson.model_dump() if lesson else None 
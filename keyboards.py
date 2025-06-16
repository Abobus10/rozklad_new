# -*- coding: utf-8 -*-
"""
Фабрика клавиатур для Telegram бота.

Современная архитектура с типизацией и паттерном "Фабрика".
Отвечает за создание всех типов клавиатур, используемых в боте.
"""

from typing import Dict, List, Optional, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from data_manager import data_manager
from logger_config import LoggerMixin


class KeyboardFactory(LoggerMixin):
    """Фабрика для создания клавиатур бота."""
    
    def __init__(self):
        """Инициализация фабрики клавиатур."""
        self.logger.info("Инициализация фабрики клавиатур")
        
        # Кэш для часто используемых клавиатур
        self._cache: Dict[str, InlineKeyboardMarkup] = {}
        self._setup_static_keyboards()

    def _setup_static_keyboards(self) -> None:
        """Настраивает статические клавиатуры."""
        # Быстрая навигация для расписания на сегодня
        self._cache["quick_nav"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
                InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("📊 Неделя", callback_data="quick_week"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])
        
        # Навигация для расписания на завтра
        self._cache["tomorrow_nav"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="quick_today"),
                InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("📊 Неделя", callback_data="quick_week"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])
        
        # Навигация для следующей пары
        self._cache["next_lesson_nav"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="quick_today"),
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")
            ],
            [
                InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])
        
        # Клавиатура когда больше нет пар
        self._cache["no_more_lessons"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
                InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])

    def get_main_menu_keyboard(self, user_id: str, chat_id: str, is_group: bool) -> InlineKeyboardMarkup:
        """
        Создает динамическую главную клавиатуру.
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата
            is_group: Является ли чат групповым
            
        Returns:
            Готовая клавиатура для главного меню
        """
        if is_group:
            return self._build_group_menu_keyboard(chat_id)
        else:
            return self._build_private_menu_keyboard(user_id)

    def _build_group_menu_keyboard(self, chat_id: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для группового чата.
        
        Args:
            chat_id: ID группового чата
            
        Returns:
            Клавиатура для группового меню
        """
        group_data = data_manager.get_group_chat(chat_id)
        default_group = group_data.default_group if group_data else None
        
        if default_group:
            # Полный набор кнопок для настроенной группы
            keyboard = [
                [
                    InlineKeyboardButton("📅 Сегодня", callback_data="quick_today"),
                    InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")
                ],
                [
                    InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule"),
                    InlineKeyboardButton("⏰ Следующая пара", callback_data="quick_next")
                ],
                [
                    InlineKeyboardButton("📊 Неделя", callback_data="quick_week"),
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")
                ],
                [
                    InlineKeyboardButton("ℹ️ Инфо группы", callback_data="quick_groupinfo"),
                    InlineKeyboardButton("🎮 Игра", callback_data="quick_game")
                ]
            ]
        else:
            # Ограниченный набор для ненастроенной группы
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Установить расписание", callback_data="quick_setgroupschedule")
                ],
                [
                    InlineKeyboardButton("ℹ️ Инфо группы", callback_data="quick_groupinfo"),
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")
                ]
            ]
        
        return InlineKeyboardMarkup(keyboard)

    def _build_private_menu_keyboard(self, user_id: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для приватного чата.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Клавиатура для приватного меню
        """
        user_data = data_manager.get_user(user_id)
        user_group = user_data.group if user_data else None
        
        if user_group:
            # Полный набор кнопок для пользователя с группой
            keyboard = [
                [
                    InlineKeyboardButton("📅 Сегодня", callback_data="quick_today"),
                    InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")
                ],
                [
                    InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule"),
                    InlineKeyboardButton("⏰ Следующая пара", callback_data="quick_next")
                ],
                [
                    InlineKeyboardButton("📊 Неделя", callback_data="quick_week"),
                    InlineKeyboardButton("🔔 Напоминания", callback_data="quick_reminders")
                ],
                [
                    InlineKeyboardButton("👤 Профиль", callback_data="quick_me"),
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")
                ],
                [
                    InlineKeyboardButton("🎮 Игра", callback_data="quick_game"),
                    InlineKeyboardButton("⚙️ Изменить группу", callback_data="quick_setgroup")
                ]
            ]
        else:
            # Ограниченный набор для пользователя без группы
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Установить группу", callback_data="quick_setgroup")
                ],
                [
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact"),
                    InlineKeyboardButton("🎮 Игра", callback_data="quick_game")
                ],
                [
                    InlineKeyboardButton("👤 Профиль", callback_data="quick_me")
                ]
            ]
        
        return InlineKeyboardMarkup(keyboard)

    def get_schedule_day_keyboard(self, user_group: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для выбора дня недели.
        
        Args:
            user_group: Название группы пользователя
            
        Returns:
            Клавиатура для выбора дня
        """
        # Получаем доступные дни для группы
        available_days = self._get_available_days_for_group(user_group)
        
        keyboard = [
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="schedule_today"),
                InlineKeyboardButton("📅 Завтра", callback_data="schedule_tomorrow")
            ]
        ]
        
        # Добавляем кнопки дней недели по две в ряд
        for i in range(0, len(available_days), 2):
            row = []
            for day in available_days[i:i+2]:
                row.append(
                    InlineKeyboardButton(
                        day.capitalize(), 
                        callback_data=f"schedule_day_{day}"
                    )
                )
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)

    def _get_available_days_for_group(self, user_group: str) -> List[str]:
        """
        Получает список дней недели с расписанием для группы.
        
        Args:
            user_group: Название группы
            
        Returns:
            Список дней недели
        """
        schedule_data = data_manager.schedule_data
        group_schedule = schedule_data.groups.get(user_group)
        
        if not group_schedule:
            return []
            
        schedule = group_schedule.schedule
        
        days_order = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота"]
        return [day for day in days_order if day in schedule and schedule[day]]

    def get_reminders_keyboard(self, user_id: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для настройки уведомлений.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Клавиатура настроек уведомлений
        """
        user_data = data_manager.get_user(user_id)
        
        if not user_data:
            # Если пользователь не найден, создаем базовую клавиатуру
            daily_reminder = False
            lesson_notifications = True
        else:
            daily_reminder = user_data.daily_reminder
            lesson_notifications = user_data.lesson_notifications
        
        keyboard = [
            [
                InlineKeyboardButton("⏰ Установить время напоминания", callback_data="set_reminder_time")
            ],
            [
                InlineKeyboardButton(
                    f"📅 Ежедневные напоминания: {'✅' if daily_reminder else '❌'}",
                    callback_data="toggle_daily_reminder"
                )
            ],
            [
                InlineKeyboardButton(
                    f"🔔 Уведомления между парами: {'✅' if lesson_notifications else '❌'}",
                    callback_data="toggle_lesson_notifications"
                )
            ],
            [
                InlineKeyboardButton("❌ Отключить все напоминания", callback_data="disable_reminders")
            ],
            [
                InlineKeyboardButton("⬅️ Назад в меню", callback_data="show_menu")
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)

    def get_group_selection_keyboard(self) -> ReplyKeyboardMarkup:
        """
        Создает клавиатуру для выбора группы.
        
        Returns:
            Reply клавиатура с доступными группами
        """
        schedule_data = data_manager.get_schedule_data()
        available_groups = list(schedule_data.get("groups", {}).keys())
        
        if not available_groups:
            # Если групп нет, возвращаем пустую клавиатуру
            return ReplyKeyboardMarkup([["Нет доступных групп"]], one_time_keyboard=True)
        
        return ReplyKeyboardMarkup(
            [available_groups], 
            one_time_keyboard=True, 
            input_field_placeholder="Название группы"
        )

    def get_admin_group_selection_keyboard(self, chat_id: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для администратора для установки группы чата.
        
        Args:
            chat_id: ID чата для которого устанавливается группа
            
        Returns:
            Inline клавиатура с доступными группами
        """
        schedule_data = data_manager.get_schedule_data()
        available_groups = list(schedule_data.get("groups", {}).keys())
        
        keyboard = []
        
        # Разбиваем группы по две в ряд
        for i in range(0, len(available_groups), 2):
            row = []
            for group in available_groups[i:i+2]:
                row.append(
                    InlineKeyboardButton(
                        group, 
                        callback_data=f"setgroup_{group}_{chat_id}"
                    )
                )
            keyboard.append(row)
        
        if not keyboard:
            # Если групп нет, добавляем информационную кнопку
            keyboard.append([
                InlineKeyboardButton("Нет доступных групп", callback_data="no_groups_available")
            ])
        
        return InlineKeyboardMarkup(keyboard)

    def get_conversation_keyboard(self, conversation_type: str, **kwargs) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для различных диалогов.
        
        Args:
            conversation_type: Тип диалога
            **kwargs: Дополнительные параметры
            
        Returns:
            Клавиатура для диалога
        """
        if conversation_type == "group_selection":
            return self._get_group_selection_conversation_keyboard()
        elif conversation_type == "game":
            return self._get_game_conversation_keyboard()
        elif conversation_type == "cancel":
            return self._get_cancel_conversation_keyboard()
        else:
            return self._get_default_conversation_keyboard()

    def _get_group_selection_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Создает клавиатуру для выбора группы в диалоге."""
        schedule_data = data_manager.get_schedule_data()
        available_groups = list(schedule_data.get("groups", {}).keys())
        
        keyboard = []
        
        # Группы по две в ряд
        for i in range(0, len(available_groups), 2):
            row = []
            for group in available_groups[i:i+2]:
                row.append(
                    InlineKeyboardButton(
                        group, 
                        callback_data=f"conv_group_{group}"
                    )
                )
            keyboard.append(row)
        
        # Кнопка отмены
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="conv_cancel")
        ])
        
        return InlineKeyboardMarkup(keyboard)

    def _get_game_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Создает клавиатуру для игры."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Прекратить игру", callback_data="conv_cancel")]
        ])

    def _get_cancel_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Создает клавиатуру с кнопкой отмены."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="conv_cancel")]
        ])

    def _get_default_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Создает стандартную клавиатуру для диалога."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 В меню", callback_data="show_menu")]
        ])

    def get_cached_keyboard(self, keyboard_name: str) -> Optional[InlineKeyboardMarkup]:
        """
        Получает клавиатуру из кэша.
        
        Args:
            keyboard_name: Название кэшированной клавиатуры
            
        Returns:
            Клавиатура из кэша или None
        """
        return self._cache.get(keyboard_name)

    def add_to_cache(self, keyboard_name: str, keyboard: InlineKeyboardMarkup) -> None:
        """
        Добавляет клавиатуру в кэш.
        
        Args:
            keyboard_name: Название клавиатуры
            keyboard: Клавиатура для кэширования
        """
        self._cache[keyboard_name] = keyboard
        self.logger.debug(f"Клавиатура '{keyboard_name}' добавлена в кэш")

    def clear_cache(self) -> None:
        """Очищает кэш клавиатур."""
        self._cache.clear()
        self._setup_static_keyboards()
        self.logger.info("Кэш клавиатур очищен и пересоздан")

    def get_navigation_keyboard(self, nav_type: str) -> InlineKeyboardMarkup:
        """
        Получает навигационную клавиатуру по типу.
        
        Args:
            nav_type: Тип навигационной клавиатуры
            
        Returns:
            Навигационная клавиатура
        """
        keyboard_mapping = {
            "quick_nav": "quick_nav",
            "tomorrow_nav": "tomorrow_nav", 
            "next_lesson_nav": "next_lesson_nav",
            "no_more_lessons": "no_more_lessons"
        }
        
        keyboard_name = keyboard_mapping.get(nav_type, "quick_nav")
        return self._cache.get(keyboard_name, self._cache["quick_nav"])

    def create_custom_keyboard(self, buttons_data: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
        """
        Создает кастомную клавиатуру по переданным данным.
        
        Args:
            buttons_data: Данные для кнопок в формате 
                         [[{"text": "...", "callback_data": "..."}, ...], ...]
                         
        Returns:
            Готовая кастомная клавиатура
        """
        keyboard = []
        
        for row_data in buttons_data:
            row = []
            for button_data in row_data:
                button = InlineKeyboardButton(
                    text=button_data.get("text", "Кнопка"),
                    callback_data=button_data.get("callback_data", "empty")
                )
                row.append(button)
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)


# Создаем глобальный экземпляр фабрики
keyboard_factory = KeyboardFactory()

# Экспортируем функции для обратной совместимости
def get_main_menu_keyboard(user_id: str, chat_id: str, is_group: bool) -> InlineKeyboardMarkup:
    """Обратная совместимость для главного меню."""
    return keyboard_factory.get_main_menu_keyboard(user_id, chat_id, is_group)

def get_schedule_day_keyboard(user_group: str) -> InlineKeyboardMarkup:
    """Обратная совместимость для выбора дня."""
    return keyboard_factory.get_schedule_day_keyboard(user_group)

def get_reminders_keyboard(user_id: str) -> InlineKeyboardMarkup:
    """Обратная совместимость для настроек напоминаний."""
    return keyboard_factory.get_reminders_keyboard(user_id)

def get_group_selection_keyboard() -> ReplyKeyboardMarkup:
    """Обратная совместимость для выбора группы."""
    return keyboard_factory.get_group_selection_keyboard()

def get_admin_group_selection_keyboard(chat_id: str) -> InlineKeyboardMarkup:
    """Обратная совместимость для админской настройки группы."""
    return keyboard_factory.get_admin_group_selection_keyboard(chat_id)

# Статические клавиатуры для обратной совместимости
quick_nav_keyboard = keyboard_factory.get_cached_keyboard("quick_nav")
tomorrow_nav_keyboard = keyboard_factory.get_cached_keyboard("tomorrow_nav")
next_lesson_nav_keyboard = keyboard_factory.get_cached_keyboard("next_lesson_nav")
no_more_lessons_keyboard = keyboard_factory.get_cached_keyboard("no_more_lessons") 
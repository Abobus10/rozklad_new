# -*- coding: utf-8 -*-
"""
Фабрика клавіатур для Telegram бота.

Сучасна архітектура з типізацією та патерном "Фабрика".
Відповідає за створення всіх типів клавіатур, що використовуються в боті.
"""

from typing import Dict, List, Optional, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from data_manager import data_manager
from logger_config import LoggerMixin


class KeyboardFactory(LoggerMixin):
    """Фабрика для створення клавіатур бота."""
    
    def __init__(self):
        """Ініціалізація фабрики клавіатур."""
        self.logger.info("Ініціалізація фабрики клавіатур")
        
        # Кеш для клавіатур, що часто використовуються
        self._cache: Dict[str, InlineKeyboardMarkup] = {}
        self._setup_static_keyboards()

    def _setup_static_keyboards(self) -> None:
        """Налаштовує статичні клавіатури."""
        # Швидка навігація для розкладу на сьогодні
        self._cache["quick_nav"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
                InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])
        
        # Навігація для розкладу на завтра
        self._cache["tomorrow_nav"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
                InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])
        
        # Навігація для наступної пари
        self._cache["next_lesson_nav"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")
            ],
            [
                InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])
        
        # Клавіатура, коли більше немає пар
        self._cache["no_more_lessons"] = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
                InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ])

    def get_main_menu_keyboard(self, user_id: str, chat_id: str, is_group: bool) -> InlineKeyboardMarkup:
        """
        Створює динамічну головну клавіатуру.
        
        Args:
            user_id: ID користувача
            chat_id: ID чату
            is_group: Чи є чат груповим
            
        Returns:
            Готова клавіатура для головного меню
        """
        if is_group:
            return self._build_group_menu_keyboard(chat_id)
        else:
            return self._build_private_menu_keyboard(user_id)

    def _build_group_menu_keyboard(self, chat_id: str) -> InlineKeyboardMarkup:
        """
        Створює клавіатуру для групового чату.
        
        Args:
            chat_id: ID групового чату
            
        Returns:
            Клавіатура для групового меню
        """
        group_data = data_manager.get_group_chat(chat_id)
        default_group = group_data.default_group if group_data else None
        
        if default_group:
            # Повний набір кнопок для налаштованої групи
            keyboard = [
                [
                    InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
                    InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")
                ],
                [
                    InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule"),
                    InlineKeyboardButton("⏰ Наступна пара", callback_data="quick_next")
                ],
                [
                    InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")
                ],
                [
                    InlineKeyboardButton("ℹ️ Інфо групи", callback_data="quick_groupinfo"),
                    InlineKeyboardButton("🎮 Гра", callback_data="quick_game")
                ]
            ]
        else:
            # Обмежений набір для ненастроєної групи
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Встановити розклад", callback_data="quick_setgroupschedule")
                ],
                [
                    InlineKeyboardButton("ℹ️ Інфо групи", callback_data="quick_groupinfo"),
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")
                ]
            ]
        
        return InlineKeyboardMarkup(keyboard)

    def _build_private_menu_keyboard(self, user_id: str) -> InlineKeyboardMarkup:
        """
        Створює клавіатуру для приватного чату.
        
        Args:
            user_id: ID користувача
            
        Returns:
            Клавіатура для приватного меню
        """
        user_data = data_manager.get_user(user_id)
        user_group = user_data.group if user_data else None
        
        if user_group:
            # Повний набір кнопок для користувача з групою
            keyboard = [
                [
                    InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
                    InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")
                ],
                [
                    InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule"),
                    InlineKeyboardButton("⏰ Наступна пара", callback_data="quick_next")
                ],
                [
                    InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                    InlineKeyboardButton("🔔 Нагадування", callback_data="quick_reminders")
                ],
                [
                    InlineKeyboardButton("👤 Профіль", callback_data="quick_me"),
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")
                ],
                [
                    InlineKeyboardButton("🎮 Гра", callback_data="quick_game"),
                    InlineKeyboardButton("⚙️ Змінити групу", callback_data="quick_setgroup")
                ]
            ]
        else:
            # Обмежений набір для користувача без групи
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Встановити групу", callback_data="quick_setgroup")
                ],
                [
                    InlineKeyboardButton("🎲 Факт", callback_data="quick_fact"),
                    InlineKeyboardButton("🎮 Гра", callback_data="quick_game")
                ],
                [
                    InlineKeyboardButton("👤 Профіль", callback_data="quick_me")
                ]
            ]
        
        return InlineKeyboardMarkup(keyboard)

    def get_schedule_day_keyboard(self, user_group: str) -> InlineKeyboardMarkup:
        """
        Створює клавіатуру для вибору дня тижня.
        
        Args:
            user_group: Назва групи користувача
            
        Returns:
            Клавіатура для вибору дня
        """
        # Отримуємо доступні дні для групи
        available_days = self._get_available_days_for_group(user_group)
        
        keyboard = [
            [
                InlineKeyboardButton("📅 Сьогодні", callback_data="schedule_today"),
                InlineKeyboardButton("📅 Завтра", callback_data="schedule_tomorrow")
            ]
        ]
        
        # Додаємо кнопки днів тижня по дві в ряд
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
        Отримує список днів тижня з розкладом для групи.
        
        Args:
            user_group: Назва групи
            
        Returns:
            Список днів тижня
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
        Створює клавіатуру налаштувань нагадувань.
        
        Args:
            user_id: ID користувача
            
        Returns:
            Клавіатура налаштувань
        """
        user = data_manager.get_user(user_id)
        
        daily_reminder_status = "✅ Увімкнено" if user and user.daily_reminder else "❌ Вимкнено"
        lesson_notifications_status = "✅ Увімкнено" if user and user.lesson_notifications else "❌ Вимкнено"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"Нагадування о {user.reminder_time if user and user.reminder_time else '08:00'}",
                    callback_data="set_reminder_time"
                )
            ],
            [
                InlineKeyboardButton(
                    f"Щоденне: {daily_reminder_status}",
                    callback_data="toggle_daily_reminder"
                )
            ],
            [
                InlineKeyboardButton(
                    f"Про пари: {lesson_notifications_status}",
                    callback_data="toggle_lesson_notifications"
                )
            ],
            [
                InlineKeyboardButton("🚫 Вимкнути все", callback_data="disable_reminders"),
                InlineKeyboardButton("⬅️ Назад", callback_data="show_menu")
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)

    def get_group_selection_keyboard(self) -> ReplyKeyboardMarkup:
        """
        Створює клавіатуру для вибору групи.
        
        Returns:
            Reply клавіатура з доступними групами
        """
        schedule_data = data_manager.get_schedule_data()
        available_groups = list(schedule_data.get("groups", {}).keys())
        
        if not available_groups:
            # Якщо груп немає, повертаємо пусту клавіатуру
            return ReplyKeyboardMarkup([["Немає доступних груп"]], one_time_keyboard=True)
        
        return ReplyKeyboardMarkup(
            [available_groups], 
            one_time_keyboard=True, 
            input_field_placeholder="Назва групи"
        )

    def get_admin_group_selection_keyboard(self, chat_id: str) -> InlineKeyboardMarkup:
        """
        Створює клавіатуру для адміна для установки групи чату.
        
        Args:
            chat_id: ID чату для якого установлюється група
            
        Returns:
            Inline клавіатура з доступними групами
        """
        schedule_data = data_manager.get_schedule_data()
        available_groups = list(schedule_data.get("groups", {}).keys())
        
        keyboard = []
        
        # Розбиваємо групи по дві в ряд
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
            # Якщо груп немає, додаємо інформаційну кнопку
            keyboard.append([
                InlineKeyboardButton("Немає доступних груп", callback_data="no_groups_available")
            ])
        
        return InlineKeyboardMarkup(keyboard)

    def get_conversation_keyboard(self, conversation_type: str, **kwargs) -> InlineKeyboardMarkup:
        """
        Створює клавіатуру для різних діалогів.
        
        Args:
            conversation_type: Тип діалогу
            **kwargs: Додаткові параметри
            
        Returns:
            Клавіатура для діалогу
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
        """Створює клавіатуру для вибору групи в діалозі."""
        schedule_data = data_manager.get_schedule_data()
        available_groups = list(schedule_data.get("groups", {}).keys())
        
        keyboard = []
        
        # Групи по дві в ряд
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
        
        # Кнопка скасування
        keyboard.append([
            InlineKeyboardButton("❌ Скасувати", callback_data="conv_cancel")
        ])
        
        return InlineKeyboardMarkup(keyboard)

    def _get_game_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Клавіатура для гри."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Скасувати гру", callback_data="conv_cancel")
        ]])

    def _get_cancel_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Клавіатура для скасування дії."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Скасувати", callback_data="conv_cancel")
        ]])

    def _get_default_conversation_keyboard(self) -> InlineKeyboardMarkup:
        """Створює стандартну клавіатуру для діалогу."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 В меню", callback_data="show_menu")]
        ])

    def get_cached_keyboard(self, keyboard_name: str) -> Optional[InlineKeyboardMarkup]:
        """
        Отримує клавіатуру з кеша.
        
        Args:
            keyboard_name: Назва кешованої клавіатури
            
        Returns:
            Клавіатура з кеша або None
        """
        return self._cache.get(keyboard_name)

    def add_to_cache(self, keyboard_name: str, keyboard: InlineKeyboardMarkup) -> None:
        """
        Додає клавіатуру в кеш.
        
        Args:
            keyboard_name: Назва клавіатури
            keyboard: Клавіатура для кешування
        """
        self._cache[keyboard_name] = keyboard
        self.logger.debug(f"Клавіатура '{keyboard_name}' додана в кеш")

    def clear_cache(self) -> None:
        """Очищає кеш клавіатур."""
        self._cache.clear()
        self._setup_static_keyboards()
        self.logger.info("Кеш клавіатур очищений і пересоздан")

    def get_navigation_keyboard(self, nav_type: str) -> InlineKeyboardMarkup:
        """
        Отримує навігаційну клавіатуру по типу.
        
        Args:
            nav_type: Тип навігаційної клавіатури
            
        Returns:
            Навігаційна клавіатура
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
        Створює кастомну клавіатуру на основі наданих даних.
        
        Args:
            buttons_data: Список списків, що містять словники з 'text' і 'callback_data'.
            
        Returns:
            Готова кастомна клавіатура
        """
        keyboard = []
        for row_data in buttons_data:
            row = [
                InlineKeyboardButton(button['text'], callback_data=button['callback_data']) 
                for button in row_data
            ]
            keyboard.append(row)
            
        return InlineKeyboardMarkup(keyboard)


# Створюємо глобальний екземпляр фабрики
keyboard_factory = KeyboardFactory()

# Експортуємо функції для зворотної сумісності
def get_main_menu_keyboard(user_id: str, chat_id: str, is_group: bool) -> InlineKeyboardMarkup:
    """Зворотна сумісність для головного меню."""
    return keyboard_factory.get_main_menu_keyboard(user_id, chat_id, is_group)

def get_schedule_day_keyboard(user_group: str) -> InlineKeyboardMarkup:
    """Зворотна сумісність для вибору дня."""
    return keyboard_factory.get_schedule_day_keyboard(user_group)

def get_reminders_keyboard(user_id: str) -> InlineKeyboardMarkup:
    """Зворотна сумісність для налаштувань напоминань."""
    return keyboard_factory.get_reminders_keyboard(user_id)

def get_group_selection_keyboard() -> ReplyKeyboardMarkup:
    """Зворотна сумісність для вибору групи."""
    return keyboard_factory.get_group_selection_keyboard()

def get_admin_group_selection_keyboard(chat_id: str) -> InlineKeyboardMarkup:
    """Зворотна сумісність для адмінської настройки групи."""
    return keyboard_factory.get_admin_group_selection_keyboard(chat_id)

# Статичні клавіатури для зворотної сумісності
quick_nav_keyboard = keyboard_factory.get_cached_keyboard("quick_nav")
tomorrow_nav_keyboard = keyboard_factory.get_cached_keyboard("tomorrow_nav")
next_lesson_nav_keyboard = keyboard_factory.get_cached_keyboard("next_lesson_nav")
no_more_lessons_keyboard = keyboard_factory.get_cached_keyboard("no_more_lessons") 
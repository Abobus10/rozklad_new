# -*- coding: utf-8 -*-
"""
Модуль для створення клавіатур (inline та reply).

Тут зосереджена логіка генерації клавіатур, що використовуються в боті.
Це дозволяє відокремити подання (view) від логіки обробників (controller),
роблячи код чистішим та легшим для підтримки.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from data_manager import schedule_data, group_chats_data, users_data

def get_main_menu_keyboard(user_id: str, chat_id: str, is_group: bool) -> InlineKeyboardMarkup:
    """
    Створює динамічну головну клавіатуру.
    
    Набір кнопок залежить від контексту:
    - Для групових чатів: показує різні кнопки залежно від того, чи встановлено розклад.
    - Для приватних чатів: адаптується до того, чи вибрав користувач свою групу.
    """
    if is_group:
        # --- Клавіатура для групового чату ---
        default_group = group_chats_data.get(chat_id, {}).get("default_group")
        if default_group:
            # Повний набір кнопок, якщо розклад для групи встановлено
            keyboard = [
                [InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
                 InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")],
                [InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule"),
                 InlineKeyboardButton("⏰ Наступна пара", callback_data="quick_next")],
                [InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                 InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")],
                [InlineKeyboardButton("ℹ️ Інфо групи", callback_data="quick_groupinfo"),
                 InlineKeyboardButton("🎮 Гра", callback_data="quick_game")]
            ]
        else:
            # Скорочений набір, якщо розклад не встановлено
            keyboard = [
                [InlineKeyboardButton("⚙️ Встановити розклад", callback_data="quick_setgroupschedule")],
                [InlineKeyboardButton("ℹ️ Інфо групи", callback_data="quick_groupinfo"),
                 InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")]
            ]
    else:
        # --- Клавіатура для приватного чату ---
        user_group = users_data.get(user_id, {}).get("group")
        if user_group:
            # Повний набір кнопок, якщо користувач встановив групу
            keyboard = [
                [InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
                 InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")],
                [InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule"),
                 InlineKeyboardButton("⏰ Наступна пара", callback_data="quick_next")],
                [InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                 InlineKeyboardButton("🔔 Нагадування", callback_data="quick_reminders")],
                [InlineKeyboardButton("👤 Профіль", callback_data="quick_me"),
                 InlineKeyboardButton("🎲 Факт", callback_data="quick_fact")],
                [InlineKeyboardButton("🎮 Гра", callback_data="quick_game"),
                 InlineKeyboardButton("⚙️ Змінити групу", callback_data="quick_setgroup")]
            ]
        else:
            # Скорочений набір, якщо група не встановлена
            keyboard = [
                [InlineKeyboardButton("⚙️ Встановити групу", callback_data="quick_setgroup")],
                [InlineKeyboardButton("🎲 Факт", callback_data="quick_fact"),
                 InlineKeyboardButton("🎮 Гра", callback_data="quick_game")],
                [InlineKeyboardButton("👤 Профіль", callback_data="quick_me")]
            ]
    return InlineKeyboardMarkup(keyboard)

def get_schedule_day_keyboard(user_group: str) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру для вибору дня тижня.
    
    Динамічно генерує кнопки тільки для тих днів, для яких є розклад у `schedule.json`,
    що робить інтерфейс більш чистим та релевантним.
    """
    group_schedule = schedule_data.get("groups", {}).get(user_group, {}).get("schedule", {})
    keyboard = []
    days_order = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота"]
    days_with_schedule = [day for day in days_order if day in group_schedule]
    
    keyboard.append([
        InlineKeyboardButton("📅 Сьогодні", callback_data="schedule_today"),
        InlineKeyboardButton("📅 Завтра", callback_data="schedule_tomorrow")
    ])
    
    # Розбивка кнопок по дві в ряду
    for i in range(0, len(days_with_schedule), 2):
        row = [InlineKeyboardButton(day.capitalize(), callback_data=f"schedule_day_{day}") for day in days_with_schedule[i:i+2]]
        keyboard.append(row)
        
    return InlineKeyboardMarkup(keyboard)

def get_reminders_keyboard(user_id: str) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру для налаштування сповіщень.
    
    Відображає поточний стан налаштувань користувача (увімкнено/вимкнено)
    за допомогою емодзі ✅ та ❌.
    """
    user_data = users_data.get(user_id, {})
    daily_reminder = user_data.get("daily_reminder", False)
    lesson_notifications = user_data.get("lesson_notifications", True)
    
    keyboard = [
        [InlineKeyboardButton("⏰ Встановити час нагадування", callback_data="set_reminder_time")],
        [InlineKeyboardButton(
            f"📅 Щоденні нагадування: {'✅' if daily_reminder else '❌'}",
            callback_data="toggle_daily_reminder"
        )],
        [InlineKeyboardButton(
            f"🔔 Повідомлення між парами: {'✅' if lesson_notifications else '❌'}",
            callback_data="toggle_lesson_notifications"
        )],
        [InlineKeyboardButton("❌ Вимкнути всі нагадування", callback_data="disable_reminders")],
        [InlineKeyboardButton("⬅️ Назад до меню", callback_data="show_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_group_selection_keyboard():
    """Creates keyboard with available groups for selection."""
    available_groups = list(schedule_data.get("groups", {}).keys())
    return ReplyKeyboardMarkup([available_groups], one_time_keyboard=True, input_field_placeholder="Назва групи")

def get_admin_group_selection_keyboard(chat_id: str) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру для адміністратора, щоб встановити групу для чату.
    
    Формує список кнопок з усіх доступних груп у `schedule.json`.
    """
    available_groups = list(schedule_data.get("groups", {}).keys())
    keyboard = []
    # Розбивка кнопок по дві в ряду
    for i in range(0, len(available_groups), 2):
        row = [InlineKeyboardButton(g, callback_data=f"setgroup_{g}_{chat_id}") for g in available_groups[i:i+2]]
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

# --- Статичні клавіатури для навігації ---
# Винесені в окремі змінні, оскільки їх структура не змінюється.
# Це дозволяє уникнути їх повторного створення при кожному виклику.

quick_nav_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
     InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")],
    [InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
     InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]
])

tomorrow_nav_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
     InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")],
    [InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
     InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]
])

next_lesson_nav_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📅 Сьогодні", callback_data="quick_today"),
     InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow")],
    [InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule"),
     InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]
])

no_more_lessons_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
     InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")],
    [InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]
]) 
# -*- coding: utf-8 -*-
"""
Обробники натискань на inline-кнопки (CallbackQueryHandler).

Цей модуль містить логіку, що виконується у відповідь на дії користувача
з inline-клавіатурами. Використання `callback_data` дозволяє точно
визначити, яка кнопка була натиснута.
"""

import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from data_manager import users_data, group_chats_data, save_users_data, save_group_chat_data, schedule_data
from schedule_logic import get_day_schedule, format_schedule_text, get_current_week, get_user_group, is_group_chat, get_next_lesson
from keyboards import (
    quick_nav_keyboard, tomorrow_nav_keyboard, no_more_lessons_keyboard, 
    get_main_menu_keyboard, get_reminders_keyboard
)
from handlers.commands import (
    me_command, reminders_command, schedule_command, 
    set_group_schedule_command, group_info_command, week_command, today_command, tomorrow_command
)
from handlers.utils import get_fact, schedule_message_deletion
from handlers.conversations import game_start
from config import DAYS_UA, LESSON_TIMES

logger = logging.getLogger(__name__)


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє вибір дня тижня з клавіатури розкладу.
    
    Парсить `callback_data` (напр., "schedule_day_понеділок"),
    визначає запитуваний день, отримує для нього розклад і оновлює повідомлення.
    """
    query = update.callback_query
    await query.answer()

    day_part = query.data.replace("schedule_", "")
    user_id = str(query.from_user.id)
    chat_id = str(query.message.chat.id)
    user_group = get_user_group(user_id, chat_id)

    if not user_group:
        await query.edit_message_text("⚠️ Спочатку встановіть групу.")
        # Тут не плануємо видалення, бо це редагування, і старе завдання вже може існувати.
        return

    day_name = None
    target_date = datetime.now()

    if day_part == "today":
        day_name = DAYS_UA.get(target_date.weekday())
    elif day_part == "tomorrow":
        target_date = datetime.now() + timedelta(days=1)
        day_name = DAYS_UA.get(target_date.weekday())
    else:
        day_name = day_part.replace("day_", "")
    
    week = get_current_week(target_date)

    if not day_name or day_name not in schedule_data.get("groups", {}).get(user_group, {}).get("schedule", {}):
        await query.edit_message_text(f"📅 На {day_name.capitalize()} пар немає! Відпочивай 😊", reply_markup=quick_nav_keyboard)
        return

    lessons = get_day_schedule(user_group, day_name, week)
    schedule_text = format_schedule_text(user_group, day_name, lessons, week)

    await query.edit_message_text(
        text=schedule_text,
        reply_markup=quick_nav_keyboard,
        parse_mode='Markdown'
    )
    # Явно не викликаємо schedule_message_deletion, оскільки редагування повідомлення 
    # не створює нового, і таймер видалення для початкового повідомлення продовжує діяти.


async def reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє натискання на кнопки в меню налаштувань сповіщень.
    
    Змінює налаштування користувача (`daily_reminder`, `lesson_notifications`)
    у `users_data` і оновлює клавіатуру, щоб відобразити зміни.
    """
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = query.data

    if user_id not in users_data:
        users_data[user_id] = {}

    # Логіка перемикання налаштувань
    if data == "toggle_daily_reminder":
        current_setting = users_data[user_id].get("daily_reminder", False)
        users_data[user_id]["daily_reminder"] = not current_setting
        save_users_data()
    elif data == "toggle_lesson_notifications":
        current_setting = users_data[user_id].get("lesson_notifications", True)
        users_data[user_id]["lesson_notifications"] = not current_setting
        save_users_data()
    elif data == "disable_reminders":
        users_data[user_id]["reminder_time"] = None
        users_data[user_id]["daily_reminder"] = False
        users_data[user_id]["lesson_notifications"] = False
        save_users_data()

    # Оновлення клавіатури з актуальними налаштуваннями
    reply_markup = get_reminders_keyboard(user_id)
    await query.edit_message_text("⚙️ *Налаштування нагадувань*", reply_markup=reply_markup, parse_mode='Markdown')


async def group_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє вибір групи для встановлення розкладу в груповому чаті.
    
    Викликається адміністратором чату.
    """
    query = update.callback_query
    await query.answer()

    _, group, chat_id = query.data.split("_")
    
    if chat_id not in group_chats_data:
        group_chats_data[chat_id] = {}

    group_chats_data[chat_id]["default_group"] = group
    save_group_chat_data()

    text = f"✅ Розклад для групи *{group}* встановлено для цього чату."
    keyboard = [[InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def quick_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Централізований обробник для "швидких дій" (кнопки з префіксом 'quick_').
    
    Цей підхід (маршрутизатор) дозволяє уникнути створення безлічі окремих
    обробників для кожної кнопки. Натомість, він аналізує `callback_data`
    і делегує виконання відповідній функції (часто з `from_callback=True`).
    """
    query = update.callback_query
    await query.answer()

    action = query.data

    # Маршрутизація до відповідних команд
    if action == "quick_today":
        await today_command(update, context, from_callback=True)
    elif action == "quick_tomorrow":
        await tomorrow_command(update, context, from_callback=True)
    elif action == "quick_week":
        await week_command(update, context, from_callback=True)
    elif action == "quick_schedule":
        await schedule_command(update, context, from_callback=True)
    elif action == "quick_reminders":
        await reminders_command(update, context, from_callback=True)
    elif action == "quick_me":
        await me_command(update, context, from_callback=True)
    elif action == "quick_fact":
        fact = await get_fact()
        keyboard = [
            [InlineKeyboardButton("🎲 Інший факт", callback_data="quick_fact")],
            [InlineKeyboardButton("⬅️ Назад до меню", callback_data="show_menu")]
        ]
        await query.edit_message_text(f"🧠 *Цікавий факт:*\n\n{fact}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "quick_next":
        user_group = get_user_group(str(query.from_user.id), str(query.message.chat.id) if is_group_chat(update) else None)
        if not user_group:
            await query.answer("⚠️ Спочатку встановіть групу.", show_alert=True)
            return

        next_lesson = get_next_lesson(user_group)
        
        if next_lesson:
            time_start, time_end = LESSON_TIMES.get(next_lesson['pair'], ("??:??", "??:??"))
            text = (f"⏰ *Наступна пара:*\n\n"
                    f"🕐 Час: {time_start} - {time_end}\n"
                    f"📚 Предмет: {next_lesson['name']}\n"
                    f"👨‍🏫 Викладач: {next_lesson.get('teacher', 'N/A')}\n"
                    f"🏠 Кабінет: {next_lesson.get('room', 'N/A')}")
            await query.edit_message_text(text, reply_markup=tomorrow_nav_keyboard, parse_mode='Markdown')
        else:
            await query.edit_message_text("📅 Сьогодні більше пар немає! 🎉", reply_markup=no_more_lessons_keyboard, parse_mode='Markdown')
    # Інші швидкі дії, що не редагують повідомлення, а надсилають нове
    elif action == "quick_game":
        await game_start(update, context)
    elif action == "quick_setgroup":
        message = await query.message.reply_text("⚙️ Для встановлення групи використай команду /setgroup.")
        schedule_message_deletion(message, context, 60)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє натискання кнопки "Меню" або "Назад до меню".
    
    Завжди показує головне меню, оновлюючи поточне повідомлення.
    """
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    chat_id = str(query.message.chat.id)
    is_group = query.message.chat.type in ['group', 'supergroup']

    if is_group:
        default_group = group_chats_data.get(chat_id, {}).get("default_group")
        menu_text = f"🎯 *Меню групи*\n👥 Група: *{default_group}*" if default_group else "🎯 *Меню групи*\n⚠️ Розклад не встановлено"
    else:
        user_group = users_data.get(user_id, {}).get("group")
        menu_text = f"🎯 *Головне меню*\n👤 Група: *{user_group}*" if user_group else "🎯 *Головне меню*\n⚠️ Група не встановлена"

    reply_markup = get_main_menu_keyboard(user_id, chat_id, is_group)
    await query.edit_message_text(
        text=menu_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
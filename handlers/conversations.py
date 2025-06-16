# -*- coding: utf-8 -*-
"""
Обробники діалогів (ConversationHandler).

Цей модуль реалізує покрокові взаємодії з користувачем,
такі як встановлення групи, гра або налаштування часу сповіщень.
Кожен діалог — це скінченний автомат зі своїми станами та переходами.
"""

import logging
import random
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_manager import users_data, schedule_data, save_users_data
from keyboards import get_admin_group_selection_keyboard
from handlers.utils import schedule_message_deletion

logger = logging.getLogger(__name__)

# --- Визначення станів діалогів ---
# Кожен стан - це просто унікальне ціле число.
# Використання `range` - зручний спосіб гарантувати їх унікальність.
CHOOSING_GROUP, GUESSING_NUMBER, SETTING_REMINDER_TIME = range(3)

# --- Діалог встановлення групи ---

async def set_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Починає діалог вибору групи.
    
    Надсилає користувачу клавіатуру з доступними групами.
    Переводить діалог у стан CHOOSING_GROUP.
    """
    if not schedule_data.get("groups", {}):
        message = await update.message.reply_text("На жаль, наразі немає доступних груп.")
        schedule_message_deletion(message, context, 60)
        return ConversationHandler.END

    groups = list(schedule_data.get("groups", {}).keys())
    keyboard = []
    # Розбивка кнопок по дві в ряду
    for i in range(0, len(groups), 2):
        row = [InlineKeyboardButton(group, callback_data=f"conv_group_{group}") for group in groups[i:i+2]]
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ Скасувати", callback_data="conv_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Логіка для обробки як команди, так і натискання на inline-кнопку
    if update.callback_query:
        message = await update.callback_query.message.edit_text("Будь ласка, вибери свою групу:", reply_markup=reply_markup)
    else:
        message = await update.message.reply_text("Будь ласка, вибери свою групу:", reply_markup=reply_markup)
    
    # Повідомлення з вибором буде видалено через 20 хвилин
    schedule_message_deletion(message, context)
    return CHOOSING_GROUP


async def group_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробляє вибір групи, зберігає результат та завершує діалог.
    
    Активується при натисканні на кнопку з назвою групи.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    # Видобуття назви групи з `callback_data` (напр., "conv_group_НТ-24-01")
    chosen_group = query.data.split('_')[-1]
    
    keyboard = [[InlineKeyboardButton("🎯 Показати меню", callback_data="show_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if chosen_group in schedule_data.get("groups", {}):
        # Оновлення або створення запису для користувача
        if user_id not in users_data:
             users_data[user_id] = {"first_name": query.from_user.first_name, "username": query.from_user.username}
        users_data[user_id]["group"] = chosen_group
        save_users_data()
        message = await query.edit_message_text(f"Чудово! Твою групу встановлено як *{chosen_group}*.", reply_markup=reply_markup, parse_mode='Markdown')
    else:
        message = await query.edit_message_text("Такої групи не знайдено. Спробуй ще раз.", reply_markup=reply_markup)
    
    schedule_message_deletion(message, context, 600)
    return ConversationHandler.END


# --- Діалог гри "Вгадай число" ---

async def game_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Починає гру 'Вгадай число'.
    
    Загадує число, зберігає його в `context.user_data` і переводить діалог
    у стан GUESSING_NUMBER. `user_data` - це словник, унікальний для кожного
    користувача в рамках одного діалогу.
    """
    keyboard = [[InlineKeyboardButton("❌ Скасувати гру", callback_data="conv_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        message = await update.callback_query.message.edit_text(
            "Я загадав число від 1 до 100. Спробуй вгадати!",
            reply_markup=reply_markup
        )
    else:
        message = await update.message.reply_text(
            "Я загадав число від 1 до 100. Спробуй вгадати!",
            reply_markup=reply_markup
        )
    schedule_message_deletion(message, context)

    # Ініціалізація даних гри
    context.user_data['secret_number'] = random.randint(1, 100)
    context.user_data['attempts'] = 0
    return GUESSING_NUMBER


async def game_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробляє спробу користувача вгадати число.
    
    Залишається у стані GUESSING_NUMBER доти, доки користувач не вгадає число.
    Після успішного вгадування оновлює найкращий результат та завершує діалог.
    """
    user_id = str(update.effective_user.id)
    try:
        guess = int(update.message.text)
        context.user_data['attempts'] += 1
        secret_number = context.user_data['secret_number']

        if guess < secret_number:
            message = await update.message.reply_text("Більше!")
            schedule_message_deletion(message, context, 15)
            return GUESSING_NUMBER # Залишаємось у тому ж стані
        elif guess > secret_number:
            message = await update.message.reply_text("Менше!")
            schedule_message_deletion(message, context, 15)
            return GUESSING_NUMBER # Залишаємось у тому ж стані
        else:
            # --- Успішне вгадування ---
            attempts = context.user_data['attempts']
            best_score = users_data.get(user_id, {}).get("best_score")
            reply_text = f"🎉 Вітаю! Ти вгадав число {secret_number} за {attempts} спроб!"
            
            # Оновлення рекорду
            if best_score is None or attempts < best_score:
                users_data[user_id]["best_score"] = attempts
                save_users_data()
                reply_text += "\nЦе твій новий найкращий результат!"
            
            keyboard = [
                [InlineKeyboardButton("🎮 Зіграти ще раз", callback_data="quick_game")],
                [InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await update.message.reply_text(reply_text, reply_markup=reply_markup)
            schedule_message_deletion(message, context)
            context.user_data.clear() # Очищення даних гри
            return ConversationHandler.END # Завершення діалогу
    except (ValueError, KeyError):
        message = await update.message.reply_text("Будь ласка, введи число.")
        schedule_message_deletion(message, context)
        return GUESSING_NUMBER


# --- Діалог налаштування часу нагадувань ---

async def set_reminder_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Починає діалог встановлення часу нагадувань."""
    keyboard = [[InlineKeyboardButton("❌ Скасувати", callback_data="conv_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        message = await update.callback_query.message.edit_text(
            "Введи час для щоденного нагадування у форматі *HH:MM* (наприклад, 20:30):",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        message = await update.message.reply_text(
            "Введи час для щоденного нагадування у форматі *HH:MM* (наприклад, 20:30):",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    schedule_message_deletion(message, context)
    return SETTING_REMINDER_TIME


async def reminder_time_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробляє введений час, валідує його та зберігає.
    
    Якщо формат часу невірний, просить користувача ввести його знову,
    залишаючись у тому ж стані.
    """
    user_id = str(update.effective_user.id)
    time_text = update.message.text
    try:
        # Валідація формату часу HH:MM
        datetime.strptime(time_text, "%H:%M")
        if user_id not in users_data:
            users_data[user_id] = {}
        users_data[user_id]["reminder_time"] = time_text
        save_users_data()
        
        keyboard = [[InlineKeyboardButton("🔔 Назад до нагадувань", callback_data="quick_reminders")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await update.message.reply_text(f"✅ Час нагадування встановлено на {time_text}!", reply_markup=reply_markup)
        schedule_message_deletion(message, context)
    except ValueError:
        message = await update.message.reply_text("❌ Неправильний формат. Будь ласка, введи час у форматі *HH:MM*", parse_mode='Markdown')
        schedule_message_deletion(message, context, 60)
        return SETTING_REMINDER_TIME # Просимо ввести час знову
        
    return ConversationHandler.END


# --- Завершення діалогів ---

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Універсальна функція для скасування будь-якого діалогу.
    
    Прив'язана до кнопок скасування у всіх діалогах.
    Очищує `user_data` та завершує діалог.
    """
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("🎯 Показати меню", callback_data="show_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.answer()
        message = await query.edit_message_text("Дію скасовано.", reply_markup=reply_markup)
    else:
        message = await update.message.reply_text("Дію скасовано.", reply_markup=reply_markup)
    
    schedule_message_deletion(message, context, 60)
    context.user_data.clear()
    return ConversationHandler.END 
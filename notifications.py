# -*- coding: utf-8 -*-
"""
Модуль для надсилання запланованих сповіщень.

Містить функції, які виконуються через `JobQueue` для інформування
користувачів про розклад та наступні пари.
"""

import logging
import pytz
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from config import TIMEZONE, DAYS_UA, LESSON_TIMES
from data_manager import (
    users_data, group_chats_data, save_users_data, 
    schedule_data, schedule_start_date, save_group_chat_data
)
from schedule_logic import get_current_week, get_day_schedule, format_schedule_text
from handlers.utils import schedule_message_deletion

logger = logging.getLogger(__name__)


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Надсилає щоденні персональні нагадування про розклад на завтра.
    
    Запускається щохвилини, перевіряє налаштування кожного користувача.
    Сповіщення надсилається, якщо увімкнені нагадування (`daily_reminder`)
    і поточний час збігається з часом, вказаним користувачем (`reminder_time`).
    """
    # Отримання поточного часу у форматі HH:MM для порівняння
    current_time = datetime.now(pytz.timezone(TIMEZONE)).strftime("%H:%M")
    
    for user_id, user_data in users_data.items():
        # Перевірка, чи потрібно надсилати нагадування цьому користувачеві
        if (user_data.get("daily_reminder", False) and 
            user_data.get("reminder_time") == current_time and
            user_data.get("group")):
            
            try:
                # Отримуємо розклад на завтра
                tomorrow = datetime.now(pytz.timezone(TIMEZONE)) + timedelta(days=1)
                day_name = DAYS_UA.get(tomorrow.weekday())
                
                if day_name and day_name in schedule_data.get("groups", {}).get(user_data["group"], {}).get("schedule", {}):
                    # Розрахунок тижня для завтрашнього дня
                    tomorrow_week = get_current_week(tomorrow)
                    
                    lessons = get_day_schedule(user_data["group"], day_name, tomorrow_week)
                    
                    # Формування та відправка повідомлення
                    if lessons:
                        reminder_text = f"🔔 *Нагадування*\n\n"
                        reminder_text += format_schedule_text(user_data["group"], day_name, lessons, tomorrow_week)
                        
                        message = await context.bot.send_message(
                            chat_id=user_id,
                            text=reminder_text,
                            parse_mode='Markdown'
                        )
                        # Повідомлення видаляється через 12 годин
                        schedule_message_deletion(message, context, delay_seconds=12 * 3600)
                    else:
                        message = await context.bot.send_message(
                            chat_id=user_id,
                            text="🔔 *Нагадування*\n\nЗавтра пар немає! Можна відпочивати 😊",
                            parse_mode='Markdown'
                        )
                        schedule_message_deletion(message, context, delay_seconds=12 * 3600)
                else:
                    # Обробка випадку, коли на завтра немає розкладу (напр. неділя)
                    message = await context.bot.send_message(
                        chat_id=user_id,
                        text="🔔 *Нагадування*\n\nЗавтра пар немає! Можна відпочивати 😊",
                        parse_mode='Markdown'
                    )
                    schedule_message_deletion(message, context, delay_seconds=12 * 3600)
            except Exception as e:
                logger.error(f"Помилка надсилання нагадування користувачу {user_id}: {e}")

async def send_morning_schedule(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Надсилає щоденний розклад у всі групові чати о 7:00.
    
    Перед надсиланням нового повідомлення, відкріплює та видаляє старе.
    Нове повідомлення закріплюється, а його ID зберігається.
    """
    logger.info("Запуск ранкової розсилки розкладу для групових чатів...")
    today = datetime.now(pytz.timezone(TIMEZONE))
    day_name = DAYS_UA.get(today.weekday())

    # Не відправляти у неділю
    if not day_name or today.weekday() == 6:
        logger.info(f"Сьогодні {day_name}, ранковий розклад не надсилається.")
        return

    week = get_current_week()

    # Ітерація по всіх зареєстрованих групових чатах
    for chat_id, chat_info in group_chats_data.items():
        group_name = chat_info.get("default_group")
        
        if not group_name:
            logger.warning(f"Для чату {chat_id} не встановлено групу за замовчуванням, пропуск.")
            continue
            
        try:
            # --- Видалення та відкріплення старого повідомлення ---
            pinned_message_id = chat_info.get("pinned_schedule_message_id")
            if pinned_message_id:
                try:
                    await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_message_id)
                    await context.bot.delete_message(chat_id=chat_id, message_id=pinned_message_id)
                    logger.info(f"Старе закріплене повідомлення {pinned_message_id} видалено з чату {chat_id}.")
                except BadRequest as e:
                    # Помилка може виникнути, якщо повідомлення вже видалено або бот не має прав.
                    logger.warning(f"Не вдалося видалити/відкріпити повідомлення {pinned_message_id} в чаті {chat_id}: {e}")
                
            lessons = get_day_schedule(group_name, day_name, week)
            
            # Якщо сьогодні пар немає, надсилаємо відповідне повідомлення і не закріплюємо його.
            if not lessons:
                message = await context.bot.send_message(
                    chat_id=chat_id, 
                    text=f"*{day_name.capitalize()}*\n\nСьогодні пар для групи *{group_name}* немає! 🎉",
                    parse_mode='Markdown'
                )
                logger.info(f"Для групи {group_name} на {day_name} немає пар, надіслано інформаційне повідомлення в чат {chat_id}.")
                # Видаляємо старий ID, оскільки нового закріпленого повідомлення немає
                if "pinned_schedule_message_id" in chat_info:
                    del chat_info["pinned_schedule_message_id"]
                continue

            schedule_text = format_schedule_text(group_name, day_name, lessons, week)
            
            # Створення клавіатури для швидкої навігації
            keyboard = [
                [InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
                 InlineKeyboardButton("📚 Розклад", callback_data="quick_schedule")],
                [InlineKeyboardButton("📊 Тиждень", callback_data="quick_week"),
                 InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            new_message = await context.bot.send_message(
                chat_id=chat_id, 
                text=schedule_text,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_notification=True # Щоб уникнути подвійного сповіщення (відправка + пін)
            )
            
            # --- Закріплення нового повідомлення та збереження його ID ---
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=new_message.message_id, disable_notification=False)
            chat_info["pinned_schedule_message_id"] = new_message.message_id
            save_group_chat_data()
            
            logger.info(f"Надіслано та закріплено новий розклад в чаті {chat_id} для групи {group_name}. Message ID: {new_message.message_id}")

        except Exception as e:
            logger.error(f"Не вдалося надіслати ранковий розклад в чат {chat_id}: {e}")


async def send_next_lesson_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Надсилає сповіщення про наступну пару.
    
    Запускається щохвилини. Тригером для відправки є час закінчення поточної пари.
    Сповіщення надсилається як в особисті чати (якщо увімкнено), так і в групові.
    """
    logger.info("Запуск перевірки для сповіщення про наступну пару...")
    today = datetime.now(pytz.timezone(TIMEZONE))
    current_time = today.strftime('%H:%M')
    day_name = DAYS_UA.get(today.weekday())

    # Словник з часом закінчення пар, що є тригером для сповіщення
    lesson_end_times = {
        1: "09:20", 2: "10:50", 3: "12:30", 4: "14:00",
        5: "15:30", 6: "17:00", 7: "18:30", 8: "20:00"
    }
    
    # Вихід, якщо зараз не час для сповіщення
    if not day_name or current_time not in lesson_end_times.values():
        return

    current_lesson_num = next((num for num, time in lesson_end_times.items() if time == current_time), None)
    if not current_lesson_num:
        return
        
    week = get_current_week()

    # --- Обробка особистих чатів ---
    for user_id, user_data in users_data.items():
        # Перевірка, чи користувач увімкнув сповіщення та вказав групу
        if not user_data.get("lesson_notifications", True) or not user_data.get("group"):
            continue

        lessons_today = get_day_schedule(user_data["group"], day_name, week)
        if not lessons_today:
            continue

        # Пошук наступної пари
        next_lesson = next((l for l in lessons_today if l['pair'] > current_lesson_num), None)
        
        try:
            keyboard = [[InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if next_lesson:
                lesson_time = LESSON_TIMES.get(next_lesson['pair'], ("??:??",))[0]
                notification_text = (
                    f"🔔 *Наступна пара* (через 10 хв):\n\n"
                    f"🕐 Час: {lesson_time}\n"
                    f"📚 Предмет: {next_lesson['name']}\n"
                    f"👨‍🏫 Викладач: {next_lesson.get('teacher', 'N/A')}\n"
                    f"🏠 Кабінет: {next_lesson.get('room', 'N/A')}"
                )
                message = await context.bot.send_message(
                    chat_id=user_id, text=notification_text, 
                    reply_markup=reply_markup, parse_mode='Markdown'
                )
                schedule_message_deletion(message, context)
            else:
                # Сповіщення про кінець пар
                message = await context.bot.send_message(
                    chat_id=user_id, text="🎉 *Це була остання пара на сьогодні!*\n\nГарного дня! 😊",
                    reply_markup=reply_markup, parse_mode='Markdown'
                )
                schedule_message_deletion(message, context)
        except Exception as e:
            logger.error(f"Не вдалося надіслати сповіщення про наступну пару користувачу {user_id}: {e}")

    # --- Обробка групових чатів ---
    for chat_id, chat_info in group_chats_data.items():
        group_name = chat_info.get("default_group")
        if not group_name:
            continue

        lessons_today = get_day_schedule(group_name, day_name, week)
        if not lessons_today:
            continue

        next_lesson = next((l for l in lessons_today if l['pair'] > current_lesson_num), None)

        try:
            keyboard = [[InlineKeyboardButton("🎯 Меню", callback_data="show_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if next_lesson:
                lesson_time = LESSON_TIMES.get(next_lesson['pair'], ("??:??",))[0]
                notification_text = (
                    f"🔔 *Наступна пара* (через 10 хв):\n\n"
                    f"🕐 Час: {lesson_time}\n"
                    f"📚 Предмет: {next_lesson['name']}\n"
                    f"👨‍🏫 Викладач: {next_lesson.get('teacher', 'N/A')}\n"
                    f"🏠 Кабінет: {next_lesson.get('room', 'N/A')}"
                )
                message = await context.bot.send_message(
                    chat_id=chat_id, text=notification_text, 
                    reply_markup=reply_markup, parse_mode='Markdown'
                )
                schedule_message_deletion(message, context)
            else:
                message = await context.bot.send_message(
                    chat_id=chat_id, text="🎉 *Це була остання пара на сьогодні!*\n\nГарного дня всім! 😊",
                    reply_markup=reply_markup, parse_mode='Markdown'
                )
                schedule_message_deletion(message, context)
        except Exception as e:
            logger.error(f"Не вдалося надіслати сповіщення про наступну пару в чат {chat_id}: {e}") 
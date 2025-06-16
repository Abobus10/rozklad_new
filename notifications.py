# -*- coding: utf-8 -*-
"""
Сервіс сповіщень Telegram-бота.

Сучасна архітектура з типізацією, валідацією та структурованим логуванням.
Відповідає за надсилання запланованих сповіщень користувачам.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

import pytz
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, TelegramError, Forbidden

from config import config, DAYS_UA, LESSON_TIMES
from data_manager import data_manager
from schedule_logic import schedule_service
from handlers.utils import schedule_message_deletion
from logger_config import LoggerMixin


class NotificationService(LoggerMixin):
    """Сервіс для керування сповіщеннями бота."""
    
    def __init__(self):
        """Ініціалізація сервісу сповіщень."""
        self.timezone = pytz.timezone(config.timezone)
        self.logger.info("Ініціалізація сервісу сповіщень")

    async def handle_telegram_error(self, user_id: str, error: TelegramError, context: str) -> bool:
        """
        Обробляє помилки Telegram API.
        
        Args:
            user_id: ID користувача
            error: Помилка Telegram
            context: Контекст помилки
            
        Returns:
            True, якщо користувача потрібно видалити з активних
        """
        error_msg = str(error)
        
        if isinstance(error, Forbidden):
            self.logger.warning(f"Користувач {user_id} заблокував бота: {error_msg}")
            # Деактивуємо користувача замість видалення
            data_manager.update_user(user_id, {"active": False})
            return True
        elif "chat not found" in error_msg.lower():
            self.logger.warning(f"Чат {user_id} не знайдено: {error_msg}")
            return True
        else:
            self.logger.error(f"Помилка надсилання сповіщення в {context} для {user_id}: {error_msg}")
            return False

    def _get_current_time(self) -> datetime:
        """Отримує поточний час у потрібній timezone."""
        return datetime.now(self.timezone)

    def _format_time(self, dt: datetime) -> str:
        """Форматує час у рядок HH:MM."""
        return dt.strftime("%H:%M")

    def _get_tomorrow_info(self) -> Tuple[datetime, Optional[str]]:
        """
        Отримує інформацію про завтрашній день.
        
        Returns:
            Кортеж (дата_завтра, назва_дня)
        """
        tomorrow = self._get_current_time() + timedelta(days=1)
        day_name = DAYS_UA.get(tomorrow.weekday())
        return tomorrow, day_name

    async def send_daily_reminders(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Надсилає щоденні персональні нагадування про розклад на завтра.
        
        Запускається щохвилини, перевіряє налаштування кожного користувача.
        """
        current_time = self._format_time(self._get_current_time())
        tomorrow, day_name = self._get_tomorrow_info()
        
        self.logger.debug(f"Перевірка щоденних нагадувань на {current_time}")
        
        # Отримуємо користувачів, яким потрібно надіслати нагадування
        users_to_notify = self._get_users_for_daily_reminder(current_time)
        
        if not users_to_notify:
            return
        
        self.logger.info(f"Надсилання щоденних нагадувань {len(users_to_notify)} користувачам")
        
        # Обмежуємо кількість одночасних сповіщень
        semaphore = asyncio.Semaphore(config.max_concurrent_notifications)
        
        tasks = [
            self._send_daily_reminder_to_user(context, user_id, user_data, tomorrow, day_name, semaphore)
            for user_id, user_data in users_to_notify.items()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)

    def _get_users_for_daily_reminder(self, current_time: str) -> Dict[str, Any]:
        """
        Отримує список користувачів для надсилання щоденних нагадувань.
        
        Args:
            current_time: Поточний час у форматі HH:MM
            
        Returns:
            Словник користувачів {user_id: user_data}
        """
        all_users = data_manager.get_all_users_data()
        
        return {
            user_id: user_data
            for user_id, user_data in all_users.items()
            if (
                user_data.get("daily_reminder", False) and 
                user_data.get("reminder_time") == current_time and
                user_data.get("group") and
                user_data.get("active", True)  # Перевіряємо, чи активний користувач
            )
        }

    async def _send_daily_reminder_to_user(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        user_id: str, 
        user_data: Dict[str, Any],
        tomorrow: datetime, 
        day_name: Optional[str],
        semaphore: asyncio.Semaphore
    ) -> None:
        """
        Надсилає щоденне нагадування одному користувачеві.
        
        Args:
            context: Контекст Telegram
            user_id: ID користувача
            user_data: Дані користувача
            tomorrow: Дата завтра
            day_name: Назва дня завтра
            semaphore: Семафор для обмеження конкурентності
        """
        async with semaphore:
            try:
                user_group = user_data["group"]
                
                if not day_name:
                    # Завтра вихідний
                    message_text = "🔔 *Нагадування*\n\nЗавтра вихідний! Можна відпочивати 😊"
                    await self._send_simple_reminder(context, user_id, message_text)
                    return
                
                # Перевіряємо, чи є розклад на завтра
                tomorrow_week = schedule_service.get_current_week(tomorrow)
                lessons = schedule_service.get_day_schedule(user_group, day_name, tomorrow_week)
                
                if lessons:
                    schedule_text = schedule_service.format_schedule_text(user_group, day_name, lessons, tomorrow_week)
                    message_text = f"🔔 *Нагадування*\n\n{schedule_text}"
                else:
                    message_text = "🔔 *Нагадування*\n\nЗавтра пар немає! Можна відпочивати 😊"
                
                await self._send_simple_reminder(context, user_id, message_text)
                
            except Exception as e:
                self.logger.error(f"Помилка надсилання щоденного нагадування користувачеві {user_id}: {e}")

    async def _send_simple_reminder(self, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str) -> None:
        """
        Надсилає просте нагадування користувачеві.
        
        Args:
            context: Контекст Telegram
            user_id: ID користувача
            text: Текст повідомлення
        """
        try:
            message = await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='Markdown'
            )
            
            # Плануємо видалення повідомлення через 12 годин
            schedule_message_deletion(message, context, delay_seconds=12 * 3600)
            
        except TelegramError as e:
            await self.handle_telegram_error(user_id, e, "daily_reminder")

    async def send_morning_schedule(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Надсилає ранковий розклад у всі групові чати о 7:00.
        
        Перед надсиланням нового повідомлення відкріплює та видаляє старе.
        """
        self.logger.info("Запуск ранкової розсилки розкладу для групових чатів")
        
        today = self._get_current_time()
        day_name = DAYS_UA.get(today.weekday())

        # Не надсилаємо в неділю
        if not day_name or today.weekday() == 6:
            self.logger.info(f"Сьогодні {day_name or 'неділя'}, ранковий розклад не надсилається")
            return

        week = schedule_service.get_current_week()
        group_chats = data_manager.get_all_group_chats()
        
        if not group_chats:
            self.logger.info("Немає зареєстрованих групових чатів")
            return
        
        # Обмежуємо кількість одночасних відправлень
        semaphore = asyncio.Semaphore(config.max_concurrent_notifications)
        
        tasks = [
            self._send_morning_schedule_to_chat(context, chat_id, chat_info, day_name, week, semaphore)
            for chat_id, chat_info in group_chats.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if result is True)
        self.logger.info(f"Ранковий розклад надіслано в {success_count} з {len(group_chats)} чатів")

    async def _send_morning_schedule_to_chat(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: str, 
        chat_info: Dict[str, Any],
        day_name: str, 
        week: int,
        semaphore: asyncio.Semaphore
    ) -> bool:
        """
        Надсилає ранковий розклад в один груповий чат.
        
        Returns:
            True, якщо відправка пройшла успішно
        """
        async with semaphore:
            try:
                group_name = chat_info.get("default_group")
                
                if not group_name:
                    self.logger.warning(f"Для чата {chat_id} не установлена группа по умолчанию")
                    return False
                
                # Удаляем старое закрепленное сообщение
                await self._remove_old_pinned_message(context, chat_id, chat_info)
                
                # Получаем расписание на сегодня
                lessons = schedule_service.get_day_schedule(group_name, day_name, week)
                
                if not lessons:
                    await self._send_no_lessons_message(context, chat_id, chat_info, group_name, day_name)
                    return True
                
                # Отправляем новое расписание
                await self._send_schedule_message(context, chat_id, chat_info, group_name, day_name, lessons, week)
                return True
                
            except Exception as e:
                self.logger.error(f"Ошибка отправки утреннего расписания в чат {chat_id}: {e}")
                return False

    async def _remove_old_pinned_message(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: str, 
        chat_info: Dict[str, Any]
    ) -> None:
        """Удаляет старое закрепленное сообщение."""
        pinned_message_id = chat_info.get("pinned_schedule_message_id")
        
        if not pinned_message_id:
            return
        
        try:
            await context.bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_message_id)
            await context.bot.delete_message(chat_id=chat_id, message_id=pinned_message_id)
            self.logger.debug(f"Старое сообщение {pinned_message_id} удалено из чата {chat_id}")
            
        except BadRequest as e:
            self.logger.warning(f"Не удалось удалить старое сообщение {pinned_message_id} в чате {chat_id}: {e}")

    async def _send_no_lessons_message(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: str, 
        chat_info: Dict[str, Any],
        group_name: str, 
        day_name: str
    ) -> None:
        """Отправляет сообщение об отсутствии пар."""
        message_text = f"*{day_name.capitalize()}*\n\nСегодня пар для группы *{group_name}* нет! 🎉"
        
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='Markdown'
        )
        
        # Удаляем ID старого закрепленного сообщения
        if "pinned_schedule_message_id" in chat_info:
            del chat_info["pinned_schedule_message_id"]
            data_manager.save_group_chat_data()
        
        self.logger.info(f"Для группы {group_name} на {day_name} нет пар, отправлено уведомление в чат {chat_id}")

    async def _send_schedule_message(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: str, 
        chat_info: Dict[str, Any],
        group_name: str, 
        day_name: str, 
        lessons: List[Dict[str, Any]], 
        week: int
    ) -> None:
        """Отправляет сообщение с расписанием."""
        schedule_text = schedule_service.format_schedule_text(group_name, day_name, lessons, week)
        
        # Создаем клавиатуру для быстрой навигации
        keyboard = [
            [
                InlineKeyboardButton("📅 Завтра", callback_data="quick_tomorrow"),
                InlineKeyboardButton("📚 Расписание", callback_data="quick_schedule")
            ],
            [
                InlineKeyboardButton("📊 Неделя", callback_data="quick_week"),
                InlineKeyboardButton("🎯 Меню", callback_data="show_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        new_message = await context.bot.send_message(
            chat_id=chat_id,
            text=schedule_text,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_notification=True  # Избегаем двойного уведомления
        )
        
        # Закрепляем новое сообщение
        await context.bot.pin_chat_message(
            chat_id=chat_id, 
            message_id=new_message.message_id, 
            disable_notification=False
        )
        
        # Сохраняем ID нового сообщения
        chat_info["pinned_schedule_message_id"] = new_message.message_id
        data_manager.update_group_chat(chat_id, chat_info)
        
        self.logger.info(
            f"Отправлено и закреплено расписание в чате {chat_id} для группы {group_name}. "
            f"Message ID: {new_message.message_id}"
        )

    async def send_next_lesson_notifications(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Отправляет уведомления о следующей паре.
        
        Запускается каждую минуту. Триггером служит время окончания текущей пары.
        """
        current_time = self._format_time(self._get_current_time())
        today = self._get_current_time()
        day_name = DAYS_UA.get(today.weekday())

        # Определяем времена окончания пар
        lesson_end_times = {pair: end_time for pair, (_, end_time) in LESSON_TIMES.items()}
        
        # Проверяем, является ли текущее время временем окончания какой-либо пары
        if not day_name or current_time not in lesson_end_times.values():
            return

        current_lesson_num = next(
            (num for num, time in lesson_end_times.items() if time == current_time), 
            None
        )
        
        if not current_lesson_num:
            return
        
        self.logger.info(f"Отправка уведомлений о следующей паре (после {current_lesson_num} пары)")
        
        week = schedule_service.get_current_week()
        
        # Отправляем уведомления в личные чаты и групповые чаты параллельно
        await asyncio.gather(
            self._send_personal_next_lesson_notifications(context, day_name, week, current_lesson_num),
            self._send_group_next_lesson_notifications(context, day_name, week, current_lesson_num),
            return_exceptions=True
        )

    async def _send_personal_next_lesson_notifications(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        day_name: str, 
        week: int, 
        current_lesson_num: int
    ) -> None:
        """Отправляет уведомления о следующей паре в личные чаты."""
        users_data = data_manager.get_all_users_data()
        
        # Фильтруем пользователей, которым нужно отправить уведомление
        users_to_notify = {
            user_id: user_data
            for user_id, user_data in users_data.items()
            if (
                user_data.get("lesson_notifications", True) and
                user_data.get("group") and
                user_data.get("active", True)
            )
        }
        
        if not users_to_notify:
            return
        
        semaphore = asyncio.Semaphore(config.max_concurrent_notifications)
        
        tasks = [
            self._send_next_lesson_to_user(context, user_id, user_data, day_name, week, current_lesson_num, semaphore)
            for user_id, user_data in users_to_notify.items()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_next_lesson_to_user(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        user_id: str, 
        user_data: Dict[str, Any],
        day_name: str, 
        week: int, 
        current_lesson_num: int,
        semaphore: asyncio.Semaphore
    ) -> None:
        """Отправляет уведомление о следующей паре одному пользователю."""
        async with semaphore:
            try:
                user_group = user_data["group"]
                lessons_today = schedule_service.get_day_schedule(user_group, day_name, week)
                
                next_lesson = self._find_next_lesson(lessons_today, current_lesson_num)
                
                if next_lesson:
                    message_text = self._format_next_lesson_message(next_lesson)
                else:
                    message_text = (
                        "🔔 *Уведомление*\n\n"
                        "📚 Сегодня больше пар нет!\n"
                        "Можно отдыхать! 😴"
                    )
                
                await self._send_simple_reminder(context, user_id, message_text)
                
            except Exception as e:
                self.logger.error(f"Ошибка отправки уведомления о следующей паре пользователю {user_id}: {e}")

    def _find_next_lesson(self, lessons: List[Dict[str, Any]], current_lesson_num: int) -> Optional[Dict[str, Any]]:
        """
        Находит следующую пару после указанной.
        
        Args:
            lessons: Список пар на день
            current_lesson_num: Номер текущей завершившейся пары
            
        Returns:
            Следующая пара или None
        """
        return next(
            (lesson for lesson in lessons if lesson['pair'] > current_lesson_num),
            None
        )

    def _format_next_lesson_message(self, lesson: Dict[str, Any]) -> str:
        """
        Форматирует сообщение о следующей паре.
        
        Args:
            lesson: Данные о паре
            
        Returns:
            Отформатированное сообщение
        """
        time_start, time_end = LESSON_TIMES.get(lesson['pair'], ("??:??", "??:??"))
        
        return (
            f"🔔 *Уведомление о следующей паре*\n\n"
            f"🕐 Время: {time_start} - {time_end}\n"
            f"📚 Предмет: {lesson['name']}\n"
            f"👨‍🏫 Преподаватель: {lesson.get('teacher', 'Не указан')}\n"
            f"🏠 Кабинет: {lesson.get('room', 'Не указан')}"
        )

    async def _send_group_next_lesson_notifications(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        day_name: str, 
        week: int, 
        current_lesson_num: int
    ) -> None:
        """Отправляет уведомления о следующей паре в групповые чаты."""
        group_chats = data_manager.get_all_group_chats()
        
        if not group_chats:
            return
        
        semaphore = asyncio.Semaphore(config.max_concurrent_notifications)
        
        tasks = [
            self._send_next_lesson_to_group(context, chat_id, chat_info, day_name, week, current_lesson_num, semaphore)
            for chat_id, chat_info in group_chats.items()
            if chat_info.get("default_group")
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_next_lesson_to_group(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        chat_id: str, 
        chat_info: Dict[str, Any],
        day_name: str, 
        week: int, 
        current_lesson_num: int,
        semaphore: asyncio.Semaphore
    ) -> None:
        """Отправляет уведомление о следующей паре в групповой чат."""
        async with semaphore:
            try:
                group_name = chat_info["default_group"]
                lessons_today = schedule_service.get_day_schedule(group_name, day_name, week)
                
                next_lesson = self._find_next_lesson(lessons_today, current_lesson_num)
                
                if next_lesson:
                    message_text = self._format_next_lesson_message(next_lesson)
                else:
                    message_text = (
                        "🔔 *Уведомление*\n\n"
                        "📚 Сегодня больше пар нет!\n"
                        "Можно отдыхать! 😴"
                    )
                
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode='Markdown'
                )
                
                # Планируем удаление через 2 часа
                schedule_message_deletion(message, context, delay_seconds=2 * 3600)
                
            except TelegramError as e:
                await self.handle_telegram_error(chat_id, e, "group_next_lesson")
            except Exception as e:
                self.logger.error(f"Ошибка отправки уведомления о следующей паре в группу {chat_id}: {e}")


# Создаем глобальный экземпляр сервиса
notification_service = NotificationService()

# Экспортируем функции для обратной совместимости
send_daily_reminders = notification_service.send_daily_reminders
send_morning_schedule = notification_service.send_morning_schedule
send_next_lesson_notifications = notification_service.send_next_lesson_notifications 
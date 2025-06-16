# -*- coding: utf-8 -*-
"""
Обработчики команд Telegram бота.

Современная архитектура с типизацией, валидацией и структурированным логированием.
Использует принципы чистого кода и хорошие практики Python разработки.
"""

from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TelegramError

from config import config, DAYS_UA, LESSON_TIMES
from data_manager import data_manager
from schedule_logic import schedule_service
from keyboards import (
    get_main_menu_keyboard, get_schedule_day_keyboard, get_reminders_keyboard,
    get_admin_group_selection_keyboard,
    quick_nav_keyboard, tomorrow_nav_keyboard, next_lesson_nav_keyboard,
    no_more_lessons_keyboard
)
from handlers.utils import get_fact, schedule_message_deletion, admin_only
from notifications import send_morning_schedule
from logger_config import LoggerMixin


class CommandHandlers(LoggerMixin):
    """Класс для обработки команд бота с современной архитектурой."""
    
    def __init__(self):
        """Инициализация обработчиков команд."""
        self.logger.info("Инициализация обработчиков команд")

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, error_msg: str) -> None:
        """
        Централизованная обработка ошибок.
        
        Args:
            update: Обновление Telegram
            context: Контекст выполнения
            error_msg: Сообщение об ошибке
        """
        self.logger.error(f"Ошибка в команде: {error_msg}")
        
        try:
            if update.message:
                await update.message.reply_text(
                    "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору.",
                    parse_mode='Markdown'
                )
        except TelegramError as e:
            self.logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

    def _get_user_context(self, update: Update) -> tuple[str, str, bool]:
        """
        Получает контекст пользователя и чата.
        
        Args:
            update: Обновление Telegram
            
        Returns:
            Кортеж (user_id, chat_id, is_group)
        """
        user = update.effective_user
        chat = update.effective_chat
        user_id = str(user.id)
        chat_id = str(chat.id)
        is_group = chat.type in ['group', 'supergroup']
        
        return user_id, chat_id, is_group

    @admin_only
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает админ-панель с доступными командами."""
        try:
            admin_help_text = (
                "👑 *Админ-панель*\n\n"
                "Доступные команды:\n"
                "`/stats` - Статистика бота\n"
                "`/broadcast [сообщение]` - Рассылка\n"
                "`/test_schedule` - Тестовая отправка расписания"
            )
            
            message = await update.message.reply_text(
                admin_help_text, 
                parse_mode='Markdown'
            )
            schedule_message_deletion(message, context, 600)
            
        except TelegramError as e:
            await self.handle_error(update, context, f"admin_command: {e}")

    @admin_only
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает статистику использования бота."""
        try:
            total_users = data_manager.get_users_count()
            active_today = data_manager.get_active_users_today()
            total_groups = data_manager.get_groups_count()
            
            stats_text = (
                f"📊 *Статистика бота*\n\n"
                f"👤 Всего пользователей: {total_users}\n"
                f"👥 Групп в расписании: {total_groups}\n"
                f"📈 Активных сегодня: {active_today}"
            )
            
            message = await update.message.reply_text(
                stats_text, 
                parse_mode='Markdown'
            )
            schedule_message_deletion(message, context, 600)
            
        except Exception as e:
            await self.handle_error(update, context, f"stats_command: {e}")

    @admin_only
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Делает рассылку сообщения всем пользователям."""
        try:
            message_to_send = " ".join(context.args)
            if not message_to_send:
                message = await update.message.reply_text(
                    "Пожалуйста, укажите сообщение для рассылки.\n"
                    "Пример: `/broadcast Привет всем!`",
                    parse_mode='Markdown'
                )
                schedule_message_deletion(message, context)
                return

            sent_count, failed_count = 0, 0
            users = data_manager.get_all_users_data()
            
            for user_id in users.keys():
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📢 *Сообщение от администратора:*\n\n{message_to_send}",
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                except TelegramError as e:
                    self.logger.error(f"Не удалось отправить сообщение {user_id}: {e}")
                    failed_count += 1
            
            reply_text = (
                f"📢 Рассылка завершена!\n\n"
                f"✅ Отправлено: {sent_count}\n"
                f"❌ Ошибок: {failed_count}"
            )
            
            message = await update.message.reply_text(reply_text)
            schedule_message_deletion(message, context, 600)
            
        except Exception as e:
            await self.handle_error(update, context, f"broadcast_command: {e}")

    @admin_only
    async def test_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Запускает тестовую отправку утреннего расписания."""
        try:
            await update.message.reply_text("🚀 Запускаю тестовую отправку расписания...")
            await send_morning_schedule(context)
            
            message = await update.message.reply_text("✅ Тестовая отправка завершена.")
            schedule_message_deletion(message, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"test_schedule_command: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Приветствие пользователя.
        
        Регистрирует нового пользователя или приветствует существующего.
        """
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user = update.effective_user
            
            if is_group:
                await self._handle_group_start(update, context, chat_id)
            else:
                await self._handle_private_start(update, context, user_id, user)
                await self.menu_command(update, context)
                
        except Exception as e:
            await self.handle_error(update, context, f"start: {e}")

    async def _handle_group_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str) -> None:
        """Обрабатывает команду /start в групповом чате."""
        chat_title = update.effective_chat.title
        
        # Регистрируем групповой чат
        group_data = data_manager.get_group_chat(chat_id)
        default_group = group_data.default_group if group_data else None
        
        data_manager.update_group_chat(chat_id, {"chat_title": chat_title})
        
        welcome_text = f"👋 Привет, группа *{chat_title}*!\nЯ бот расписания колледжа! 📚\n\n"
        
        if default_group:
            welcome_text += f"✅ Для этого чата установлено расписание группы *{default_group}*.\n"
        else:
            welcome_text += "⚠️ Для этого чата еще не установлено расписание. Администратор может сделать это командой /setgroupschedule.\n"
        
        welcome_text += "\n🎯 Используйте /menu для просмотра доступных действий."
        
        message = await update.message.reply_text(welcome_text, parse_mode='Markdown')
        schedule_message_deletion(message, context)

    async def _handle_private_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   user_id: str, user) -> None:
        """Обрабатывает команду /start в приватном чате."""
        existing_user = data_manager.get_user(user_id)
        
        if not existing_user:
            # Новый пользователь
            data_manager.update_user(
                user_id,
                first_name=user.first_name,
                username=user.username,
                registration_date=datetime.now()
            )
            
            message = await update.message.reply_html(
                f"Привет, {user.mention_html()}! 👋 Рад тебя видеть."
            )
        else:
            # Существующий пользователь
            data_manager.update_user(user_id, first_name=user.first_name, username=user.username)
            
            message = await update.message.reply_html(
                f"С возвращением, {user.first_name}! 👋"
            )
        
        schedule_message_deletion(message, context, 60)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          from_callback: bool = False) -> None:
        """Показывает главное меню с кнопками."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            
            # Формирование текста меню
            menu_text = self._build_menu_text(user_id, chat_id, is_group)
            reply_markup = get_main_menu_keyboard(user_id, chat_id, is_group)
            
            if from_callback:
                query = update.callback_query
                try:
                    await query.edit_message_text(
                        menu_text, 
                        reply_markup=reply_markup, 
                        parse_mode='Markdown'
                    )
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
            else:
                message = await update.message.reply_text(
                    menu_text, 
                    reply_markup=reply_markup, 
                    parse_mode='Markdown'
                )
                schedule_message_deletion(message, context)
                
        except Exception as e:
            await self.handle_error(update, context, f"menu_command: {e}")

    def _build_menu_text(self, user_id: str, chat_id: str, is_group: bool) -> str:
        """Формирует текст для главного меню."""
        
        if is_group:
            group_chat_data = data_manager.get_group_chat(chat_id)
            group_name = group_chat_data.default_group or 'не выбрана'
            
            menu_text = (
                f"📋 *Главное меню для группы*\n"
                f"Текущая группа: *{group_name}*\n\n"
                "Выберите действие:"
            )
        else:
            user_data = data_manager.get_user(user_id)
            group_name = user_data.group if user_data and user_data.group else 'не выбрана'
            
            menu_text = (
                "📋 *Главное меню*\n"
                f"Твоя группа: *{group_name}*\n\n"
                "Чем могу помочь?"
            )
        return menu_text

    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           from_callback: bool = False) -> None:
        """Показывает расписание на сегодня."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)
            
            if not user_group:
                await self._send_no_group_message(update, from_callback)
                return
            
            today = datetime.now()
            day_name = DAYS_UA.get(today.weekday())
            
            if not day_name:
                text = "🗓 Сегодня выходной день!"
                keyboard = quick_nav_keyboard
            else:
                current_week = schedule_service.get_current_week()
                lessons = schedule_service.get_day_schedule(user_group, day_name, current_week)
                
                if lessons:
                    text = schedule_service.format_schedule_text(user_group, day_name, lessons, current_week)
                    keyboard = quick_nav_keyboard
                else:
                    text = f"📅 *{day_name.capitalize()}*\n\nСегодня пар нет! 🎉"
                    keyboard = quick_nav_keyboard
            
            await self._send_or_edit_message(update, text, keyboard, from_callback, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"today_command: {e}")

    async def tomorrow_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              from_callback: bool = False) -> None:
        """Показывает расписание на завтра."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)
            
            if not user_group:
                await self._send_no_group_message(update, from_callback)
                return
            
            tomorrow = datetime.now() + timedelta(days=1)
            day_name = DAYS_UA.get(tomorrow.weekday())
            
            if not day_name:
                text = "🗓 Завтра выходной день!"
                keyboard = tomorrow_nav_keyboard
            else:
                tomorrow_week = schedule_service.get_current_week(tomorrow)
                lessons = schedule_service.get_day_schedule(user_group, day_name, tomorrow_week)
                
                if lessons:
                    text = schedule_service.format_schedule_text(user_group, day_name, lessons, tomorrow_week)
                    keyboard = tomorrow_nav_keyboard
                else:
                    text = f"📅 *{day_name.capitalize()}*\n\nЗавтра пар нет! 🎉"
                    keyboard = tomorrow_nav_keyboard
            
            await self._send_or_edit_message(update, text, keyboard, from_callback, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"tomorrow_command: {e}")

    async def next_lesson_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает информацию о следующей паре."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)
            
            if not user_group:
                await self._send_no_group_message(update, False)
                return
            
            next_lesson_info = schedule_service.get_next_lesson(user_group)
            
            if next_lesson_info:
                text = f"⏰ *Следующая пара*\n\n{next_lesson_info}"
                keyboard = next_lesson_nav_keyboard
            else:
                text = "⏰ *Следующая пара*\n\nБольше пар сегодня нет. Можно отдыхать! 😴"
                keyboard = no_more_lessons_keyboard
            
            message = await update.message.reply_text(
                text, 
                reply_markup=keyboard, 
                parse_mode='Markdown'
            )
            schedule_message_deletion(message, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"next_lesson_command: {e}")

    async def _send_no_group_message(self, update: Update, from_callback: bool) -> None:
        """Отправляет сообщение о необходимости установить группу."""
        keyboard = [[InlineKeyboardButton("⚙️ Установить группу", callback_data="quick_setgroup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "⚠️ Сначала установите группу."
        
        if from_callback:
            query = update.callback_query
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def _send_or_edit_message(self, update: Update, text: str, keyboard, 
                                   from_callback: bool, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отправляет новое сообщение или редактирует существующее."""
        if from_callback:
            query = update.callback_query
            try:
                await query.edit_message_text(
                    text, 
                    reply_markup=keyboard, 
                    parse_mode='Markdown'
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        else:
            message = await update.message.reply_text(
                text, 
                reply_markup=keyboard, 
                parse_mode='Markdown'
            )
            schedule_message_deletion(message, context)


# Создаем глобальный экземпляр обработчиков
command_handlers = CommandHandlers()

# Экспортируем методы для обратной совместимости
admin_command = command_handlers.admin_command
stats_command = command_handlers.stats_command
broadcast_command = command_handlers.broadcast_command
test_schedule_command = command_handlers.test_schedule_command
start = command_handlers.start
menu_command = command_handlers.menu_command
today_command = command_handlers.today_command
tomorrow_command = command_handlers.tomorrow_command
next_lesson_command = command_handlers.next_lesson_command

# TODO: Добавить остальные команды в следующих итерациях
# Это позволяет постепенно мигрировать код без нарушения функциональности
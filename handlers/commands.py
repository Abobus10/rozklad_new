# -*- coding: utf-8 -*-
"""
Обробники команд Telegram бота.

Сучасна архітектура з типізацією, валідацією та структурованим логуванням.
Використовує принципи чистого коду та хороші практики Python розробки.
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
    """Клас для обробки команд бота з сучасною архітектурою."""
    
    def __init__(self):
        """Ініціалізація обробників команд."""
        self.logger.info("Ініціалізація обробників команд")

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, error_msg: str) -> None:
        """
        Централізована обробка помилок.
        
        Args:
            update: Оновлення Telegram
            context: Контекст виконання
            error_msg: Повідомлення про помилку
        """
        self.logger.error(f"Помилка в команді: {error_msg}")
        
        try:
            if update.message:
                await update.message.reply_text(
                    "❌ Сталася помилка. Спробуйте пізніше або зверніться до адміністратора.",
                    parse_mode='Markdown'
                )
        except TelegramError as e:
            self.logger.error(f"Не вдалося надіслати повідомлення про помилку: {e}")

    def _get_user_context(self, update: Update) -> tuple[str, str, bool]:
        """
        Отримує контекст користувача та чату.
        
        Args:
            update: Оновлення Telegram
            
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
        """Показує адмін-панель з доступними командами."""
        try:
            admin_help_text = (
                "👑 *Адмін-панель*\n\n"
                "Доступні команди:\n"
                "`/stats` - Статистика бота\n"
                "`/broadcast [повідомлення]` - Розсилка\n"
                "`/test_schedule` - Тестова відправка розкладу"
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
        """Показує статистику використання бота."""
        try:
            total_users = data_manager.get_users_count()
            active_today = data_manager.get_active_users_today()
            total_groups = data_manager.get_groups_count()
            
            stats_text = (
                f"📊 *Статистика бота*\n\n"
                f"👤 Всього користувачів: {total_users}\n"
                f"👥 Груп у розкладі: {total_groups}\n"
                f"📈 Активних сьогодні: {active_today}"
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
        """Робить розсилку повідомлення всім користувачам."""
        try:
            message_to_send = " ".join(context.args)
            if not message_to_send:
                message = await update.message.reply_text(
                    "Будь ласка, вкажіть повідомлення для розсилки.\n"
                    "Приклад: `/broadcast Привіт усім!`",
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
                        text=f"📢 *Повідомлення від адміністратора:*\n\n{message_to_send}",
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                except TelegramError as e:
                    self.logger.error(f"Не вдалося надіслати повідомлення {user_id}: {e}")
                    failed_count += 1
            
            reply_text = (
                f"📢 Розсилка завершена!\n\n"
                f"✅ Надіслано: {sent_count}\n"
                f"❌ Помилок: {failed_count}"
            )
            
            message = await update.message.reply_text(reply_text)
            schedule_message_deletion(message, context, 600)
            
        except Exception as e:
            await self.handle_error(update, context, f"broadcast_command: {e}")

    @admin_only
    async def test_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Запускає тестову відправку ранкового розкладу."""
        try:
            await update.message.reply_text("🚀 Запускаю тестову відправку розкладу...")
            await send_morning_schedule(context)
            
            message = await update.message.reply_text("✅ Тестова відправка завершена.")
            schedule_message_deletion(message, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"test_schedule_command: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Привітання користувача.
        
        Реєструє нового користувача або вітає існуючого.
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
        """Обробляє команду /start в груповому чаті."""
        chat_title = update.effective_chat.title
        
        # Реєструємо груповий чат
        group_data = data_manager.get_group_chat(chat_id)
        default_group = group_data.default_group if group_data else None
        
        data_manager.update_group_chat(chat_id, **{"chat_title": chat_title})
        
        welcome_text = f"👋 Привіт, група *{chat_title}*!\nЯ бот розкладу коледжу! 📚\n\n"
        
        if default_group:
            welcome_text += f"✅ Для цього чату встановлено розклад групи *{default_group}*.\n"
        else:
            welcome_text += "⚠️ Для цього чату ще не встановлено розклад. Адміністратор може зробити це командою /setgroupschedule.\n"
        
        welcome_text += "\n🎯 Використовуйте /menu для перегляду доступних дій."
        
        message = await update.message.reply_text(welcome_text, parse_mode='Markdown')
        schedule_message_deletion(message, context)

    async def _handle_private_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   user_id: str, user) -> None:
        """Обробляє команду /start в приватному чаті."""
        existing_user = data_manager.get_user(user_id)
        
        if not existing_user:
            # Новий користувач
            data_manager.update_user(
                user_id,
                first_name=user.first_name,
                username=user.username,
                registration_date=datetime.now()
            )
            
            message = await update.message.reply_html(
                f"Привіт, {user.mention_html()}! 👋 Радий тебе бачити."
            )
        else:
            # Існуючий користувач
            data_manager.update_user(user_id, first_name=user.first_name, username=user.username)
            
            message = await update.message.reply_html(
                f"З поверненням, {user.first_name}! 👋"
            )
        
        schedule_message_deletion(message, context, 60)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          from_callback: bool = False) -> None:
        """Показує головне меню з кнопками."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            
            # Формування тексту меню
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
        """Формує текст для головного меню."""
        
        if is_group:
            group_chat_data = data_manager.get_group_chat(chat_id)
            group_name = group_chat_data.default_group or 'не обрана'
            
            menu_text = (
                f"📋 *Головне меню для групи*\n"
                f"Поточна група: *{group_name}*\n\n"
                "Оберіть дію:"
            )
        else:
            user_data = data_manager.get_user(user_id)
            group_name = user_data.group if user_data and user_data.group else 'не обрана'
            
            menu_text = (
                "📋 *Головне меню*\n"
                f"Твоя група: *{group_name}*\n\n"
                "Чим можу допомогти?"
            )
        return menu_text

    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           from_callback: bool = False) -> None:
        """Показує розклад на сьогодні."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)
            
            if not user_group:
                await self._send_no_group_message(update, from_callback)
                return
            
            today = datetime.now()
            day_name = DAYS_UA.get(today.weekday())
            
            if not day_name:
                text = "🗓 Сьогодні вихідний день!"
                keyboard = quick_nav_keyboard
            else:
                current_week = schedule_service.get_current_week()
                lessons = schedule_service.get_day_lessons(user_group, day_name, current_week)
                
                if lessons:
                    text = schedule_service.format_schedule_text(user_group, day_name, lessons, current_week)
                    keyboard = quick_nav_keyboard
                else:
                    text = f"📅 *{day_name.capitalize()}*\n\nСьогодні пар немає! 🎉"
                    keyboard = quick_nav_keyboard
            
            await self._send_or_edit_message(update, text, keyboard, from_callback, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"today_command: {e}")

    async def tomorrow_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              from_callback: bool = False) -> None:
        """Показує розклад на завтра."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)
            
            if not user_group:
                await self._send_no_group_message(update, from_callback)
                return
            
            tomorrow = datetime.now() + timedelta(days=1)
            day_name = DAYS_UA.get(tomorrow.weekday())
            
            if not day_name:
                text = "🗓 Завтра вихідний день!"
                keyboard = tomorrow_nav_keyboard
            else:
                tomorrow_week = schedule_service.get_current_week(tomorrow)
                lessons = schedule_service.get_day_lessons(user_group, day_name, tomorrow_week)
                
                if lessons:
                    text = schedule_service.format_schedule_text(user_group, day_name, lessons, tomorrow_week)
                    keyboard = tomorrow_nav_keyboard
                else:
                    text = f"📅 *{day_name.capitalize()}*\n\nЗавтра пар немає! 🎉"
                    keyboard = tomorrow_nav_keyboard
            
            await self._send_or_edit_message(update, text, keyboard, from_callback, context)
            
        except Exception as e:
            await self.handle_error(update, context, f"tomorrow_command: {e}")

    async def next_lesson_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показує інформацію про наступну пару."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)
            
            if not user_group:
                await self._send_no_group_message(update, False)
                return
            
            next_lesson_info = schedule_service.get_next_lesson(user_group)
            
            if next_lesson_info:
                text = f"⏰ *Наступна пара*\n\n{next_lesson_info}"
                keyboard = next_lesson_nav_keyboard
            else:
                text = "⏰ *Наступна пара*\n\nБільше пар сьогодні немає. Можна відпочивати! 😴"
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
        """Надсилає повідомлення про необхідність встановити групу."""
        keyboard = [[InlineKeyboardButton("⚙️ Встановити групу", callback_data="quick_setgroup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "⚠️ Спочатку встановіть групу."
        
        if from_callback:
            query = update.callback_query
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def _send_or_edit_message(self, update: Update, text: str, keyboard, 
                                   from_callback: bool, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Надсилає нове повідомлення або редагує існуюче."""
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

    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False) -> None:
        """Показує меню вибору дня для перегляду розкладу."""
        try:
            user_id, chat_id, is_group = self._get_user_context(update)
            user_group = schedule_service.get_user_group(user_id, chat_id if is_group else None)

            if not user_group:
                await self._send_no_group_message(update, from_callback)
                return

            text = "📅 Оберіть день для перегляду розкладу:"
            keyboard = get_schedule_day_keyboard(user_group)
            
            await self._send_or_edit_message(update, text, keyboard, from_callback, context)

        except Exception as e:
            await self.handle_error(update, context, f"schedule_command: {e}")


# Створюємо глобальний екземпляр обробників
command_handlers = CommandHandlers()

# Експортуємо методи для зворотної сумісності
admin_command = command_handlers.admin_command
stats_command = command_handlers.stats_command
broadcast_command = command_handlers.broadcast_command
test_schedule_command = command_handlers.test_schedule_command
start = command_handlers.start
menu_command = command_handlers.menu_command
schedule_command = command_handlers.schedule_command
today_command = command_handlers.today_command
tomorrow_command = command_handlers.tomorrow_command
next_lesson_command = command_handlers.next_lesson_command

# TODO: Додати інші команди в наступних ітераціях
# Це дозволяє поступово мігрувати код без порушення функціональності
# -*- coding: utf-8 -*-
"""
Основний файл для запуску Telegram-бота розкладу.

Використовує сучасну архітектуру з типізацією, валідацією даних,
структурованим логуванням і гарною організацією коду.
"""

import asyncio
import signal
import sys
from datetime import time
from typing import Optional

import pytz
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)

from config import config, KYIV_TZ
from logger_config import main_logger, LoggerMixin
from data_manager import data_manager
from notifications import send_daily_reminders, send_morning_schedule, send_next_lesson_notifications
from handlers import commands, callbacks, conversations


class TelegramBot(LoggerMixin):
    """Основний клас Telegram бота з сучасною архітектурою."""
    
    def __init__(self):
        """Ініціалізація бота."""
        self.application: Optional[Application] = None
        self._shutdown_requested = False
        
        # Налаштування обробників сигналів для graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Ініціалізація Telegram бота завершена")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Обробник сигналів для коректного завершення роботи."""
        self.logger.info(f"Отримано сигнал {signum}. Починаю graceful shutdown...")
        self._shutdown_requested = True
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Глобальний обробник помилок.
        
        Args:
            update: Оновлення від Telegram
            context: Контекст виконання
        """
        error_msg = f"Помилка при обробці оновлення: {context.error}"
        
        if update:
            if hasattr(update, 'effective_user') and update.effective_user:
                error_msg += f" | Користувач: {update.effective_user.id}"
            if hasattr(update, 'effective_chat') and update.effective_chat:
                error_msg += f" | Чат: {update.effective_chat.id}"
        
        self.logger.error(error_msg, exc_info=context.error)
        
        # Можна додати відправку повідомлення адміністраторам про критичні помилки
        if context.error and "critical" in str(context.error).lower():
            await self._notify_admins_about_error(context.error)
    
    async def _notify_admins_about_error(self, error: Exception) -> None:
        """Повідомляє адміністраторів про критичні помилки."""
        try:
            for admin_id in config.admin_ids:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=f"🚨 Критична помилка в боті:\n{error}",
                    parse_mode="HTML"
                )
        except Exception as e:
            self.logger.error(f"Не вдалося повідомити адміністраторів: {e}")
    
    def _create_conversation_handlers(self) -> list[ConversationHandler]:
        """
        Створює обробники діалогів.
        
        Returns:
            Список налаштованих ConversationHandler
        """
        handlers = []
        
        # Діалог встановлення групи
        conv_handler_group = ConversationHandler(
            entry_points=[
                CommandHandler("setgroup", conversations.set_group_start),
                CallbackQueryHandler(conversations.set_group_start, pattern="^quick_setgroup$")
            ],
            states={
                conversations.CHOOSING_GROUP: [
                    CallbackQueryHandler(conversations.group_chosen, pattern="^conv_group_"),
                    CallbackQueryHandler(conversations.cancel_conversation, pattern="^conv_cancel$")
                ]
            },
            fallbacks=[CommandHandler("cancel", conversations.cancel_conversation)],
            name="set_group_conversation"
        )
        handlers.append(conv_handler_group)
        
        # Діалог гри "Вгадай число"
        conv_handler_game = ConversationHandler(
            entry_points=[
                CommandHandler("game", conversations.game_start),
                CallbackQueryHandler(conversations.game_start, pattern="^quick_game$")
            ],
            states={
                conversations.GUESSING_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.game_guess),
                    CallbackQueryHandler(conversations.cancel_conversation, pattern="^conv_cancel$")
                ]
            },
            fallbacks=[CommandHandler("cancel", conversations.cancel_conversation)],
            name="game_conversation"
        )
        handlers.append(conv_handler_game)
        
        # Діалог встановлення часу нагадувань
        conv_handler_reminder = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(conversations.set_reminder_time_start, pattern="^set_reminder_time$")
            ],
            states={
                conversations.SETTING_REMINDER_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.reminder_time_received),
                    CallbackQueryHandler(conversations.cancel_conversation, pattern="^conv_cancel$")
                ]
            },
            fallbacks=[CommandHandler("cancel", conversations.cancel_conversation)],
            name="reminder_time_conversation"
        )
        handlers.append(conv_handler_reminder)
        
        self.logger.info(f"Створено {len(handlers)} обробників діалогів")
        return handlers
    
    def _register_handlers(self) -> None:
        """Реєструє всі обробники команд та повідомлень."""
        
        # Команди адміністратора
        self.application.add_handler(CommandHandler("admin", commands.admin_command))
        self.application.add_handler(CommandHandler("stats", commands.stats_command))
        self.application.add_handler(CommandHandler("broadcast", commands.broadcast_command))
        self.application.add_handler(CommandHandler("test_schedule", commands.test_schedule_command))
        
        # Основні команди користувачів
        self.application.add_handler(CommandHandler("start", commands.start))
        self.application.add_handler(CommandHandler("help", commands.menu_command))  # допомога = меню
        self.application.add_handler(CommandHandler("menu", commands.menu_command))
        
        # Команди розкладу
        self.application.add_handler(CommandHandler("today", commands.today_command))
        self.application.add_handler(CommandHandler("tomorrow", commands.tomorrow_command))
        self.application.add_handler(CommandHandler("next", commands.next_lesson_command))
        self.application.add_handler(CommandHandler("schedule", commands.schedule_command))
        
        # Команди налаштувань - замінюємо на menu_command, оскільки вони не реалізовані
        self.application.add_handler(CommandHandler("reminders", commands.menu_command))
        self.application.add_handler(CommandHandler("me", commands.menu_command))
        self.application.add_handler(CommandHandler("week", commands.menu_command))
        
        # Додаткові команди - замінюємо на menu_command, оскільки вони не реалізовані  
        self.application.add_handler(CommandHandler("fact", commands.menu_command))
        self.application.add_handler(CommandHandler("setgroupschedule", commands.menu_command))
        self.application.add_handler(CommandHandler("groupinfo", commands.menu_command))
        
        # Обробники діалогів
        for handler in self._create_conversation_handlers():
            self.application.add_handler(handler)
        
        # Обробники callback кнопок
        self.application.add_handler(CallbackQueryHandler(callbacks.schedule_callback, pattern="^schedule_"))
        self.application.add_handler(CallbackQueryHandler(callbacks.reminder_callback, pattern="^(toggle_|disable_)"))
        self.application.add_handler(CallbackQueryHandler(callbacks.group_schedule_callback, pattern="^setgroup_"))
        self.application.add_handler(CallbackQueryHandler(callbacks.quick_action_callback, pattern="^quick_"))
        self.application.add_handler(CallbackQueryHandler(callbacks.menu_callback, pattern="^show_menu$"))
        
        # Глобальний обробник помилок
        self.application.add_error_handler(self._error_handler)
        
        self.logger.info("Всі обробники успішно зареєстровані")
    
    def _setup_scheduled_jobs(self) -> None:
        """Налаштовує заплановані задачі."""
        job_queue = self.application.job_queue
        
        if not job_queue:
            self.logger.error("Job queue не ініціалізовано")
            return
        
        # Ранкова розсилка розкладу (пн-сб о 7:00)
        morning_time = time(hour=7, minute=0, tzinfo=pytz.timezone(KYIV_TZ))
        job_queue.run_daily(
            callback=send_morning_schedule,
            time=morning_time,
            days=tuple(range(6)),  # пн-сб
            name="morning_schedule"
        )
        
        # Перевірка персональних нагадувань (щохвилини)
        job_queue.run_repeating(
            callback=send_daily_reminders,
            interval=60,
            first=10,
            name="daily_reminders"
        )
        
        # Сповіщення про наступну пару (щохвилини)
        job_queue.run_repeating(
            callback=send_next_lesson_notifications,
            interval=60,
            first=15,
            name="next_lesson_notifications"
        )
        
        self.logger.info("Заплановані задачі налаштовано")
    
    def start(self) -> None:
        """Запускає бота."""
        try:
            self.logger.info("Створення Application...")
            
            # Створюємо Application з додатковими налаштуваннями
            builder = Application.builder()
            builder.token(config.telegram_token)
            builder.concurrent_updates(True)  # Включаємо конкурентну обробку
            builder.read_timeout(config.request_timeout)
            builder.write_timeout(config.request_timeout)
            
            self.application = builder.build()
            
            # Реєструємо обробники
            self._register_handlers()
            
            # Налаштовуємо заплановані задачі
            self._setup_scheduled_jobs()
            
            self.logger.info("Ініціалізація завершена. Запускаю polling...")
            
            # Запускаємо бота з простим підходом для Windows
            self.application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            self.logger.critical(f"Критична помилка при запуску бота: {e}", exc_info=True)
            raise
    
    def stop(self) -> None:
        """Зупиняє бота."""
        if self.application:
            self.logger.info("Зупинка бота...")
            try:
                # При синхронному запуску зупинка відбувається автоматично
                self.logger.info("Бот успішно зупинений")
            except Exception as e:
                self.logger.error(f"Помилка при зупинці бота: {e}")


def main() -> None:
    """Основна функція додатку."""
    bot = TelegramBot()
    
    try:
        # Перевіряємо базові налаштування
        user_count = data_manager.get_users_count()
        groups_count = data_manager.get_groups_count()
        
        main_logger.info(f"Завантажено користувачів: {user_count}")
        main_logger.info(f"Завантажено груп: {groups_count}")
        
        # Запускаємо бота
        bot.start()
        
    except KeyboardInterrupt:
        main_logger.info("Отримано сигнал переривання від користувача")
    except Exception as e:
        main_logger.critical(f"Неочікувана помилка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        bot.stop()
        main_logger.info("Додаток завершено")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрограму перервано користувачем")
    except Exception as e:
        print(f"Критична помилка: {e}")
        sys.exit(1) 
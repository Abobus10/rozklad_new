# -*- coding: utf-8 -*-
"""
Основной файл для запуска Telegram-бота расписания.

Использует современную архитектуру с типизацией, валидацией данных,
структурированным логированием и хорошей организацией кода.
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
    """Основной класс Telegram бота с современной архитектурой."""
    
    def __init__(self):
        """Инициализация бота."""
        self.application: Optional[Application] = None
        self._shutdown_requested = False
        
        # Настройка обработчиков сигналов для graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Инициализация Telegram бота завершена")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Обработчик сигналов для корректного завершения работы."""
        self.logger.info(f"Получен сигнал {signum}. Начинаю graceful shutdown...")
        self._shutdown_requested = True
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Глобальный обработчик ошибок.
        
        Args:
            update: Обновление от Telegram
            context: Контекст выполнения
        """
        error_msg = f"Ошибка при обработке обновления: {context.error}"
        
        if update:
            if hasattr(update, 'effective_user') and update.effective_user:
                error_msg += f" | Пользователь: {update.effective_user.id}"
            if hasattr(update, 'effective_chat') and update.effective_chat:
                error_msg += f" | Чат: {update.effective_chat.id}"
        
        self.logger.error(error_msg, exc_info=context.error)
        
        # Можно добавить отправку уведомления администраторам о критических ошибках
        if context.error and "critical" in str(context.error).lower():
            await self._notify_admins_about_error(context.error)
    
    async def _notify_admins_about_error(self, error: Exception) -> None:
        """Уведомляет администраторов о критических ошибках."""
        try:
            for admin_id in config.admin_ids:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=f"🚨 Критическая ошибка в боте:\n{error}",
                    parse_mode="HTML"
                )
        except Exception as e:
            self.logger.error(f"Не удалось уведомить администраторов: {e}")
    
    def _create_conversation_handlers(self) -> list[ConversationHandler]:
        """
        Создает обработчики диалогов.
        
        Returns:
            Список настроенных ConversationHandler
        """
        handlers = []
        
        # Диалог установки группы
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
        
        # Диалог игры "Угадай число"
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
        
        # Диалог установки времени напоминаний
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
        
        self.logger.info(f"Создано {len(handlers)} обработчиков диалогов")
        return handlers
    
    def _register_handlers(self) -> None:
        """Регистрирует все обработчики команд и сообщений."""
        
        # Команды администратора
        self.application.add_handler(CommandHandler("admin", commands.admin_command))
        self.application.add_handler(CommandHandler("stats", commands.stats_command))
        self.application.add_handler(CommandHandler("broadcast", commands.broadcast_command))
        self.application.add_handler(CommandHandler("test_schedule", commands.test_schedule_command))
        
        # Основные команды пользователей
        self.application.add_handler(CommandHandler("start", commands.start))
        self.application.add_handler(CommandHandler("help", commands.help_command))
        self.application.add_handler(CommandHandler("menu", commands.menu_command))
        
        # Команды расписания
        self.application.add_handler(CommandHandler("today", commands.today_command))
        self.application.add_handler(CommandHandler("tomorrow", commands.tomorrow_command))
        self.application.add_handler(CommandHandler("week", commands.week_command))
        self.application.add_handler(CommandHandler("next", commands.next_lesson_command))
        self.application.add_handler(CommandHandler("schedule", commands.schedule_command))
        
        # Команды настроек
        self.application.add_handler(CommandHandler("reminders", commands.reminders_command))
        self.application.add_handler(CommandHandler("me", commands.me_command))
        
        # Дополнительные команды
        self.application.add_handler(CommandHandler("fact", commands.fact_command))
        self.application.add_handler(CommandHandler("setgroupschedule", commands.set_group_schedule_command))
        self.application.add_handler(CommandHandler("groupinfo", commands.group_info_command))
        
        # Обработчики диалогов
        for handler in self._create_conversation_handlers():
            self.application.add_handler(handler)
        
        # Обработчики callback кнопок
        self.application.add_handler(CallbackQueryHandler(callbacks.schedule_callback, pattern="^schedule_"))
        self.application.add_handler(CallbackQueryHandler(callbacks.reminder_callback, pattern="^(toggle_|disable_)"))
        self.application.add_handler(CallbackQueryHandler(callbacks.group_schedule_callback, pattern="^setgroup_"))
        self.application.add_handler(CallbackQueryHandler(callbacks.quick_action_callback, pattern="^quick_"))
        self.application.add_handler(CallbackQueryHandler(callbacks.menu_callback, pattern="^show_menu$"))
        
        # Глобальный обработчик ошибок
        self.application.add_error_handler(self._error_handler)
        
        self.logger.info("Все обработчики успешно зарегистрированы")
    
    def _setup_scheduled_jobs(self) -> None:
        """Настраивает запланированные задачи."""
        job_queue = self.application.job_queue
        
        if not job_queue:
            self.logger.error("Job queue не инициализирован")
            return
        
        # Утренняя рассылка расписания (пн-сб в 7:00)
        morning_time = time(hour=7, minute=0, tzinfo=pytz.timezone(KYIV_TZ))
        job_queue.run_daily(
            callback=send_morning_schedule,
            time=morning_time,
            days=tuple(range(6)),  # пн-сб
            name="morning_schedule"
        )
        
        # Проверка персональных напоминаний (каждую минуту)
        job_queue.run_repeating(
            callback=send_daily_reminders,
            interval=60,
            first=10,
            name="daily_reminders"
        )
        
        # Уведомления о следующей паре (каждую минуту)
        job_queue.run_repeating(
            callback=send_next_lesson_notifications,
            interval=60,
            first=15,
            name="next_lesson_notifications"
        )
        
        self.logger.info("Запланированные задачи настроены")
    
    async def start(self) -> None:
        """Запускает бота."""
        try:
            self.logger.info("Создание Application...")
            
            # Создаем Application с дополнительными настройками
            builder = Application.builder()
            builder.token(config.telegram_token)
            builder.concurrent_updates(True)  # Включаем конкурентную обработку
            builder.read_timeout(config.request_timeout)
            builder.write_timeout(config.request_timeout)
            
            self.application = builder.build()
            
            # Регистрируем обработчики
            self._register_handlers()
            
            # Настраиваем запланированные задачи
            self._setup_scheduled_jobs()
            
            self.logger.info("Инициализация завершена. Запускаю polling...")
            
            # Запускаем бота
            await self.application.run_polling(
                drop_pending_updates=True,  # Игнорируем накопившиеся обновления
                close_loop=False  # Не закрываем event loop
            )
            
        except Exception as e:
            self.logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Останавливает бота."""
        if self.application:
            self.logger.info("Остановка бота...")
            try:
                await self.application.stop()
                await self.application.shutdown()
                self.logger.info("Бот успешно остановлен")
            except Exception as e:
                self.logger.error(f"Ошибка при остановке бота: {e}")


async def main() -> None:
    """Основная функция приложения."""
    bot = TelegramBot()
    
    try:
        # Проверяем базовые настройки
        user_count = data_manager.get_users_count()
        groups_count = data_manager.get_groups_count()
        
        main_logger.info(f"Загружено пользователей: {user_count}")
        main_logger.info(f"Загружено групп: {groups_count}")
        
        # Запускаем бота
        await bot.start()
        
    except KeyboardInterrupt:
        main_logger.info("Получен сигнал прерывания от пользователя")
    except Exception as e:
        main_logger.critical(f"Неожиданная ошибка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await bot.stop()
        main_logger.info("Приложение завершено")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1) 
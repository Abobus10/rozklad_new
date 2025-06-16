"""
Модуль налаштування логування для Telegram-бота.

Забезпечує структуроване логування з ротацією файлів,
кольоровим виведенням у консоль та різними рівнями деталізації.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import config


class ColoredFormatter(logging.Formatter):
    """Форматтер з кольоровим виведенням для консолі."""
    
    # ANSI коди кольорів
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматує лог-запис з кольорами."""
        # Додаємо колір до імені рівня
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            record.levelname = colored_levelname
        
        # Форматуємо запис
        formatted = super().format(record)
        
        # Повертаємо початкове ім'я рівня
        record.levelname = levelname
        
        return formatted


class BotLogger:
    """Клас для налаштування логування бота."""
    
    def __init__(
        self,
        name: str = "telegram_bot",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """
        Ініціалізація логера.
        
        Args:
            name: Ім'я логера
            log_level: Рівень логування
            log_file: Шлях до файлу логів
            max_file_size: Максимальний розмір файлу в байтах
            backup_count: Кількість резервних файлів
        """
        self.name = name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Налаштовує логер з консольним та файловим виводом."""
        # Очищуємо існуючі обробники
        self.logger.handlers.clear()
        
        # Встановлюємо рівень логування
        self.logger.setLevel(self.log_level)
        
        # Створюємо консольний обробник
        self._setup_console_handler()
        
        # Створюємо файловий обробник, якщо вказано файл
        if self.log_file:
            self._setup_file_handler()
        
        # Запобігаємо дублюванню логів
        self.logger.propagate = False
    
    def _setup_console_handler(self) -> None:
        """Налаштовує консольний вивід з кольорами."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        
        # Використовуємо кольоровий форматтер для консолі
        console_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        console_formatter = ColoredFormatter(
            console_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self) -> None:
        """Налаштовує файловий вивід з ротацією."""
        # Створюємо директорію для логів, якщо не існує
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Створюємо обробник з ротацією файлів
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        
        # Більш детальний формат для файлів
        file_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(funcName)s:%(lineno)d | "
            "%(message)s | PID:%(process)d"
        )
        file_formatter = logging.Formatter(
            file_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """Повертає налаштований логер."""
        return self.logger


def setup_logging() -> logging.Logger:
    """
    Налаштовує та повертає основний логер додатка.
    
    Returns:
        Налаштований екземпляр логера
    """
    bot_logger = BotLogger(
        name="telegram_schedule_bot",
        log_level=config.log_level,
        log_file=config.log_file,
        max_file_size=10 * 1024 * 1024,  # 10MB
        backup_count=5
    )
    
    logger = bot_logger.get_logger()
    
    # Логуємо інформацію про запуск
    logger.info("=" * 60)
    logger.info("Запуск Telegram-бота розкладу")
    logger.info(f"Час запуску: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Рівень логування: {config.log_level}")
    logger.info(f"Файл логів: {config.log_file}")
    logger.info("=" * 60)
    
    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Створює логер для конкретного модуля.
    
    Args:
        module_name: Ім'я модуля
        
    Returns:
        Логер для модуля
    """
    return logging.getLogger(f"telegram_schedule_bot.{module_name}")


class LoggerMixin:
    """Міксин для додавання логування в класи."""
    
    @property
    def logger(self) -> logging.Logger:
        """Повертає логер для класу."""
        if not hasattr(self, '_logger'):
            class_name = self.__class__.__name__
            self._logger = get_module_logger(class_name)
        return self._logger
    
    def log_method_call(self, method_name: str, **kwargs) -> None:
        """
        Логує виклик методу з параметрами.
        
        Args:
            method_name: Ім'я методу
            **kwargs: Параметри методу
        """
        params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.debug(f"Виклик {method_name}({params})")
    
    def log_error(self, error: Exception, context: str = "") -> None:
        """
        Логує помилку з контекстом.
        
        Args:
            error: Виняток
            context: Додатковий контекст
        """
        error_msg = f"Помилка: {error}"
        if context:
            error_msg = f"{context} - {error_msg}"
        
        self.logger.error(error_msg, exc_info=True)


# Налаштовуємо основний логер при імпорті модуля
main_logger = setup_logging()

# Експортуємо основні функції
__all__ = [
    'setup_logging',
    'get_module_logger', 
    'LoggerMixin',
    'main_logger'
] 
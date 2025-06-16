"""
Модуль настройки логирования для Telegram бота.

Обеспечивает структурированное логирование с ротацией файлов,
цветным выводом в консоль и различными уровнями детализации.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import config


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли."""
    
    # ANSI цветовые коды
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует лог-запись с цветами."""
        # Добавляем цвет к имени уровня
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            record.levelname = colored_levelname
        
        # Форматируем запись
        formatted = super().format(record)
        
        # Возвращаем исходное имя уровня
        record.levelname = levelname
        
        return formatted


class BotLogger:
    """Класс для настройки логирования бота."""
    
    def __init__(
        self,
        name: str = "telegram_bot",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """
        Инициализация логгера.
        
        Args:
            name: Имя логгера
            log_level: Уровень логирования
            log_file: Путь к файлу логов
            max_file_size: Максимальный размер файла в байтах
            backup_count: Количество резервных файлов
        """
        self.name = name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Настраивает логгер с консольным и файловым выводом."""
        # Очищаем существующие обработчики
        self.logger.handlers.clear()
        
        # Устанавливаем уровень логирования
        self.logger.setLevel(self.log_level)
        
        # Создаем консольный обработчик
        self._setup_console_handler()
        
        # Создаем файловый обработчик если указан файл
        if self.log_file:
            self._setup_file_handler()
        
        # Предотвращаем дублирование логов
        self.logger.propagate = False
    
    def _setup_console_handler(self) -> None:
        """Настраивает консольный вывод с цветами."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        
        # Используем цветной форматтер для консоли
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
        """Настраивает файловый вывод с ротацией."""
        # Создаем директорию для логов если не существует
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Создаем обработчик с ротацией файлов
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        
        # Более подробный формат для файлов
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
        """Возвращает настроенный логгер."""
        return self.logger


def setup_logging() -> logging.Logger:
    """
    Настраивает и возвращает основной логгер приложения.
    
    Returns:
        Настроенный экземпляр логгера
    """
    bot_logger = BotLogger(
        name="telegram_schedule_bot",
        log_level=config.log_level,
        log_file=config.log_file,
        max_file_size=10 * 1024 * 1024,  # 10MB
        backup_count=5
    )
    
    logger = bot_logger.get_logger()
    
    # Логируем информацию о запуске
    logger.info("=" * 60)
    logger.info("Запуск Telegram бота расписания")
    logger.info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Уровень логирования: {config.log_level}")
    logger.info(f"Файл логов: {config.log_file}")
    logger.info("=" * 60)
    
    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Создает логгер для конкретного модуля.
    
    Args:
        module_name: Имя модуля
        
    Returns:
        Логгер для модуля
    """
    return logging.getLogger(f"telegram_schedule_bot.{module_name}")


class LoggerMixin:
    """Миксин для добавления логирования в классы."""
    
    @property
    def logger(self) -> logging.Logger:
        """Возвращает логгер для класса."""
        if not hasattr(self, '_logger'):
            class_name = self.__class__.__name__
            self._logger = get_module_logger(class_name)
        return self._logger
    
    def log_method_call(self, method_name: str, **kwargs) -> None:
        """
        Логирует вызов метода с параметрами.
        
        Args:
            method_name: Имя метода
            **kwargs: Параметры метода
        """
        params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.debug(f"Вызов {method_name}({params})")
    
    def log_error(self, error: Exception, context: str = "") -> None:
        """
        Логирует ошибку с контекстом.
        
        Args:
            error: Исключение
            context: Дополнительный контекст
        """
        error_msg = f"Ошибка: {error}"
        if context:
            error_msg = f"{context} - {error_msg}"
        
        self.logger.error(error_msg, exc_info=True)


# Настраиваем основной логгер при импорте модуля
main_logger = setup_logging()

# Экспортируем основные функции
__all__ = [
    'setup_logging',
    'get_module_logger', 
    'LoggerMixin',
    'main_logger'
] 
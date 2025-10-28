"""
Централизованная настройка логирования для всего приложения.
"""
import logging
import sys
import os
from typing import Optional

def setup_logger(name: Optional[str] = None, log_level: str = 'INFO', log_file: str = 'bot_log.txt') -> logging.Logger:
    """
    Настраивает и возвращает logger с консольным и файловым выводом.
    
    Args:
        name: Имя логгера. Если None, используется root logger.
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов
    
    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)
    
    # Если логгер уже настроен, не настраиваем заново
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Настройка формата
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Консольный хендлер с правильной кодировкой для Windows
    if os.name == 'nt':  # Windows
        import io
        console_handler = logging.StreamHandler(
            io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        )
    else:
        console_handler = logging.StreamHandler()
    
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    
    # Файловый хендлер
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"⚠️ Не удалось создать файл логов: {e}")
    
    logger.addHandler(console_handler)
    
    return logger

# Создаем базовый логгер для модуля
logger = setup_logger(__name__)


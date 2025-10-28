"""
Water Reminder Bot - Точка входа для обратной совместимости

DEPRECATED: Этот файл оставлен для обратной совместимости.
Новый модульный код находится в папке app/

Чтобы запустить бота, используйте:
    python water_reminder_bot.py  (старый способ, работает)
    python -m app.bot             (новый способ, рекомендуется)
"""
import warnings

# Показываем предупреждение о deprecated файле
warnings.warn(
    "water_reminder_bot.py is deprecated. Please use 'python -m app.bot' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Импортируем и запускаем новый модульный бот
from app.bot import run_bot

if __name__ == '__main__':
    print("=" * 70)
    print("WARNING: Using deprecated launch method")
    print("=" * 70)
    print("Recommended: python -m app.bot")
    print("Current method will work for backwards compatibility.")
    print("=" * 70)
    print()
    
    run_bot()

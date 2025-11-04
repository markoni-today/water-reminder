"""
Главная точка входа для Water Reminder Bot
Модульная архитектура с исправленной логикой планировщика
"""
import sys
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler
)

from .config import (
    TELEGRAM_BOT_TOKEN,
    LOG_LEVEL, LOG_FILE
)
from .utils import setup_logger
from .database import init_db, get_all_active_water_reminders
from .scheduler import job_manager
from .handlers import (
    start, reset_command, cancel,
    water_menu, water_stop, water_resume, check_and_send_water_reminder
)

# Инициализация логгера
logger = setup_logger(__name__, LOG_LEVEL, LOG_FILE)

print(f"--- Запущено с помощью Python версии: {sys.version} ---")

async def post_init(application: Application):
    """
    Восстановление задач после запуска бота.
    Критически важно для корректной работы после перезапуска.
    """
    logger.info("🔄 --- Восстановление задач из БД ---")
    
    try:
        # Восстановление задач о воде
        water_reminders = get_all_active_water_reminders()
        logger.info(f"📊 Найдено {len(water_reminders)} активных напоминаний о воде")
        
        for r in water_reminders:
            logger.info(f"🔄 Восстанавливаю напоминание о воде для {r['chat_id']}")
            job_manager.schedule_water_reminders(
                application,
                r['chat_id'],
                r,
                check_and_send_water_reminder
            )
        
        logger.info("✅ --- Восстановление завершено ---")
        
        # Выводим статистику задач
        job_manager.print_jobs()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при восстановлении задач: {e}", exc_info=True)

async def error_handler(update: object, context):
    """Глобальный обработчик ошибок для бота."""
    logger.error(f"❌ Ошибка в боте: {context.error}", exc_info=context.error)

def create_application() -> Application:
    """
    Создает и настраивает Application бота.
    
    Returns:
        Настроенный экземпляр Application
    """
    # Проверка токена
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("❌ TELEGRAM_BOT_TOKEN не найден!")
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
    # Инициализация БД
    init_db()
    from app.database import run_all_migrations
    run_all_migrations()
    
    # Создание Application с post_init
    application = Application.builder()\
        .token(TELEGRAM_BOT_TOKEN)\
        .post_init(post_init)\
        .build()
    
    # Добавление обработчика ошибок
    application.add_error_handler(error_handler)
    
    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    
    # =========================================================================
    # CALLBACK QUERY HANDLERS
    # =========================================================================
    
    application.add_handler(CallbackQueryHandler(start, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(water_menu, pattern='^menu_water$'))
    application.add_handler(CallbackQueryHandler(water_stop, pattern='^water_stop$'))
    application.add_handler(CallbackQueryHandler(water_resume, pattern='^water_resume$'))
    
    # Обработчик активации после онбординга
    from .handlers.start import onboarding_activate
    application.add_handler(CallbackQueryHandler(onboarding_activate, pattern='^onboarding_activate$'))
    
    logger.info("✅ Application настроен и готов к работе")
    
    return application

def run_bot():
    """Запускает бота с планировщиком задач."""
    try:
        logger.info("🚀 Запуск Water Reminder Bot v2.0 (Рефакторинг)")
        
        # ИСПРАВЛЕНИЕ: Запускаем планировщик ДО создания application
        # Это необходимо, чтобы jobstore был инициализирован
        logger.info("📊 Запуск планировщика...")
        job_manager.start()
        
        # Создаем application (post_init добавит задачи в УЖЕ работающий планировщик)
        application = create_application()
        
        logger.info("✅ Бот запущен и готов к работе...")
        print("Bot is running...")
        
        # Запускаем polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        logger.info("🛑 Бот останавливается...")
        job_manager.shutdown()
        logger.info("✅ Планировщик остановлен. Работа завершена.")

if __name__ == '__main__':
    run_bot()


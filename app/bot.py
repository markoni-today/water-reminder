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
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)
from apscheduler.triggers.interval import IntervalTrigger

from .config import (
    TELEGRAM_BOT_TOKEN,
    WATER_MESSAGE, WATER_START_TIME, WATER_END_TIME, WATER_INTERVAL,
    CUSTOM_MESSAGE, CUSTOM_TIME, CUSTOM_FREQUENCY,
    LOG_LEVEL, LOG_FILE,
    CLEANUP_INTERVAL_HOURS
)
from .utils import setup_logger
from .database import init_db, get_all_active_water_reminders, get_all_active_custom_reminders, cleanup_old_reminders
from .scheduler import job_manager
from .handlers import (
    start, reset_command, cancel,
    water_menu, water_setup_start, water_get_message, water_get_start_time, 
    water_get_end_time, water_get_interval, water_stop, check_and_send_water_reminder,
    custom_menu, custom_view, custom_add_start, custom_get_message, 
    custom_get_time, custom_get_frequency, custom_delete,
    send_custom_message, send_once_and_delete_custom
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
        
        # Восстановление кастомных задач
        custom_reminders = get_all_active_custom_reminders()
        logger.info(f"📊 Найдено {len(custom_reminders)} активных кастомных напоминаний")
        
        for r in custom_reminders:
            logger.info(f"🔄 Восстанавливаю кастомное напоминание ID {r['id']}")
            
            # Определяем функцию отправки в зависимости от частоты
            send_func = send_once_and_delete_custom if r['frequency'] == 'once' else send_custom_message
            
            result = job_manager.schedule_custom_reminder(
                application,
                r,
                send_func
            )
            
            # Если одноразовое напоминание пропущено, отправляем уведомление
            if result == 'missed_once':
                from datetime import datetime
                import pytz
                from .config import Messages, DEFAULT_TIMEZONE
                
                reminder_time = datetime.fromisoformat(r['reminder_time'])
                user_tz = pytz.timezone(r.get('timezone', DEFAULT_TIMEZONE))
                
                if reminder_time.tzinfo is None:
                    reminder_time = user_tz.localize(reminder_time)
                
                missed_text = Messages.MISSED_CUSTOM_REMINDER.format(
                    message=r['message'],
                    time=reminder_time.strftime('%d.%m.%Y в %H:%M')
                )
                
                try:
                    await application.bot.send_message(chat_id=r['chat_id'], text=missed_text)
                    logger.warning(f"⚠️ Отправлено уведомление о пропущенном напоминании {r['id']}")
                except Exception as send_error:
                    # Обработка ошибок отправки (например, пользователь заблокировал бота)
                    from telegram.error import Forbidden
                    if isinstance(send_error, Forbidden):
                        logger.warning(f"⚠️ Пользователь {r['chat_id']} заблокировал бота, деактивируем напоминание {r['id']}")
                        from app.database import set_custom_reminder_active
                        set_custom_reminder_active(r['id'], False)
                    else:
                        logger.error(f"❌ Ошибка при отправке уведомления о пропущенном напоминании {r['id']}: {send_error}")
        
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
    # CONVERSATION HANDLERS
    # =========================================================================
    
    # Диалог настройки напоминаний о воде
    water_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(water_setup_start, pattern='^water_setup_start$')],
        states={
            WATER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, water_get_message)],
            WATER_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, water_get_start_time)],
            WATER_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, water_get_end_time)],
            WATER_INTERVAL: [CallbackQueryHandler(water_get_interval, pattern='^w_int_')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_chat=True,
        per_user=True,
    )
    
    # Диалог создания кастомного напоминания
    custom_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(custom_add_start, pattern='^custom_add_start$')],
        states={
            CUSTOM_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_get_message)],
            CUSTOM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_get_time)],
            CUSTOM_FREQUENCY: [CallbackQueryHandler(custom_get_frequency, pattern='^c_freq_')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_chat=True,
        per_user=True,
    )
    
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
    application.add_handler(CallbackQueryHandler(custom_menu, pattern='^menu_custom$'))
    application.add_handler(CallbackQueryHandler(water_stop, pattern='^water_stop$'))
    application.add_handler(CallbackQueryHandler(custom_view, pattern='^custom_view_'))
    application.add_handler(CallbackQueryHandler(custom_delete, pattern='^custom_delete_'))
    
    # =========================================================================
    # CONVERSATION HANDLERS (добавляем после callback handlers)
    # =========================================================================
    
    application.add_handler(water_conv)
    application.add_handler(custom_conv)
    
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
        
        # Добавляем задачу очистки старых напоминаний (если ещё не добавлена)
        if not job_manager.scheduler.get_job('cleanup_old_reminders'):
            job_manager.scheduler.add_job(
                cleanup_old_reminders,
                IntervalTrigger(hours=CLEANUP_INTERVAL_HOURS),
                id='cleanup_old_reminders',
                name='Cleanup old reminders',
                replace_existing=True
            )
            logger.info(f"🧹 Задача очистки старых напоминаний запланирована (каждые {CLEANUP_INTERVAL_HOURS} ч)")
        else:
            logger.info(f"✅ Задача очистки уже запланирована")
        
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


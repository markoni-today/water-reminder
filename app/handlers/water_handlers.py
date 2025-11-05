"""
Обработчики напоминаний о воде
Упрощенная версия с фиксированным расписанием
"""
import logging
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from app.config import (
    DEFAULT_TIMEZONE, DEFAULT_START_HOUR, DEFAULT_END_HOUR, 
    WATER_REMINDER_MESSAGE, Messages
)
from app.database import (
    get_water_reminder,
    save_water_reminder,
    set_water_reminder_active
)
from app.scheduler import job_manager

logger = logging.getLogger(__name__)

# =============================================================================
# ФУНКЦИИ ОТПРАВКИ НАПОМИНАНИЙ
# =============================================================================

async def check_and_send_water_reminder(application, chat_id: int, settings: dict):
    """
    Упрощенная версия: Отправляет напоминание о воде.
    
    ИСПРАВЛЕНО: Добавлена проверка и удаление задач для неактивных пользователей.
    
    Args:
        application: Telegram Application
        chat_id: ID чата пользователя
        settings: Настройки напоминаний
    """
    try:
        user_tz = pytz.timezone(settings.get('timezone', DEFAULT_TIMEZONE))
        now = datetime.now(user_tz)
        
        # Используем фиксированные значения (8-23, каждый час)
        start_hour = DEFAULT_START_HOUR  # 8
        end_hour = DEFAULT_END_HOUR  # 23
        message = WATER_REMINDER_MESSAGE  # Фиксированное сообщение
        
        logger.info(f"⏰ Проверка времени для {chat_id}: час {now.hour}, диапазон {start_hour}-{end_hour}")
        
        # ИСПРАВЛЕНИЕ: Проверяем is_active И удаляем задачи если пользователь неактивен
        from app.database import get_water_reminder
        user_settings = get_water_reminder(chat_id)
        
        if not user_settings:
            logger.warning(f"⚠️ Пользователь {chat_id} не найден в БД, удаляем задачи")
            # Удаляем задачи для несуществующего пользователя
            job_manager._remove_jobs_by_prefix(f"water_{chat_id}")
            return
            
        if not user_settings.get('is_active', False):
            logger.warning(f"⚠️ Пользователь {chat_id} неактивен, но задачи ещё существуют! Удаляем.")
            # Это не должно происходить - задачи должны были быть удалены при остановке
            job_manager._remove_jobs_by_prefix(f"water_{chat_id}")
            return
        
        # ИСПРАВЛЕНИЕ: Изменяем условие на <= для включения 23:00
        if start_hour <= now.hour <= end_hour:
            await application.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"✅ Отправлено напоминание о воде для {chat_id} в {now.hour}:00")
        else:
            logger.info(f"⏭️ Напоминание пропущено - час {now.hour} вне диапазона {start_hour}-{end_hour}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке и отправке напоминания о воде для {chat_id}: {e}", exc_info=True)

# =============================================================================
# ОБРАБОТЧИКИ МЕНЮ И ДИАЛОГОВ
# =============================================================================

async def water_menu(update: Update, context: CallbackContext):
    """Отображает меню управления напоминаниями о воде."""
    try:
        chat_id = update.effective_chat.id
        settings = get_water_reminder(chat_id)
        text = "💧 **Напоминания о воде**\n\n"
        keyboard = []
        
        if settings and settings.get('is_active', False):
            text += Messages.WATER_STATUS_ACTIVE
            keyboard.append([InlineKeyboardButton("⏹️ Остановить", callback_data='water_stop')])
        else:
            text += Messages.WATER_STATUS_INACTIVE
            keyboard.append([InlineKeyboardButton("▶️ Продолжить уведомления", callback_data='water_resume')])
        
        keyboard.append([InlineKeyboardButton("« Назад", callback_data='main_menu')])
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в water_menu: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)

def calculate_next_notification_time(timezone_str: str = DEFAULT_TIMEZONE) -> datetime:
    """
    Вычисляет время следующего уведомления на основе текущего времени.
    
    Логика:
    - Если сейчас между 08:00 и 23:00 → следующее в ближайший час (округление вверх)
    - Если сейчас между 23:00 и 08:00 → следующее в 08:00 (или следующего дня)
    
    Args:
        timezone_str: Часовой пояс пользователя
        
    Returns:
        datetime следующего уведомления
    """
    user_tz = pytz.timezone(timezone_str)
    now = datetime.now(user_tz)
    current_hour = now.hour
    
    if DEFAULT_START_HOUR <= current_hour < DEFAULT_END_HOUR:
        # В рабочее время - следующее уведомление в ближайший час (округление вверх)
        next_hour = current_hour + 1
        next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    elif current_hour < DEFAULT_START_HOUR:
        # До начала рабочего времени - следующее в 08:00 сегодня
        next_time = now.replace(hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0)
    else:
        # После 23:00 - следующее в 08:00 следующего дня
        tomorrow = now + timedelta(days=1)
        next_time = tomorrow.replace(hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0)
    
    return next_time

async def water_stop(update: Update, context: CallbackContext):
    """
    Останавливает напоминания о воде.
    
    ИСПРАВЛЕНО: Улучшено логирование и порядок операций для надёжности.
    """
    try:
        chat_id = update.effective_chat.id
        job_id_prefix = f"water_{chat_id}"
        
        logger.info(f"🛑 Остановка напоминаний для {chat_id}...")
        
        # ИСПРАВЛЕНИЕ: СНАЧАЛА обновляем БД
        set_water_reminder_active(chat_id, is_active=False)
        logger.info(f"💾 БД обновлена: is_active=False для {chat_id}")
        
        # ЗАТЕМ удаляем ВСЕ задачи через job_manager
        jobs = job_manager.get_all_jobs()
        removed_count = 0
        logger.info(f"📋 Всего задач в планировщике: {len(jobs)}")
        
        for job in jobs:
            if job.id.startswith(job_id_prefix):
                logger.info(f"🗑️ Удаляю задачу: {job.id} (next_run: {job.next_run_time})")
                job_manager.remove_job(job.id)
                removed_count += 1
        
        logger.info(f"✅ Напоминания о воде для {chat_id} остановлены ({removed_count} задач удалено)")
        
        # ПРОВЕРКА: Убеждаемся, что задачи действительно удалены
        remaining_jobs = [j for j in job_manager.get_all_jobs() if j.id.startswith(job_id_prefix)]
        if remaining_jobs:
            logger.error(f"❌ ОШИБКА: После остановки остались задачи: {[j.id for j in remaining_jobs]}")
        else:
            logger.info(f"✅ Проверка: все задачи для {chat_id} успешно удалены")
        
        text = Messages.WATER_STOPPED
        keyboard = [
            [InlineKeyboardButton("▶️ Продолжить уведомления", callback_data='water_resume')],
            [InlineKeyboardButton("« Назад", callback_data='main_menu')]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в water_stop для {chat_id}: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)

async def water_resume(update: Update, context: CallbackContext):
    """Возобновляет напоминания о воде."""
    try:
        chat_id = update.effective_chat.id
        
        # Получаем настройки пользователя
        settings = get_water_reminder(chat_id)
        if not settings:
            # Если пользователя нет в БД, создаем запись
            from app.database import save_water_reminder
            save_water_reminder(chat_id, {
                'is_active': True,
                'onboarding_completed': True,
                'timezone': DEFAULT_TIMEZONE
            })
            settings = get_water_reminder(chat_id)
        
        # Активируем напоминания
        set_water_reminder_active(chat_id, is_active=True)
        
        # Планируем задачи
        job_manager.schedule_water_reminders(
            context.application,
            chat_id,
            settings,
            check_and_send_water_reminder
        )
        
        # Вычисляем время следующего уведомления
        next_time = calculate_next_notification_time(settings.get('timezone', DEFAULT_TIMEZONE))
        next_time_str = next_time.strftime('%d.%m.%Y в %H:%M')
        
        text = Messages.WATER_RESUMED.format(next_time=next_time_str)
        keyboard = [
            [InlineKeyboardButton("⏹️ Остановить", callback_data='water_stop')],
            [InlineKeyboardButton("« Назад", callback_data='main_menu')]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"✅ Напоминания о воде для {chat_id} возобновлены, следующее в {next_time_str}")
    except Exception as e:
        logger.error(f"❌ Ошибка в water_resume: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)


"""
Обработчики напоминаний о воде
ИСПРАВЛЕНА логика отслеживания пропущенных напоминаний
"""
import logging
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from app.config import (
    WATER_MESSAGE, WATER_START_TIME, WATER_END_TIME, WATER_INTERVAL,
    DEFAULT_TIMEZONE, DEFAULT_START_HOUR, DEFAULT_END_HOUR, Messages
)
from app.database import (
    get_water_reminder,
    save_water_reminder,
    set_water_reminder_active,
    save_last_water_reminder_time,
    get_last_water_reminder_time
)
from app.scheduler import job_manager

logger = logging.getLogger(__name__)

# =============================================================================
# ФУНКЦИИ ОТПРАВКИ НАПОМИНАНИЙ
# =============================================================================

async def check_and_send_water_reminder(application, chat_id: int, settings: dict):
    """
    ИСПРАВЛЕННАЯ версия: Проверяет время И отслеживает пропущенные напоминания.
    
    Args:
        application: Telegram Application
        chat_id: ID чата пользователя
        settings: Настройки напоминаний
    """
    try:
        user_tz = pytz.timezone(settings.get('timezone', DEFAULT_TIMEZONE))
        now = datetime.now(user_tz)
        
        # ИСПРАВЛЕНИЕ: Используем значения по умолчанию (8-23) если не установлены
        start_hour = settings.get('start_hour', DEFAULT_START_HOUR)
        end_hour = settings.get('end_hour', DEFAULT_END_HOUR)
        interval_minutes = settings.get('interval_minutes', 60)
        message = settings.get('message', 'Время пить воду! 💧')
        
        logger.info(f"⏰ Проверка времени для {chat_id}: час {now.hour}, диапазон {start_hour}-{end_hour}")
        
        # Проверяем, находимся ли мы в рабочем диапазоне
        if start_hour <= now.hour < end_hour:
            # ИСПРАВЛЕНО: Упрощенная логика пропущенных напоминаний
            last_sent = get_last_water_reminder_time(chat_id)
            
            if last_sent:
                last_sent_dt = datetime.fromisoformat(last_sent)
                if last_sent_dt.tzinfo is None:
                    last_sent_dt = user_tz.localize(last_sent_dt)
                
                time_since_last = (now - last_sent_dt).total_seconds() / 60  # в минутах
                
                # ИСПРАВЛЕНИЕ: Отправляем предупреждение только если пропущено МНОГО (3+)
                # И только один раз, а не за каждое пропущенное
                if time_since_last > interval_minutes * 3:  # Пропущено 3+ напоминания
                    missed_count = int(time_since_last / interval_minutes)
                    warning_text = f"⚠️ Пропущено {missed_count} напоминаний за время отсутствия.\n\n{message}"
                    await application.bot.send_message(chat_id=chat_id, text=warning_text)
                    logger.warning(f"⚠️ Пропущено {missed_count} напоминаний для {chat_id} (время простоя: {time_since_last:.0f} мин)")
                else:
                    # Обычное напоминание без предупреждения о пропущенных
                    await application.bot.send_message(chat_id=chat_id, text=message)
            else:
                # Первое напоминание
                await application.bot.send_message(chat_id=chat_id, text=message)
            
            # Сохраняем время отправки
            save_last_water_reminder_time(chat_id, now.isoformat())
            logger.info(f"✅ Отправлено напоминание о воде для {chat_id}")
        else:
            logger.info(f"⏭️ Напоминание пропущено - час {now.hour} вне диапазона {start_hour}-{end_hour}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке и отправке напоминания о воде: {e}", exc_info=True)

# =============================================================================
# ОБРАБОТЧИКИ МЕНЮ И ДИАЛОГОВ
# =============================================================================

async def water_menu(update: Update, context: CallbackContext):
    """Отображает меню настроек напоминаний о воде."""
    try:
        chat_id = update.effective_chat.id
        settings = get_water_reminder(chat_id)
        text = "💧 **Напоминания о воде**\n\n"
        keyboard = [
            [InlineKeyboardButton("✏️ Изменить настройки", callback_data='water_setup_start')],
            [InlineKeyboardButton("⏹️ Остановить", callback_data='water_stop')]
        ]
        
        if settings and settings.get('is_active', False):
            text += Messages.WATER_STATUS_ACTIVE.format(
                message=settings['message'],
                interval=settings['interval_minutes'],
                start=settings['start_hour'],
                end=settings['end_hour']
            )
        else:
            text += Messages.WATER_STATUS_INACTIVE
            keyboard = [[InlineKeyboardButton("▶️ Настроить и запустить", callback_data='water_setup_start')]]
        
        keyboard.append([InlineKeyboardButton("« Назад", callback_data='main_menu')])
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в water_menu: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)

async def water_setup_start(update: Update, context: CallbackContext):
    """Начинает диалог настройки напоминаний о воде."""
    try:
        context.user_data.clear()
        context.user_data['water_settings'] = {}
        
        logger.info(f"🔧 Начинаем настройку воды для user {update.effective_user.id}")
        await update.callback_query.edit_message_text(
            "Шаг 1/4: Введите текст напоминания (например: Пора пить воду! 💧)"
        )
        return WATER_MESSAGE
    except Exception as e:
        logger.error(f"❌ Ошибка в water_setup_start: {e}", exc_info=True)
        await update.callback_query.edit_message_text(Messages.ERROR_GENERAL)
        return ConversationHandler.END

async def water_get_message(update: Update, context: CallbackContext):
    """Получает текст напоминания от пользователя."""
    try:
        context.user_data['water_settings']['message'] = update.message.text
        await update.message.reply_text("Шаг 2/4: Теперь введите час начала (от 0 до 23).")
        return WATER_START_TIME
    except Exception as e:
        logger.error(f"❌ Ошибка в water_get_message: {e}", exc_info=True)
        return ConversationHandler.END

async def water_get_start_time(update: Update, context: CallbackContext):
    """Получает час начала напоминаний."""
    try:
        hour = int(update.message.text)
        if not 0 <= hour <= 23:
            raise ValueError("Час должен быть от 0 до 23")
        context.user_data['water_settings']['start_time'] = hour
        await update.message.reply_text("Шаг 3/4: Отлично. А теперь час окончания (должен быть больше начального).")
        return WATER_END_TIME
    except (ValueError, TypeError):
        await update.message.reply_text(Messages.ERROR_INVALID_TIME.format(min=0, max=23))
        return WATER_START_TIME

async def water_get_end_time(update: Update, context: CallbackContext):
    """Получает час окончания напоминаний."""
    try:
        hour = int(update.message.text)
        start_hour = context.user_data['water_settings']['start_time']
        if not (start_hour < hour <= 23):
            raise ValueError("Час окончания должен быть больше начального")
        context.user_data['water_settings']['end_time'] = hour
        
        keyboard = [
            [InlineKeyboardButton("30 мин", callback_data='w_int_30'), 
             InlineKeyboardButton("1 час", callback_data='w_int_60')],
            [InlineKeyboardButton("1.5 часа", callback_data='w_int_90'), 
             InlineKeyboardButton("2 часа", callback_data='w_int_120')],
            [InlineKeyboardButton("2.5 часа", callback_data='w_int_150'), 
             InlineKeyboardButton("3 часа", callback_data='w_int_180')],
            [InlineKeyboardButton("4 часа", callback_data='w_int_240')],
        ]
        await update.message.reply_text(
            "Шаг 4/4: Выберите интервал:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WATER_INTERVAL
    except (ValueError, TypeError):
        start_hour = context.user_data['water_settings']['start_time']
        await update.message.reply_text(
            Messages.ERROR_INVALID_TIME.format(min=start_hour + 1, max=23)
        )
        return WATER_END_TIME

async def water_get_interval(update: Update, context: CallbackContext):
    """Получает интервал и завершает настройку напоминаний."""
    try:
        interval = int(update.callback_query.data.split('_')[-1])
        context.user_data['water_settings']['interval'] = interval
        chat_id = update.effective_chat.id
        
        # Получаем все данные из user_data
        user_settings = context.user_data.get('water_settings', {})
        message = user_settings.get('message', 'Время пить воду! 💧')
        # ИСПРАВЛЕНИЕ: Используем значения по умолчанию (8-23) если не установлены
        start_hour = user_settings.get('start_time', DEFAULT_START_HOUR)
        end_hour = user_settings.get('end_time', DEFAULT_END_HOUR)
        
        # ВАЛИДАЦИЯ: проверяем что интервал разумный для рабочего времени
        work_hours = end_hour - start_hour
        max_interval = work_hours * 60
        
        if interval > max_interval:
            await update.callback_query.answer(
                f"❌ Интервал {interval} мин слишком большой для рабочего времени {work_hours} часов (максимум {max_interval} мин)",
                show_alert=True
            )
            return WATER_INTERVAL
        
        # Подготавливаем данные для сохранения
        water_settings = {
            'message': message,
            'start_hour': start_hour,
            'end_hour': end_hour,
            'interval_minutes': interval,
            'timezone': DEFAULT_TIMEZONE,
            'is_active': True
        }
        
        logger.info(f"💾 Сохраняем настройки воды для {chat_id}: {water_settings}")
        
        # Сохраняем в БД
        save_water_reminder(chat_id, water_settings)
        settings = get_water_reminder(chat_id)
        
        if settings:
            # Планируем задачи через job_manager
            job_manager.schedule_water_reminders(
                context.application,
                chat_id,
                settings,
                check_and_send_water_reminder
            )
            
            # Вычисляем время следующего напоминания
            user_tz = pytz.timezone(DEFAULT_TIMEZONE)
            now = datetime.now(user_tz)
            current_hour = now.hour
            
            if start_hour <= current_hour < end_hour:
                next_reminder_time = now + timedelta(minutes=interval)
            elif current_hour < start_hour:
                next_reminder_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            else:
                tomorrow = now + timedelta(days=1)
                next_reminder_time = tomorrow.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            
            next_time_str = next_reminder_time.strftime('%d.%m.%Y в %H:%M')
            
            success_text = Messages.WATER_SETUP_SUCCESS.format(
                next_time=next_time_str,
                interval=interval,
                start=start_hour,
                end=end_hour
            )
            
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]]
            await update.callback_query.edit_message_text(
                success_text, 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"✅ Напоминания о воде настроены для {chat_id}")
        else:
            await update.callback_query.edit_message_text("❌ Ошибка при сохранении настроек.")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ Ошибка в water_get_interval: {e}", exc_info=True)
        await update.callback_query.edit_message_text(Messages.ERROR_GENERAL)
        return ConversationHandler.END

async def water_stop(update: Update, context: CallbackContext):
    """Останавливает напоминания о воде."""
    try:
        chat_id = update.effective_chat.id
        job_id_prefix = f"water_{chat_id}"
        
        # Удаляем все задачи через job_manager
        jobs = job_manager.get_all_jobs()
        removed_count = 0
        for job in jobs:
            if job.id.startswith(job_id_prefix):
                job_manager.remove_job(job.id)
                removed_count += 1
        
        set_water_reminder_active(chat_id, is_active=False)
        logger.info(f"🛑 Напоминания о воде для {chat_id} остановлены ({removed_count} задач)")
        
        await update.callback_query.answer("✅ Напоминания о воде остановлены.")
        await water_menu(update, context)
    except Exception as e:
        logger.error(f"❌ Ошибка в water_stop: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)


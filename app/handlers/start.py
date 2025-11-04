"""
Обработчики команд /start, /reset и общего управления
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from app.database import init_db, get_water_reminder, save_water_reminder, set_onboarding_completed
from app.config import Messages, DEFAULT_TIMEZONE, DEFAULT_START_HOUR, DEFAULT_END_HOUR
from app.scheduler import job_manager
from app.handlers.water_handlers import check_and_send_water_reminder
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext):
    """
    Обработчик команды /start и главного меню.
    Показывает онбординг для новых пользователей или меню управления для существующих.
    """
    try:
        # Убеждаемся, что БД инициализирована
        init_db()
        
        chat_id = update.effective_chat.id
        settings = get_water_reminder(chat_id)
        
        # Проверяем, прошел ли пользователь онбординг
        onboarding_completed = settings.get('onboarding_completed', False) if settings else False
        
        if not onboarding_completed:
            # Показываем онбординг для новых пользователей
            keyboard = [
                [InlineKeyboardButton(Messages.ONBOARDING_BUTTON_TEXT, callback_data='onboarding_activate')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    Messages.ONBOARDING_TEXT,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    Messages.ONBOARDING_TEXT,
                    reply_markup=reply_markup
                )
            logger.info(f"📚 Показан онбординг для пользователя {chat_id}")
        else:
            # Показываем обычное меню для пользователей, прошедших онбординг
            keyboard = [
                [InlineKeyboardButton("💧 Напоминания о воде", callback_data='menu_water')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    Messages.WELCOME, 
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    Messages.WELCOME, 
                    reply_markup=reply_markup
                )
            logger.info(f"✅ Пользователь {chat_id} открыл главное меню")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в функции start: {e}", exc_info=True)
        error_text = Messages.ERROR_GENERAL
        
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def onboarding_activate(update: Update, context: CallbackContext):
    """
    Активирует бота после онбординга.
    Устанавливает флаг onboarding_completed, активирует напоминания и планирует задачи.
    """
    try:
        chat_id = update.effective_chat.id
        
        # Получаем или создаем настройки пользователя
        settings = get_water_reminder(chat_id)
        if not settings:
            # Создаем новую запись для пользователя
            save_water_reminder(chat_id, {
                'is_active': True,
                'onboarding_completed': True,
                'timezone': DEFAULT_TIMEZONE
            })
            settings = get_water_reminder(chat_id)
        else:
            # Обновляем существующую запись
            set_onboarding_completed(chat_id, True)
            from app.database import set_water_reminder_active
            set_water_reminder_active(chat_id, True)
            settings = get_water_reminder(chat_id)
        
        # Планируем задачи через job_manager
        job_manager.schedule_water_reminders(
            context.application,
            chat_id,
            settings,
            check_and_send_water_reminder
        )
        
        # Вычисляем время следующего уведомления
        user_tz = pytz.timezone(settings.get('timezone', DEFAULT_TIMEZONE))
        now = datetime.now(user_tz)
        current_hour = now.hour
        
        if DEFAULT_START_HOUR <= current_hour < DEFAULT_END_HOUR:
            next_hour = current_hour + 1
            next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        elif current_hour < DEFAULT_START_HOUR:
            next_time = now.replace(hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0)
        else:
            tomorrow = now + timedelta(days=1)
            next_time = tomorrow.replace(hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0)
        
        next_time_str = next_time.strftime('%d.%m.%Y в %H:%M')
        
        text = f"✅ Отлично! Бот активирован! 😊\n\nСледующее напоминание: {next_time_str}\n\nУведомления будут приходить каждый час с 08:00 до 23:00 по МСК."
        keyboard = [
            [InlineKeyboardButton("💧 Управление напоминаниями", callback_data='menu_water')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"✅ Пользователь {chat_id} активировал бота, следующее уведомление в {next_time_str}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в onboarding_activate: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)

async def reset_command(update: Update, context: CallbackContext):
    """
    Обработчик команды /reset.
    Сбрасывает состояние пользователя и возвращает в главное меню.
    """
    try:
        context.user_data.clear()
        await update.message.reply_text("✅ Состояние сброшено. Возвращаемся в главное меню.")
        await start(update, context)
        logger.info(f"🔄 Пользователь {update.effective_user.id} выполнил reset")
    except Exception as e:
        logger.error(f"❌ Ошибка в reset_command: {e}", exc_info=True)
        await update.message.reply_text(Messages.ERROR_GENERAL)

async def cancel(update: Update, context: CallbackContext):
    """
    Отменяет текущий диалог и возвращает в главное меню.
    Используется как fallback в ConversationHandler.
    """
    try:
        await update.message.reply_text("❌ Действие отменено.")
        context.user_data.clear()
        await start(update, context)
        logger.info(f"🚫 Пользователь {update.effective_user.id} отменил операцию")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"❌ Ошибка в cancel: {e}", exc_info=True)
        await update.message.reply_text(Messages.ERROR_GENERAL)
        return ConversationHandler.END


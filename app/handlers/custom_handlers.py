"""
Обработчики кастомных напоминаний
"""
import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from app.config import (
    CUSTOM_MESSAGE, CUSTOM_TIME, CUSTOM_FREQUENCY,
    DEFAULT_TIMEZONE, MAX_CUSTOM_REMINDERS_PER_USER,
    FREQUENCY_TYPES, Messages
)
from app.database import (
    get_custom_reminders,
    get_custom_reminder_by_id,
    get_custom_reminders_count,
    add_custom_reminder,
    delete_custom_reminder
)
from app.scheduler import job_manager

logger = logging.getLogger(__name__)

# =============================================================================
# ФУНКЦИИ ОТПРАВКИ НАПОМИНАНИЙ
# =============================================================================

async def send_custom_message(application, chat_id: int, reminder_data: dict):
    """
    Отправляет пользовательское повторяющееся напоминание.
    
    Args:
        application: Telegram Application
        chat_id: ID чата пользователя
        reminder_data: Данные напоминания (id, message)
    """
    try:
        await application.bot.send_message(chat_id=chat_id, text=reminder_data['message'])
        logger.info(f"✅ Отправлено кастомное напоминание {reminder_data['id']}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке кастомного напоминания: {e}", exc_info=True)

async def send_once_and_delete_custom(application, chat_id: int, reminder_data: dict):
    """
    Отправляет одноразовое напоминание и удаляет его из БД.
    
    Args:
        application: Telegram Application
        chat_id: ID чата пользователя
        reminder_data: Данные напоминания (id, message)
    """
    try:
        await application.bot.send_message(chat_id=chat_id, text=reminder_data['message'])
        delete_custom_reminder(reminder_data['id'])
        logger.info(f"✅ Одноразовое напоминание {reminder_data['id']} отправлено и удалено")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке одноразового напоминания: {e}", exc_info=True)

# =============================================================================
# ОБРАБОТЧИКИ МЕНЮ И ДИАЛОГОВ
# =============================================================================

async def custom_menu(update: Update, context: CallbackContext):
    """Отображает список кастомных напоминаний пользователя."""
    try:
        chat_id = update.effective_chat.id
        reminders = get_custom_reminders(chat_id)
        text = "🗓️ **Мои напоминания**\n\n"
        keyboard = []
        
        if not reminders:
            text += "У вас пока нет напоминаний."
        else:
            user_tz = pytz.timezone(DEFAULT_TIMEZONE)
            for r in reminders:
                reminder_time = datetime.fromisoformat(r['reminder_time'])
                if reminder_time.tzinfo is None:
                    reminder_time = user_tz.localize(reminder_time)
                
                rem_time = reminder_time.strftime('%d.%m.%Y в %H:%M')
                msg_preview = r['message'] if len(r['message']) < 25 else r['message'][:22] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"«{msg_preview}» ({rem_time})", 
                        callback_data=f"custom_view_{r['id']}"
                    ),
                    InlineKeyboardButton("🗑️", callback_data=f"custom_delete_{r['id']}")
                ])
        
        if len(reminders) < MAX_CUSTOM_REMINDERS_PER_USER:
            keyboard.append([InlineKeyboardButton("➕ Добавить новое", callback_data='custom_add_start')])
        
        keyboard.append([InlineKeyboardButton("« Назад", callback_data='main_menu')])
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в custom_menu: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)

async def custom_view(update: Update, context: CallbackContext):
    """Показывает детали конкретного напоминания."""
    try:
        reminder_id = int(update.callback_query.data.split('_')[-1])
        reminder = get_custom_reminder_by_id(reminder_id)
        
        if not reminder:
            await update.callback_query.answer("❌ Напоминание не найдено.")
            return
        
        reminder_time = datetime.fromisoformat(reminder['reminder_time'])
        user_tz = pytz.timezone(reminder.get('timezone', DEFAULT_TIMEZONE))
        
        if reminder_time.tzinfo is None:
            reminder_time = user_tz.localize(reminder_time)
        
        frequency_text = FREQUENCY_TYPES.get(reminder['frequency'], reminder['frequency'])
        
        text = (
            f"📝 **Детали напоминания**\n\n"
            f"**Сообщение:** {reminder['message']}\n"
            f"**Время:** {reminder_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"**Повтор:** {frequency_text}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Удалить", callback_data=f"custom_delete_{reminder_id}")],
            [InlineKeyboardButton("« Назад к списку", callback_data='menu_custom')]
        ]
        
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в custom_view: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)

async def custom_add_start(update: Update, context: CallbackContext):
    """Начинает диалог создания кастомного напоминания."""
    try:
        if get_custom_reminders_count(update.effective_chat.id) >= MAX_CUSTOM_REMINDERS_PER_USER:
            await update.callback_query.answer(
                Messages.ERROR_LIMIT_REACHED.format(limit=MAX_CUSTOM_REMINDERS_PER_USER),
                show_alert=True
            )
            return ConversationHandler.END
        
        context.user_data['custom_reminder'] = {}
        await update.callback_query.edit_message_text("Шаг 1/3: Введите текст напоминания.")
        return CUSTOM_MESSAGE
    except Exception as e:
        logger.error(f"❌ Ошибка в custom_add_start: {e}", exc_info=True)
        return ConversationHandler.END

async def custom_get_message(update: Update, context: CallbackContext):
    """Получает текст кастомного напоминания."""
    try:
        context.user_data['custom_reminder']['message'] = update.message.text
        await update.message.reply_text(
            "Шаг 2/3: Теперь введите дату и время в формате `ДД.ММ.ГГГГ ЧЧ:ММ` (например: `04.07.2025 15:30`)."
        )
        return CUSTOM_TIME
    except Exception as e:
        logger.error(f"❌ Ошибка в custom_get_message: {e}", exc_info=True)
        return ConversationHandler.END

async def custom_get_time(update: Update, context: CallbackContext):
    """Получает дату и время кастомного напоминания."""
    try:
        dt_obj = datetime.strptime(update.message.text, '%d.%m.%Y %H:%M')
        
        # Проверка, что дата не в прошлом
        user_tz = pytz.timezone(DEFAULT_TIMEZONE)
        if user_tz.localize(dt_obj) < datetime.now(user_tz):
            await update.message.reply_text(Messages.ERROR_DATE_IN_PAST)
            return CUSTOM_TIME
        
        context.user_data['custom_reminder']['time'] = dt_obj.isoformat()
        
        keyboard = [
            [InlineKeyboardButton("Только один раз", callback_data='c_freq_once')],
            [InlineKeyboardButton("Каждый день", callback_data='c_freq_daily')],
            [InlineKeyboardButton("Каждую неделю", callback_data='c_freq_weekly')],
        ]
        await update.message.reply_text(
            "Шаг 3/3: Как часто повторять?", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CUSTOM_FREQUENCY
    except ValueError:
        await update.message.reply_text(Messages.ERROR_INVALID_DATE_FORMAT)
        return CUSTOM_TIME

async def custom_get_frequency(update: Update, context: CallbackContext):
    """Получает частоту повторения и создает напоминание."""
    try:
        frequency = update.callback_query.data.split('_')[-1]
        context.user_data['custom_reminder']['frequency'] = frequency
        chat_id = update.effective_chat.id
        reminder_data = context.user_data['custom_reminder']
        
        # Добавляем в БД
        reminder_id = add_custom_reminder(
            chat_id,
            reminder_data['message'],
            reminder_data['time'],
            reminder_data['frequency'],
            DEFAULT_TIMEZONE
        )
        
        if reminder_id:
            reminder = get_custom_reminder_by_id(reminder_id)
            
            # Планируем задачу через job_manager
            result = job_manager.schedule_custom_reminder(
                context.application,
                reminder,
                send_once_and_delete_custom if frequency == 'once' else send_custom_message
            )
            
            # ИСПРАВЛЕНО: Обработка пропущенного одноразового напоминания
            if result == 'missed_once':
                reminder_time = datetime.fromisoformat(reminder_data['time'])
                user_tz = pytz.timezone(DEFAULT_TIMEZONE)
                if reminder_time.tzinfo is None:
                    reminder_time = user_tz.localize(reminder_time)
                
                # Отправляем уведомление о пропуске
                missed_text = Messages.MISSED_CUSTOM_REMINDER.format(
                    message=reminder_data['message'],
                    time=reminder_time.strftime('%d.%m.%Y в %H:%M')
                )
                await context.application.bot.send_message(chat_id=chat_id, text=missed_text)
                
                # Удаляем из БД
                delete_custom_reminder(reminder_id)
                logger.warning(f"⚠️ Пропущенное одноразовое напоминание {reminder_id} отправлено и удалено")
                
                keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]]
                await update.callback_query.edit_message_text(
                    missed_text, 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # Успешно запланировано
                reminder_time = datetime.fromisoformat(reminder_data['time'])
                user_tz = pytz.timezone(DEFAULT_TIMEZONE)
                
                if reminder_time.tzinfo is None:
                    reminder_time = user_tz.localize(reminder_time)
                
                time_str = reminder_time.strftime('%d.%m.%Y в %H:%M')
                frequency_text = FREQUENCY_TYPES.get(frequency, frequency).lower()
                
                success_text = Messages.CUSTOM_REMINDER_SUCCESS.format(
                    message=reminder_data['message'],
                    time=time_str,
                    frequency=frequency_text
                )
                
                keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]]
                await update.callback_query.edit_message_text(
                    success_text, 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info(f"✅ Кастомное напоминание {reminder_id} создано")
        else:
            await update.callback_query.edit_message_text("❌ Произошла ошибка при создании напоминания.")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ Ошибка в custom_get_frequency: {e}", exc_info=True)
        await update.callback_query.edit_message_text(Messages.ERROR_GENERAL)
        return ConversationHandler.END

async def custom_delete(update: Update, context: CallbackContext):
    """Удаляет кастомное напоминание."""
    try:
        reminder_id = int(update.callback_query.data.split('_')[-1])
        job_id = f"custom_{reminder_id}"
        
        # Удаляем задачу из планировщика
        job_manager.remove_job(job_id)
        
        # Удаляем из БД
        delete_custom_reminder(reminder_id)
        
        await update.callback_query.answer("✅ Напоминание удалено.")
        await custom_menu(update, context)
        logger.info(f"🗑️ Кастомное напоминание {reminder_id} удалено")
    except Exception as e:
        logger.error(f"❌ Ошибка в custom_delete: {e}", exc_info=True)
        await update.callback_query.answer(Messages.ERROR_GENERAL)


"""
Обработчики команд /start, /reset и общего управления
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from app.database import init_db
from app.config import Messages

logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext):
    """
    Обработчик команды /start и главного меню.
    Показывает приветственное сообщение и основные кнопки навигации.
    """
    try:
        # Убеждаемся, что БД инициализирована
        init_db()
        
        keyboard = [
            [InlineKeyboardButton("💧 Напоминания о воде", callback_data='menu_water')],
            [InlineKeyboardButton("🗓️ Мои напоминания", callback_data='menu_custom')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Проверяем, вызвано из callback_query или напрямую
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
            
        logger.info(f"✅ Пользователь {update.effective_user.id} открыл главное меню")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в функции start: {e}", exc_info=True)
        error_text = Messages.ERROR_GENERAL
        
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

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


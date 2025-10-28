"""
Операции с БД для кастомных напоминаний
"""
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pytz
from .models import DB_NAME

logger = logging.getLogger(__name__)

# =============================================================================
# ФУНКЦИИ ДЛЯ КАСТОМНЫХ НАПОМИНАНИЙ
# =============================================================================

def add_custom_reminder(chat_id: int, message: str, reminder_time: str, frequency: str, timezone: str) -> Optional[int]:
    """
    Добавляет новое кастомное напоминание и возвращает его ID.
    
    Args:
        chat_id: ID чата пользователя
        message: Текст напоминания
        reminder_time: Время напоминания в ISO формате
        frequency: Частота ('once', 'daily', 'weekly')
        timezone: Часовой пояс
        
    Returns:
        ID созданного напоминания или None в случае ошибки
    """
    try:
        # Валидация входных данных
        if not message.strip():
            logger.error("❌ Пустое сообщение для кастомного напоминания")
            return None
            
        if frequency not in ['once', 'daily', 'weekly']:
            logger.error(f"❌ Недопустимая частота: {frequency}")
            return None
            
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO custom_reminders (chat_id, message, reminder_time, frequency, timezone)
                VALUES (?, ?, ?, ?, ?)
            """, (chat_id, message, reminder_time, frequency, timezone))
            con.commit()
            reminder_id = cur.lastrowid
            logger.info(f"✅ Добавлено кастомное напоминание ID {reminder_id} для {chat_id}")
            return reminder_id
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при добавлении кастомного напоминания для {chat_id}: {e}")
        return None

def get_custom_reminders(chat_id: int) -> List[Dict[str, Any]]:
    """
    Получает все кастомные напоминания пользователя.
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Список словарей с данными напоминаний
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                SELECT * FROM custom_reminders 
                WHERE chat_id = ? AND is_active = 1 
                ORDER BY reminder_time
            """, (chat_id,))
            rows = cur.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict['is_active'] = bool(row_dict['is_active'])
                result.append(row_dict)
            return result
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении кастомных напоминаний для {chat_id}: {e}")
        return []

def get_custom_reminder_by_id(reminder_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает одно кастомное напоминание по его ID.
    
    Args:
        reminder_id: ID напоминания
        
    Returns:
        Словарь с данными напоминания или None, если не найдено
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM custom_reminders WHERE id = ?", (reminder_id,))
            row = cur.fetchone()
            if row:
                result = dict(row)
                result['is_active'] = bool(result['is_active'])
                return result
            return None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении кастомного напоминания ID {reminder_id}: {e}")
        return None

def delete_custom_reminder(reminder_id: int) -> bool:
    """
    Удаляет кастомное напоминание по ID.
    
    Args:
        reminder_id: ID напоминания для удаления
        
    Returns:
        True если удаление успешно, False в случае ошибки
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM custom_reminders WHERE id = ?", (reminder_id,))
            con.commit()
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ Кастомное напоминание ID {reminder_id} не найдено для удаления")
                return False
            else:
                logger.info(f"🗑️ Кастомное напоминание ID {reminder_id} удалено")
                return True
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при удалении кастомного напоминания ID {reminder_id}: {e}")
        return False

def update_custom_reminder(reminder_id: int, field: str, value: Any) -> bool:
    """
    Обновляет определенное поле кастомного напоминания.
    
    Args:
        reminder_id: ID напоминания
        field: Название поля для обновления
        value: Новое значение
        
    Returns:
        True если обновление успешно, False в случае ошибки
    """
    # Проверка на допустимые поля для предотвращения SQL-инъекций
    allowed_fields = ['message', 'reminder_time', 'frequency', 'timezone', 'is_active']
    if field not in allowed_fields:
        logger.error(f"❌ Попытка обновить недопустимое поле: {field}")
        return False
        
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            query = f"UPDATE custom_reminders SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            cur.execute(query, (value, reminder_id))
            con.commit()
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ Кастомное напоминание ID {reminder_id} не найдено для обновления")
                return False
            else:
                logger.info(f"✅ Поле {field} для напоминания ID {reminder_id} обновлено")
                return True
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при обновлении напоминания ID {reminder_id}: {e}")
        return False

def set_custom_reminder_active(reminder_id: int, is_active: bool) -> bool:
    """
    Включает или выключает кастомное напоминание.
    
    Args:
        reminder_id: ID напоминания
        is_active: True для включения, False для выключения
        
    Returns:
        True если обновление успешно
    """
    return update_custom_reminder(reminder_id, 'is_active', int(is_active))

def get_all_active_custom_reminders() -> List[Dict[str, Any]]:
    """
    Возвращает все активные кастомные напоминания для восстановления.
    
    Returns:
        Список словарей с данными всех активных напоминаний
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM custom_reminders WHERE is_active = 1")
            rows = cur.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict['is_active'] = bool(row_dict['is_active'])
                result.append(row_dict)
            return result
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении всех активных кастомных напоминаний: {e}")
        return []

def get_custom_reminders_count(chat_id: int) -> int:
    """
    Возвращает количество активных кастомных напоминаний пользователя.
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Количество активных напоминаний
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM custom_reminders WHERE chat_id = ? AND is_active = 1", (chat_id,))
            count = cur.fetchone()[0]
            return count
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при подсчете кастомных напоминаний для {chat_id}: {e}")
        return 0

def cleanup_old_reminders():
    """
    ИСПРАВЛЕНО: Удаляет только прошедшие одноразовые напоминания (с буфером 1 час).
    Повторяющиеся напоминания (daily/weekly) НЕ удаляются.
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            # ИСПРАВЛЕНО: Только 'once' напоминания
            cur.execute("""
                SELECT id, reminder_time, timezone FROM custom_reminders 
                WHERE frequency = 'once' AND is_active = 1
            """)
            reminders = cur.fetchall()
            
            deleted_count = 0
            for reminder in reminders:
                reminder_id, reminder_time_str, timezone_str = reminder
                try:
                    reminder_time = datetime.fromisoformat(reminder_time_str)
                    user_tz = pytz.timezone(timezone_str)
                    
                    if reminder_time.tzinfo is None:
                        reminder_time = user_tz.localize(reminder_time)
                    
                    # ИСПРАВЛЕНО: Удаляем только если прошло больше 1 часа (даем время на misfire)
                    cutoff_time = datetime.now(user_tz) - timedelta(hours=1)
                    if reminder_time < cutoff_time:
                        cur.execute("DELETE FROM custom_reminders WHERE id = ?", (reminder_id,))
                        deleted_count += 1
                        logger.info(f"🗑️ Удалено прошедшее напоминание ID {reminder_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке напоминания ID {reminder_id}: {e}")
            
            con.commit()
            if deleted_count > 0:
                logger.info(f"✅ Очистка завершена. Удалено {deleted_count} прошедших напоминаний.")
                
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при очистке старых напоминаний: {e}")


"""
Операции с БД для напоминаний о воде
"""
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from .models import DB_NAME

logger = logging.getLogger(__name__)

# =============================================================================
# ФУНКЦИИ ДЛЯ НАПОМИНАНИЙ О ВОДЕ
# =============================================================================

def save_water_reminder(chat_id: int, settings: Dict[str, Any]):
    """
    Сохраняет или обновляет настройки напоминания о воде для пользователя.
    
    Args:
        chat_id: ID чата пользователя
        settings: Словарь с настройками (message, interval_minutes, start_hour, end_hour, timezone, is_active)
    """
    try:
        logger.info(f"💾 Сохраняем настройки воды для {chat_id}: {settings}")
        
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            message = settings.get('message', 'Время пить воду! 💧')
            interval_minutes = settings.get('interval_minutes', settings.get('interval', 60))
            start_hour = settings.get('start_hour', settings.get('start_time', 9))
            end_hour = settings.get('end_hour', settings.get('end_time', 21))
            timezone = settings.get('timezone', 'Etc/GMT-3')
            is_active = settings.get('is_active', True)
            
            cur.execute("""
                INSERT INTO water_reminders (chat_id, message, interval_minutes, start_hour, end_hour, timezone, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    message = excluded.message,
                    interval_minutes = excluded.interval_minutes,
                    start_hour = excluded.start_hour,
                    end_hour = excluded.end_hour,
                    timezone = excluded.timezone,
                    is_active = excluded.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, message, interval_minutes, start_hour, end_hour, timezone, int(is_active)))
            con.commit()
            logger.info(f"✅ Настройки напоминания о воде для {chat_id} успешно сохранены")
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка БД при сохранении настроек воды для {chat_id}: {e}")
        raise

def get_water_reminder(chat_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает настройки напоминания о воде для пользователя.
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Словарь с настройками или None, если не найдено
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM water_reminders WHERE chat_id = ?", (chat_id,))
            row = cur.fetchone()
            if row:
                result = dict(row)
                result['is_active'] = bool(result['is_active'])
                return result
            return None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении настроек воды для {chat_id}: {e}")
        return None

def set_water_reminder_active(chat_id: int, is_active: bool):
    """
    Включает или выключает напоминание о воде.
    
    Args:
        chat_id: ID чата пользователя
        is_active: True для включения, False для выключения
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE water_reminders 
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE chat_id = ?
            """, (int(is_active), chat_id))
            con.commit()
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ Напоминание о воде для {chat_id} не найдено для обновления")
            else:
                logger.info(f"✅ Статус напоминания о воде для {chat_id} изменен на {is_active}")
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при изменении статуса напоминания о воде для {chat_id}: {e}")
        raise

def get_all_active_water_reminders() -> List[Dict[str, Any]]:
    """
    Возвращает все активные напоминания о воде для восстановления при перезапуске.
    
    Returns:
        Список словарей с настройками всех активных напоминаний
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM water_reminders WHERE is_active = 1")
            rows = cur.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict['is_active'] = bool(row_dict['is_active'])
                result.append(row_dict)
            return result
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении всех активных напоминаний о воде: {e}")
        return []

# =============================================================================
# НОВЫЕ ФУНКЦИИ: История отправки напоминаний о воде
# Решает проблему с отслеживанием пропущенных уведомлений
# =============================================================================

def save_last_water_reminder_time(chat_id: int, timestamp: str) -> bool:
    """
    Сохраняет время последнего отправленного напоминания о воде.
    
    Args:
        chat_id: ID чата пользователя
        timestamp: ISO формат времени отправки
        
    Returns:
        True если успешно сохранено, False в случае ошибки
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO water_reminder_history (chat_id, last_sent_time)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET 
                    last_sent_time = excluded.last_sent_time,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, timestamp))
            con.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при сохранении истории напоминания: {e}")
        return False

def get_last_water_reminder_time(chat_id: int) -> Optional[str]:
    """
    Получает время последнего отправленного напоминания о воде.
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        ISO формат времени или None, если не найдено
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("SELECT last_sent_time FROM water_reminder_history WHERE chat_id = ?", (chat_id,))
            row = cur.fetchone()
            return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении истории напоминания: {e}")
        return None


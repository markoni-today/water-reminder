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
    Использует фиксированные значения: 8-23, 60 минут, фиксированное сообщение.
    
    Args:
        chat_id: ID чата пользователя
        settings: Словарь с настройками (is_active, onboarding_completed, timezone)
    """
    try:
        logger.info(f"💾 Сохраняем настройки воды для {chat_id}: {settings}")
        
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            # Фиксированные значения
            message = 'Время пить воду! 💧'
            interval_minutes = 60
            start_hour = 8
            end_hour = 23
            timezone = settings.get('timezone', 'Etc/GMT-3')
            is_active = settings.get('is_active', True)
            onboarding_completed = settings.get('onboarding_completed', False)
            
            cur.execute("""
                INSERT INTO water_reminders (chat_id, message, interval_minutes, start_hour, end_hour, timezone, is_active, onboarding_completed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    message = excluded.message,
                    interval_minutes = excluded.interval_minutes,
                    start_hour = excluded.start_hour,
                    end_hour = excluded.end_hour,
                    timezone = excluded.timezone,
                    is_active = excluded.is_active,
                    onboarding_completed = excluded.onboarding_completed,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, message, interval_minutes, start_hour, end_hour, timezone, int(is_active), int(onboarding_completed)))
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
                result['onboarding_completed'] = bool(result.get('onboarding_completed', False))
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
                row_dict['onboarding_completed'] = bool(row_dict.get('onboarding_completed', False))
                result.append(row_dict)
            return result
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при получении всех активных напоминаний о воде: {e}")
        return []

def set_onboarding_completed(chat_id: int, completed: bool = True):
    """
    Устанавливает флаг прохождения онбординга для пользователя.
    
    Args:
        chat_id: ID чата пользователя
        completed: True если онбординг пройден, False если нет
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE water_reminders 
                SET onboarding_completed = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE chat_id = ?
            """, (int(completed), chat_id))
            con.commit()
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ Напоминание о воде для {chat_id} не найдено для обновления onboarding_completed")
            else:
                logger.info(f"✅ Флаг onboarding_completed для {chat_id} изменен на {completed}")
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при изменении onboarding_completed для {chat_id}: {e}")
        raise



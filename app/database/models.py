"""
Определения таблиц БД и функции инициализации
"""
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Глобальная переменная для имени базы данных
DB_NAME = "reminders.db"

def set_db_name(db_name: str):
    """Устанавливает имя базы данных для всех операций."""
    global DB_NAME
    DB_NAME = db_name
    logger.info(f"База данных установлена: {DB_NAME}")

def get_connection():
    """Возвращает соединение с БД."""
    return sqlite3.connect(DB_NAME)

def init_db(db_name: Optional[str] = None):
    """
    Инициализирует базу данных и создает все необходимые таблицы.
    
    Args:
        db_name: Имя файла базы данных (если None, используется DB_NAME)
    """
    global DB_NAME
    if db_name is None:
        db_name = DB_NAME
    else:
        DB_NAME = db_name
    
    try:
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        
        # ==================================================================
        # ТАБЛИЦА: Настройки напоминаний о воде
        # ==================================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS water_reminders (
                chat_id INTEGER PRIMARY KEY,
                message TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL,
                start_hour INTEGER NOT NULL,
                end_hour INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                onboarding_completed BOOLEAN DEFAULT 0,
                timezone TEXT DEFAULT 'Etc/GMT-3',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ==================================================================
        # ИНДЕКСЫ для производительности
        # ==================================================================
        cur.execute("CREATE INDEX IF NOT EXISTS idx_water_active ON water_reminders(is_active)")
        
        con.commit()
        logger.info("✅ База данных успешно инициализирована")
        
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        raise
    finally:
        if con:
            con.close()


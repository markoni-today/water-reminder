"""
Миграции базы данных
"""
import sqlite3
import logging
from .models import DB_NAME

logger = logging.getLogger(__name__)

def check_column_exists(cur, table_name: str, column_name: str) -> bool:
    """Проверяет существование колонки в таблице."""
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cur.fetchall()]
    return column_name in columns

def migrate_add_updated_at():
    """
    Добавляет колонку updated_at в таблицы, если её нет.
    
    ИСПРАВЛЕНО: Проверяет существование таблиц перед добавлением колонок.
    """
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            # Проверяем и добавляем updated_at в water_reminders
            if not check_column_exists(cur, 'water_reminders', 'updated_at'):
                logger.info("➕ Добавляем колонку updated_at в water_reminders")
                cur.execute("""
                    ALTER TABLE water_reminders 
                    ADD COLUMN updated_at TEXT
                """)
                # Устанавливаем значение по умолчанию для существующих записей
                cur.execute("""
                    UPDATE water_reminders 
                    SET updated_at = datetime('now') 
                    WHERE updated_at IS NULL
                """)
                con.commit()
                logger.info("✅ Колонка updated_at добавлена в water_reminders")
            else:
                logger.info("✓ Колонка updated_at уже существует в water_reminders")
            
            # ИСПРАВЛЕНИЕ: Проверяем существование таблицы custom_reminders перед работой с ней
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_reminders'")
            if cur.fetchone():
                # Таблица существует - добавляем updated_at
                if not check_column_exists(cur, 'custom_reminders', 'updated_at'):
                    logger.info("➕ Добавляем колонку updated_at в custom_reminders")
                    cur.execute("""
                        ALTER TABLE custom_reminders 
                        ADD COLUMN updated_at TEXT
                    """)
                    cur.execute("""
                        UPDATE custom_reminders 
                        SET updated_at = datetime('now') 
                        WHERE updated_at IS NULL
                    """)
                    con.commit()
                    logger.info("✅ Колонка updated_at добавлена в custom_reminders")
                else:
                    logger.info("✓ Колонка updated_at уже существует в custom_reminders")
            else:
                logger.info("✓ Таблица custom_reminders не существует (уже удалена или не создавалась)")
            
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при выполнении миграции: {e}")
        raise

def migrate_remove_custom_tables():
    """Удаляет таблицы кастомных напоминаний и истории."""
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            # Удаляем таблицу custom_reminders если существует
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_reminders'")
            if cur.fetchone():
                logger.info("🗑️ Удаляем таблицу custom_reminders")
                cur.execute("DROP TABLE IF EXISTS custom_reminders")
                con.commit()
                logger.info("✅ Таблица custom_reminders удалена")
            else:
                logger.info("✓ Таблица custom_reminders не существует")
            
            # Удаляем таблицу water_reminder_history если существует
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='water_reminder_history'")
            if cur.fetchone():
                logger.info("🗑️ Удаляем таблицу water_reminder_history")
                cur.execute("DROP TABLE IF EXISTS water_reminder_history")
                con.commit()
                logger.info("✅ Таблица water_reminder_history удалена")
            else:
                logger.info("✓ Таблица water_reminder_history не существует")
            
            # Удаляем индексы для custom_reminders если существуют
            cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_custom%'")
            indexes = cur.fetchall()
            for index in indexes:
                logger.info(f"🗑️ Удаляем индекс {index[0]}")
                cur.execute(f"DROP INDEX IF EXISTS {index[0]}")
                con.commit()
            
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при удалении таблиц: {e}")
        raise

def migrate_add_onboarding_completed():
    """Добавляет колонку onboarding_completed в water_reminders."""
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            if not check_column_exists(cur, 'water_reminders', 'onboarding_completed'):
                logger.info("➕ Добавляем колонку onboarding_completed в water_reminders")
                cur.execute("""
                    ALTER TABLE water_reminders 
                    ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0
                """)
                # Сбрасываем onboarding_completed для всех существующих пользователей
                cur.execute("""
                    UPDATE water_reminders 
                    SET onboarding_completed = 0
                    WHERE onboarding_completed IS NULL
                """)
                con.commit()
                logger.info("✅ Колонка onboarding_completed добавлена в water_reminders")
            else:
                logger.info("✓ Колонка onboarding_completed уже существует в water_reminders")
            
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при добавлении onboarding_completed: {e}")
        raise

def run_all_migrations():
    """Запускает все необходимые миграции."""
    logger.info("🔄 Запуск миграций базы данных...")
    migrate_add_updated_at()
    migrate_remove_custom_tables()
    migrate_add_onboarding_completed()
    logger.info("✅ Все миграции выполнены успешно")

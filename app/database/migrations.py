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
    """Добавляет колонку updated_at в таблицы, если её нет."""
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
                # Используем created_at если есть, иначе текущее время
                if check_column_exists(cur, 'water_reminders', 'created_at'):
                    cur.execute("""
                        UPDATE water_reminders 
                        SET updated_at = created_at 
                        WHERE updated_at IS NULL
                    """)
                else:
                    cur.execute("""
                        UPDATE water_reminders 
                        SET updated_at = datetime('now') 
                        WHERE updated_at IS NULL
                    """)
                con.commit()
                logger.info("✅ Колонка updated_at добавлена в water_reminders")
            else:
                logger.info("✓ Колонка updated_at уже существует в water_reminders")
            
            # Проверяем и добавляем updated_at в custom_reminders
            if not check_column_exists(cur, 'custom_reminders', 'updated_at'):
                logger.info("➕ Добавляем колонку updated_at в custom_reminders")
                cur.execute("""
                    ALTER TABLE custom_reminders 
                    ADD COLUMN updated_at TEXT
                """)
                # Устанавливаем значение по умолчанию для существующих записей
                # Используем created_at если есть, иначе текущее время
                if check_column_exists(cur, 'custom_reminders', 'created_at'):
                    cur.execute("""
                        UPDATE custom_reminders 
                        SET updated_at = created_at 
                        WHERE updated_at IS NULL
                    """)
                else:
                    cur.execute("""
                        UPDATE custom_reminders 
                        SET updated_at = datetime('now') 
                        WHERE updated_at IS NULL
                    """)
                con.commit()
                logger.info("✅ Колонка updated_at добавлена в custom_reminders")
            else:
                logger.info("✓ Колонка updated_at уже существует в custom_reminders")
            
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка при выполнении миграции: {e}")
        raise

def run_all_migrations():
    """Запускает все необходимые миграции."""
    logger.info("🔄 Запуск миграций базы данных...")
    migrate_add_updated_at()
    logger.info("✅ Все миграции выполнены успешно")

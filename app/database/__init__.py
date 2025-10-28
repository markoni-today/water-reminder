"""
Инициализация модуля database
"""
from .models import init_db, set_db_name, DB_NAME
from .water_db import (
    save_water_reminder,
    get_water_reminder,
    set_water_reminder_active,
    get_all_active_water_reminders,
    save_last_water_reminder_time,
    get_last_water_reminder_time
)
from .custom_db import (
    add_custom_reminder,
    get_custom_reminder_by_id,
    get_custom_reminders,
    get_custom_reminders_count,
    delete_custom_reminder,
    set_custom_reminder_active,
    get_all_active_custom_reminders,
    cleanup_old_reminders
)

# Алиасы для обратной совместимости
save_custom_reminder = add_custom_reminder
get_custom_reminder = get_custom_reminder_by_id
get_custom_reminders_for_user = get_custom_reminders
from .migrations import run_all_migrations

__all__ = [
    'init_db',
    'set_db_name',
    'DB_NAME',
    'save_water_reminder',
    'get_water_reminder',
    'set_water_reminder_active',
    'get_all_active_water_reminders',
    'save_last_water_reminder_time',
    'get_last_water_reminder_time',
    'add_custom_reminder',
    'save_custom_reminder',  # алиас
    'get_custom_reminder_by_id',
    'get_custom_reminder',  # алиас
    'get_custom_reminders',
    'get_custom_reminders_count',
    'get_custom_reminders_for_user',  # алиас
    'delete_custom_reminder',
    'set_custom_reminder_active',
    'get_all_active_custom_reminders',
    'cleanup_old_reminders',
    'run_all_migrations'
]


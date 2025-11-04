"""
Инициализация модуля database
"""
from .models import init_db, set_db_name, DB_NAME
from .water_db import (
    save_water_reminder,
    get_water_reminder,
    set_water_reminder_active,
    get_all_active_water_reminders,
    set_onboarding_completed
)
from .migrations import run_all_migrations

__all__ = [
    'init_db',
    'set_db_name',
    'DB_NAME',
    'save_water_reminder',
    'get_water_reminder',
    'set_water_reminder_active',
    'get_all_active_water_reminders',
    'set_onboarding_completed',
    'run_all_migrations'
]


"""
Обработчики Telegram бота
"""
from .start import start, reset_command, cancel
from .water_handlers import (
    water_menu,
    water_setup_start,
    water_get_message,
    water_get_start_time,
    water_get_end_time,
    water_get_interval,
    water_stop,
    check_and_send_water_reminder
)
from .custom_handlers import (
    custom_menu,
    custom_view,
    custom_add_start,
    custom_get_message,
    custom_get_time,
    custom_get_frequency,
    custom_delete,
    send_custom_message,
    send_once_and_delete_custom
)

__all__ = [
    'start',
    'reset_command',
    'cancel',
    'water_menu',
    'water_setup_start',
    'water_get_message',
    'water_get_start_time',
    'water_get_end_time',
    'water_get_interval',
    'water_stop',
    'check_and_send_water_reminder',
    'custom_menu',
    'custom_view',
    'custom_add_start',
    'custom_get_message',
    'custom_get_time',
    'custom_get_frequency',
    'custom_delete',
    'send_custom_message',
    'send_once_and_delete_custom'
]


"""
Менеджер задач для APScheduler с персистентным хранилищем.
ИСПРАВЛЕНО: Решена проблема с pickle для вложенных замыканий.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from ..config import (
    DEFAULT_TIMEZONE,
    DEFAULT_START_HOUR,
    DEFAULT_END_HOUR,
    MISFIRE_GRACE_TIME
)
from .async_wrapper import async_to_sync

logger = logging.getLogger(__name__)

# ============================================================================
# НОВОЕ: Сериализуемые callable классы для задач
# ============================================================================

class WaterReminderJob:
    """
    Сериализуемая задача для напоминаний о воде.
    Использует глобальный job_manager для получения application и функции.
    """
    def __init__(self, chat_id: int, settings: Dict[str, Any]):
        self.chat_id = chat_id
        self.settings = settings
    
    def __call__(self):
        """Вызывается планировщиком при выполнении задачи."""
        try:
            logger.info(f"🔔 WaterReminderJob вызван для chat_id={self.chat_id}")
            from . import job_manager  # Импортируем глобальный экземпляр
            
            if job_manager.application is None or job_manager.water_send_func is None:
                logger.error("❌ Application или send_func не установлены в JobManager")
                return
            
            logger.info(f"📤 Отправляем напоминание о воде для {self.chat_id}")
            sync_send_func = async_to_sync(job_manager.water_send_func)
            result = sync_send_func(
                application=job_manager.application,
                chat_id=self.chat_id,
                settings=self.settings
            )
            logger.info(f"✅ WaterReminderJob завершен для {self.chat_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка в WaterReminderJob для {self.chat_id}: {e}", exc_info=True)
            raise


class JobManager:
    """
    Централизованный менеджер для управления всеми задачами планировщика.
    
    АРХИТЕКТУРА:
    - Использует MemoryJobStore (задачи хранятся только в памяти)
    - Задачи восстанавливаются из reminders.db при каждом запуске бота
    - Это решает все проблемы с pickle сериализацией классов
    - Использует сериализуемые классы WaterReminderJob и CustomReminderJob
    """
    
    def __init__(self):
        # ИСПРАВЛЕНИЕ: Используем MemoryJobStore вместо SQLAlchemy
        # Задачи восстанавливаются из reminders.db при каждом запуске
        # Это решает все проблемы с сериализацией pickle
        jobstores = {
            'default': MemoryJobStore()
        }
        
        # Настройка executor'ов
        executors = {
            'default': ThreadPoolExecutor(max_workers=10)
        }
        
        # Настройки для обработки пропущенных задач
        job_defaults = {
            'coalesce': True,  # Объединить пропущенные запуски в один
            'max_instances': 1,  # Не запускать несколько экземпляров одновременно
            'misfire_grace_time': MISFIRE_GRACE_TIME  # Запустить в течение часа после пропуска
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=DEFAULT_TIMEZONE
        )
        
        # ИСПРАВЛЕНИЕ: Храним application и callback функции здесь
        self.application = None
        self.water_send_func = None
        
        # Добавляем обработчики событий для подробного логирования
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        
        logger.info("✅ JobManager инициализирован с MemoryJobStore (задачи восстанавливаются из reminders.db)")
    
    def _job_error_listener(self, event):
        """Обработчик ошибок выполнения задач."""
        logger.error(
            f"❌❌❌ ОШИБКА В ЗАДАЧЕ ❌❌❌\n"
            f"Job ID: {event.job_id}\n"
            f"Exception: {event.exception}\n"
            f"Traceback:",
            exc_info=(type(event.exception), event.exception, event.exception.__traceback__)
        )
    
    def _job_executed_listener(self, event):
        """Обработчик успешного выполнения задач."""
        logger.info(f"✅ Задача {event.job_id} выполнена успешно")
    
    def set_application(self, application: Any):
        """Устанавливает ссылку на Telegram Application."""
        self.application = application
        logger.info("✅ Application установлен в JobManager")
    
    def set_send_functions(self, water_send_func: callable):
        """Устанавливает функцию отправки для использования в задачах."""
        self.water_send_func = water_send_func
        logger.info("✅ Функция отправки установлена в JobManager")
    
    def start(self):
        """Запускает планировщик."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Планировщик задач запущен")
    
    def shutdown(self, wait: bool = True):
        """Останавливает планировщик."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("🛑 Планировщик задач остановлен")
    
    def schedule_water_reminders(
        self,
        application: Any,
        chat_id: int,
        settings: Dict[str, Any],
        send_func: callable
    ):
        """
        Упрощенная версия: Планирует напоминания о воде с фиксированным расписанием.
        Создает 16 задач (по одной на каждый час с 08:00 до 23:00).
        
        ИСПРАВЛЕНО: Улучшена изоляция пользователей и логирование.
        
        Args:
            application: Экземпляр Telegram Application
            chat_id: ID чата пользователя
            settings: Настройки напоминаний (timezone, is_active)
            send_func: Async функция для отправки напоминания
        """
        base_job_id = f"water_{chat_id}"
        
        try:
            logger.info(f"📅 Начало планирования напоминаний для {chat_id}")
            
            # Сохраняем application и функцию, если еще не сохранены
            if self.application is None:
                self.set_application(application)
            if self.water_send_func is None:
                self.water_send_func = send_func
            
            # КРИТИЧЕСКИ ВАЖНО: Удаляем ВСЕ старые задачи для этого пользователя
            jobs_before = len([j for j in self.scheduler.get_jobs() if j.id.startswith(base_job_id)])
            if jobs_before > 0:
                logger.info(f"🗑️ Найдено {jobs_before} старых задач для {chat_id}, удаляю...")
            self._remove_jobs_by_prefix(base_job_id)
            
            user_tz_str = settings.get('timezone', DEFAULT_TIMEZONE)
            user_tz = pytz.timezone(user_tz_str)
            
            # Фиксированные значения: 08:00-23:00, каждый час
            start_hour = DEFAULT_START_HOUR  # 8
            end_hour = DEFAULT_END_HOUR  # 23
            
            # Создаем задачи для каждого часа с 08:00 до 23:00 (всего 16 задач)
            # Формат job_id: water_{chat_id}_8, water_{chat_id}_9, ..., water_{chat_id}_23
            jobs_created = 0
            for hour in range(start_hour, end_hour + 1):
                job_id = f"{base_job_id}_{hour}"
                
                # ИСПРАВЛЕНИЕ: Создаем ГЛУБОКУЮ копию settings для каждой задачи
                # чтобы избежать разделения состояния между пользователями
                job_settings = {
                    'timezone': user_tz_str,
                    'is_active': settings.get('is_active', True),
                    'chat_id': chat_id  # Добавляем chat_id для явности
                }
                job_callable = WaterReminderJob(chat_id, job_settings)
                
                job = self.scheduler.add_job(
                    job_callable,
                    CronTrigger(
                        hour=hour,
                        minute=0,
                        timezone=user_tz
                    ),
                    id=job_id,
                    name=f"Water reminder for {chat_id} at {hour:02d}:00",
                    replace_existing=True
                )
                jobs_created += 1
                logger.info(f"📝 Добавлена задача {job_id}, next_run: {job.next_run_time}")
            
            logger.info(f"✅ Настроено {jobs_created} напоминаний для {chat_id} (каждый час с {start_hour:02d}:00 до {end_hour:02d}:00)")
            
            # ПРОВЕРКА: Считаем общее количество задач в планировщике
            total_jobs = len(self.scheduler.get_jobs())
            logger.info(f"📊 Всего задач в планировщике: {total_jobs}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при планировании напоминаний о воде для {chat_id}: {e}", exc_info=True)
            raise
    
    def remove_job(self, job_id: str) -> bool:
        """Удаляет задачу по ID."""
        try:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"🗑️ Задача {job_id} удалена")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении задачи {job_id}: {e}")
            return False
    
    def _remove_jobs_by_prefix(self, prefix: str):
        """Удаляет все задачи с заданным префиксом."""
        jobs = self.scheduler.get_jobs()
        removed_count = 0
        
        for job in jobs:
            if job.id.startswith(prefix):
                self.scheduler.remove_job(job.id)
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"🗑️ Удалено {removed_count} задач с префиксом '{prefix}'")
    
    def get_all_jobs(self) -> List[Any]:
        """Возвращает список всех запланированных задач."""
        return self.scheduler.get_jobs()
    
    def print_jobs(self):
        """Выводит информацию о всех задачах (для отладки)."""
        jobs = self.get_all_jobs()
        logger.info(f"📋 Всего запланированных задач: {len(jobs)}")
        for job in jobs:
            logger.info(f"  - {job.id}: {job.name}, next run: {job.next_run_time}")

# Глобальный экземпляр job manager
job_manager = JobManager()

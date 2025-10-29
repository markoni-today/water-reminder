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


class CustomReminderJob:
    """
    Сериализуемая задача для кастомных напоминаний.
    """
    def __init__(self, reminder_data: Dict[str, Any], is_once: bool):
        self.reminder_data = reminder_data
        self.is_once = is_once
    
    def __call__(self):
        """Вызывается планировщиком при выполнении задачи."""
        try:
            reminder_id = self.reminder_data.get('id', 'unknown')
            chat_id = self.reminder_data.get('chat_id', 'unknown')
            logger.info(f"🔔 CustomReminderJob вызван для reminder_id={reminder_id}, chat_id={chat_id}, is_once={self.is_once}")
            
            from . import job_manager
            
            if job_manager.application is None:
                logger.error("❌ Application не установлен в JobManager")
                return
            
            # Выбираем правильную функцию
            func_to_use = (job_manager.custom_once_send_func if self.is_once 
                          else job_manager.custom_send_func)
            
            if func_to_use is None:
                logger.error(f"❌ Send функция для {'once' if self.is_once else 'recurring'} не установлена")
                return
            
            logger.info(f"📤 Отправляем кастомное напоминание ID={reminder_id} для {chat_id}")
            sync_send_func = async_to_sync(func_to_use)
            result = sync_send_func(
                application=job_manager.application,
                chat_id=self.reminder_data['chat_id'],
                reminder_data={
                    'id': self.reminder_data['id'],
                    'message': self.reminder_data['message']
                }
            )
            logger.info(f"✅ CustomReminderJob завершен для reminder_id={reminder_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка в CustomReminderJob: {e}", exc_info=True)
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
        self.custom_send_func = None
        self.custom_once_send_func = None
        
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
    
    def set_send_functions(self, water_send_func: callable, custom_send_func: callable, custom_once_send_func: callable):
        """Устанавливает функции отправки для использования в задачах."""
        self.water_send_func = water_send_func
        self.custom_send_func = custom_send_func
        self.custom_once_send_func = custom_once_send_func
        logger.info("✅ Функции отправки установлены в JobManager")
    
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
        ИСПРАВЛЕННАЯ версия: Планирует напоминания о воде с использованием сериализуемых callable объектов.
        Каждое напоминание планируется отдельно для точного контроля времени.
        
        ИСПРАВЛЕНИЕ: Использует WaterReminderJob класс вместо вложенных замыканий.
        
        Args:
            application: Экземпляр Telegram Application
            chat_id: ID чата пользователя
            settings: Настройки напоминаний (start_hour, end_hour, interval_minutes, timezone)
            send_func: Async функция для отправки напоминания
        """
        base_job_id = f"water_{chat_id}"
        
        try:
            # ИСПРАВЛЕНИЕ: Сохраняем application и функцию, если еще не сохранены
            if self.application is None:
                self.set_application(application)
            if self.water_send_func is None:
                self.water_send_func = send_func
            
            # Удаляем все старые задачи для этого пользователя
            self._remove_jobs_by_prefix(base_job_id)
            
            user_tz_str = settings.get('timezone', DEFAULT_TIMEZONE)
            user_tz = pytz.timezone(user_tz_str)
            
            # ИСПРАВЛЕНИЕ: Используем значения по умолчанию (8-23) если не установлены
            start_hour = settings.get('start_hour', DEFAULT_START_HOUR)
            end_hour = settings.get('end_hour', DEFAULT_END_HOUR)
            interval_minutes = settings.get('interval_minutes', 60)
            
            # Вычисляем все времена отправки в течение дня
            reminder_times = self._calculate_reminder_times(
                start_hour, end_hour, interval_minutes, user_tz
            )
            
            # ИСПРАВЛЕНИЕ: Фильтруем прошедшие времена - оставляем только будущие
            now = datetime.now(user_tz)
            current_hour = now.hour
            current_minute = now.minute
            
            # Если сейчас в рабочее время, фильтруем только будущие времена
            if start_hour <= current_hour < end_hour:
                filtered_times = [
                    t for t in reminder_times 
                    if t.hour > current_hour or (t.hour == current_hour and t.minute > current_minute)
                ]
                reminder_times = filtered_times
                logger.info(f"🔍 Фильтрация: оставлено {len(reminder_times)} будущих напоминаний (исключено прошедших)")
            elif current_hour >= end_hour:
                # Уже позже рабочего времени - планируем только на завтра
                reminder_times = [
                    t for t in reminder_times 
                    if t.date() > now.date()  # Только завтрашние
                ]
                logger.info(f"🌙 Уже позже рабочего времени, планируем на завтра: {len(reminder_times)} напоминаний")
            
            logger.info(f"📅 Планируем {len(reminder_times)} напоминаний о воде для {chat_id} (рабочее время: {start_hour}:00-{end_hour}:00, интервал: {interval_minutes} мин)")
            
            # Создаем отдельную задачу для каждого времени
            for idx, reminder_time in enumerate(reminder_times):
                job_id = f"{base_job_id}_{idx}"
                
                # ИСПРАВЛЕНИЕ: Используем сериализуемый класс вместо замыкания
                job_callable = WaterReminderJob(chat_id, settings.copy())
                
                job = self.scheduler.add_job(
                    job_callable,  # Сериализуемый объект!
                    CronTrigger(
                        hour=reminder_time.hour,
                        minute=reminder_time.minute,
                        timezone=user_tz
                    ),
                    id=job_id,
                    name=f"Water reminder for {chat_id} at {reminder_time.strftime('%H:%M')}",
                    replace_existing=True
                )
                logger.info(f"📝 Добавлена задача {job_id}, next run: {job.next_run_time}")
            
            logger.info(f"✅ Настроено {len(reminder_times)} напоминаний для {chat_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при планировании напоминаний о воде: {e}", exc_info=True)
            raise
    
    def schedule_custom_reminder(
        self,
        application: Any,
        reminder: Dict[str, Any],
        send_func: callable
    ) -> Optional[str]:
        """
        ИСПРАВЛЕННАЯ версия: Планирует кастомное напоминание с использованием сериализуемых callable объектов.
        
        ИСПРАВЛЕНИЕ: Использует CustomReminderJob класс вместо вложенных замыканий.
        
        Args:
            application: Экземпляр Telegram Application
            reminder: Данные напоминания (id, chat_id, message, reminder_time, frequency, timezone)
            send_func: Async функция для отправки напоминания
            
        Returns:
            'scheduled' если успешно запланировано
            'missed_once' если одноразовое напоминание пропущено
            None если произошла ошибка
        """
        job_id = f"custom_{reminder['id']}"
        
        try:
            # ИСПРАВЛЕНИЕ: Сохраняем application и функции, если еще не сохранены
            if self.application is None:
                self.set_application(application)
            
            # Сохраняем соответствующую функцию отправки
            if reminder['frequency'] == 'once':
                if self.custom_once_send_func is None:
                    self.custom_once_send_func = send_func
            else:
                if self.custom_send_func is None:
                    self.custom_send_func = send_func
            
            # Удаляем старую задачу, если существует
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # Парсим время напоминания
            reminder_time = datetime.fromisoformat(reminder['reminder_time'])
            user_tz = pytz.timezone(reminder.get('timezone', DEFAULT_TIMEZONE))
            
            # Делаем время aware
            if reminder_time.tzinfo is None:
                aware_reminder_time = user_tz.localize(reminder_time)
            else:
                aware_reminder_time = reminder_time.astimezone(user_tz)
            
            now = datetime.now(user_tz)
            frequency = reminder['frequency']
            
            # Обработка пропущенного времени
            if aware_reminder_time < now:
                logger.warning(f"⚠️ Напоминание {job_id} запланировано на прошлое время ({aware_reminder_time})")
                
                if frequency == 'once':
                    # Для одноразовых - возвращаем статус для отправки уведомления
                    logger.warning(f"❌ Пропущенное одноразовое напоминание {job_id}")
                    return 'missed_once'
                
                elif frequency == 'daily':
                    # Для ежедневных - планируем на завтра в то же время
                    tomorrow = now + timedelta(days=1)
                    aware_reminder_time = tomorrow.replace(
                        hour=aware_reminder_time.hour,
                        minute=aware_reminder_time.minute,
                        second=0,
                        microsecond=0
                    )
                    logger.info(f"🔄 Перепланируем ежедневное напоминание на {aware_reminder_time}")
                
                elif frequency == 'weekly':
                    # Для еженедельных - планируем на следующую неделю
                    days_ahead = 7
                    aware_reminder_time = aware_reminder_time + timedelta(days=days_ahead)
                    logger.info(f"🔄 Перепланируем еженедельное напоминание на {aware_reminder_time}")
            
            # ИСПРАВЛЕНИЕ: Используем сериализуемый класс
            job_callable = CustomReminderJob(reminder.copy(), frequency == 'once')
            
            if frequency == 'once':
                # Одноразовое напоминание
                self.scheduler.add_job(
                    job_callable,
                    'date',
                    run_date=aware_reminder_time,
                    id=job_id,
                    name=f"Custom once for {reminder['chat_id']}",
                    replace_existing=True
                )
            else:
                # Повторяющееся напоминание
                trigger_args = {
                    'hour': aware_reminder_time.hour,
                    'minute': aware_reminder_time.minute,
                    'timezone': user_tz
                }
                
                if frequency == 'weekly':
                    trigger_args['day_of_week'] = aware_reminder_time.weekday()
                
                self.scheduler.add_job(
                    job_callable,
                    CronTrigger(**trigger_args),
                    id=job_id,
                    name=f"Custom {frequency} for {reminder['chat_id']}",
                    replace_existing=True
                )
            
            logger.info(f"✅ Напоминание {job_id} ({frequency}) запланировано на {aware_reminder_time}")
            return 'scheduled'
            
        except Exception as e:
            logger.error(f"❌ Ошибка при планировании кастомного напоминания: {e}", exc_info=True)
            return None
    
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
    
    def _calculate_reminder_times(
        self,
        start_hour: int,
        end_hour: int,
        interval_minutes: int,
        timezone: pytz.timezone
    ) -> List[datetime]:
        """
        Вычисляет все времена напоминаний с правильным выравниванием по интервалу.
        Например, для интервала 30 минут: X:00, X:30, (X+1):00, (X+1):30...
        Для интервала 90 минут: X:00, X:30 (через 1.5 часа), (X+1):00, (X+1):30...
        
        Args:
            start_hour: Час начала (0-23)
            end_hour: Час окончания (0-23)
            interval_minutes: Интервал между напоминаниями в минутах
            timezone: Часовой пояс
            
        Returns:
            Список datetime объектов для каждого напоминания (выровненных по интервалу)
        """
        reminder_times = []
        now = datetime.now(timezone)
        
        # Начинаем с start_hour:00
        current_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # Вычисляем времена напоминаний с интервалом
        # Интервал может быть больше 60 минут, поэтому нужно правильно обрабатывать переход часов
        while current_time <= end_time:
            # Проверяем что время не выходит за границу end_hour
            if current_time.hour > end_hour:
                break
            if current_time.hour == end_hour and current_time.minute > 0:
                break
                
            reminder_times.append(current_time)
            
            # Добавляем интервал
            current_time += timedelta(minutes=interval_minutes)
            
            # Если перешли на следующий день, останавливаемся
            if current_time.date() > now.date():
                break
        
        logger.debug(f"Вычислено {len(reminder_times)} времен напоминаний для интервала {interval_minutes} мин (с {start_hour}:00 до {end_hour}:00)")
        if reminder_times:
            logger.debug(f"Первое время: {reminder_times[0].strftime('%H:%M')}, последнее: {reminder_times[-1].strftime('%H:%M')}")
        
        return reminder_times
    
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

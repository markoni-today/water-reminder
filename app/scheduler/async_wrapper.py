"""
Синхронно-асинхронные обертки для APScheduler.
Решает проблему memory leaks и правильно управляет event loops.
"""
import asyncio
import logging
from typing import Callable, Any, Coroutine
from functools import wraps

logger = logging.getLogger(__name__)

class AsyncJobRunner:
    """
    Менеджер для запуска асинхронных функций из синхронного контекста APScheduler.
    Использует asyncio.run() для правильного управления event loops.
    """
    
    def run_async(self, coro: Coroutine) -> Any:
        """
        Запускает корутину в отдельном event loop.
        
        Args:
            coro: Асинхронная функция для выполнения
            
        Returns:
            Результат выполнения корутины
        """
        try:
            logger.debug(f"🔄 AsyncJobRunner: Запуск корутины {coro.__name__ if hasattr(coro, '__name__') else type(coro)}")
            # Для Python 3.7+ используем asyncio.run() - правильно создает и закрывает loop
            result = asyncio.run(coro)
            logger.debug(f"✅ AsyncJobRunner: Корутина завершена успешно")
            return result
        except Exception as e:
            logger.error(f"❌ AsyncJobRunner: Ошибка при выполнении async задачи: {e}", exc_info=True)
            raise

# Глобальный экземпляр runner
_runner = AsyncJobRunner()

def async_to_sync(async_func: Callable[..., Coroutine]) -> Callable:
    """
    Декоратор для преобразования async функции в sync для использования в APScheduler.
    
    Args:
        async_func: Асинхронная функция для обертки
        
    Returns:
        Синхронная функция-обертка
    
    Example:
        @async_to_sync
        async def my_async_job(param1, param2):
            await do_something()
        
        # Теперь можно использовать в APScheduler
        scheduler.add_job(my_async_job, 'interval', minutes=5)
    """
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            logger.debug(f"🔄 async_to_sync wrapper: вызвана функция {async_func.__name__}")
            coro = async_func(*args, **kwargs)
            result = _runner.run_async(coro)
            logger.debug(f"✅ async_to_sync wrapper: функция {async_func.__name__} завершена")
            return result
        except Exception as e:
            logger.error(f"❌ async_to_sync wrapper: ошибка в {async_func.__name__}: {e}", exc_info=True)
            raise
    
    return wrapper


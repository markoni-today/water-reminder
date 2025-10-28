# =============================================================================
# Water Reminder Bot - Docker Image
# =============================================================================
# 
# Использование:
#   docker build -t water-reminder-bot .
#   docker run -d --name water_bot --env-file .env water-reminder-bot
# 
# =============================================================================

FROM python:3.13-slim

# Метаданные образа
LABEL maintainer="your.email@example.com"
LABEL description="Water Reminder Telegram Bot"
LABEL version="2.0"

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY app/ ./app/
COPY water_reminder_bot.py .

# Создание директории для данных
RUN mkdir -p /app/data

# Установка переменных окружения по умолчанию
ENV PYTHONUNBUFFERED=1 \
    DB_NAME=/app/data/reminders.db \
    SCHEDULER_DB_NAME=/app/data/scheduler_jobs.db \
    LOG_FILE=/app/data/bot_log.txt

# Volume для персистентного хранения данных
VOLUME ["/app/data"]

# Healthcheck для проверки работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sqlite3; conn = sqlite3.connect('/app/data/reminders.db'); conn.close()" || exit 1

# Запуск бота
CMD ["python", "-m", "app"]


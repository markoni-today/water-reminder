#!/bin/bash
# =============================================================================
# Water Reminder Bot - Скрипт автоматического развертывания на сервере
# =============================================================================
# 
# Использование:
#   bash deploy.sh
# 
# Этот скрипт выполняет:
#   1. Обновление системы
#   2. Установку зависимостей
#   3. Настройку виртуального окружения
#   4. Установку Python пакетов
#   5. Создание .env файла (если не существует)
#   6. Настройку systemd сервиса
#   7. Запуск бота
# 
# =============================================================================

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

# Проверка root прав
if [ "$EUID" -ne 0 ]; then 
    print_error "Пожалуйста, запустите скрипт с правами root (sudo)"
    exit 1
fi

print_header "Water Reminder Bot - Автоматическое развертывание"

# Определение директории проекта
PROJECT_DIR=$(dirname "$(readlink -f "$0")")
print_info "Директория проекта: $PROJECT_DIR"

# Шаг 1: Обновление системы
print_header "Шаг 1: Обновление системы"
print_info "Обновление списка пакетов..."
apt update -qq

print_info "Обновление установленных пакетов..."
apt upgrade -y -qq

print_success "Система обновлена"

# Шаг 2: Установка зависимостей
print_header "Шаг 2: Установка зависимостей"
print_info "Установка Python, pip, venv, Git..."
apt install -y -qq python3 python3-pip python3-venv git nano curl

# Проверка версий
PYTHON_VERSION=$(python3 --version)
PIP_VERSION=$(pip3 --version | awk '{print $2}')
GIT_VERSION=$(git --version | awk '{print $3}')

print_success "Установлено:"
echo "  - Python: $PYTHON_VERSION"
echo "  - pip: $PIP_VERSION"
echo "  - Git: $GIT_VERSION"

# Шаг 3: Создание виртуального окружения
print_header "Шаг 3: Настройка виртуального окружения"

if [ -d "$PROJECT_DIR/venv" ]; then
    print_warning "Виртуальное окружение уже существует"
    read -p "Пересоздать? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Удаление старого окружения..."
        rm -rf "$PROJECT_DIR/venv"
        print_info "Создание нового виртуального окружения..."
        python3 -m venv "$PROJECT_DIR/venv"
    fi
else
    print_info "Создание виртуального окружения..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

print_success "Виртуальное окружение готово"

# Шаг 4: Установка Python пакетов
print_header "Шаг 4: Установка Python пакетов"
print_info "Активация виртуального окружения..."
source "$PROJECT_DIR/venv/bin/activate"

print_info "Обновление pip..."
pip install --upgrade pip -qq

print_info "Установка зависимостей из requirements.txt..."
pip install -r "$PROJECT_DIR/requirements.txt" -qq

print_success "Все пакеты установлены"

# Вывод списка установленных пакетов
echo ""
echo "Установленные пакеты:"
pip list | grep -E "python-telegram-bot|APScheduler|pytz|python-dotenv|sqlalchemy"

# Шаг 5: Настройка .env файла
print_header "Шаг 5: Настройка конфигурации"

if [ -f "$PROJECT_DIR/.env" ]; then
    print_warning ".env файл уже существует"
    cat "$PROJECT_DIR/.env"
    echo ""
    read -p "Пересоздать? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Введите токен Telegram бота:"
        read -r BOT_TOKEN
        cat > "$PROJECT_DIR/.env" << EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
DEFAULT_TIMEZONE=Etc/GMT-3
DB_NAME=reminders.db
SCHEDULER_DB_NAME=scheduler_jobs.db
LOG_LEVEL=INFO
LOG_FILE=bot_log.txt
MAX_CUSTOM_REMINDERS=10
MAX_MESSAGE_LENGTH=500
MISFIRE_GRACE_TIME=3600
CLEANUP_INTERVAL_HOURS=1
DEBUG_MODE=false
EOF
        print_success ".env файл создан"
    fi
else
    print_info "Создание .env файла..."
    
    if [ -f "$PROJECT_DIR/env.example" ]; then
        print_info "Найден env.example, используем как шаблон"
        cp "$PROJECT_DIR/env.example" "$PROJECT_DIR/.env"
    fi
    
    print_info "Введите токен Telegram бота:"
    read -r BOT_TOKEN
    
    cat > "$PROJECT_DIR/.env" << EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
DEFAULT_TIMEZONE=Etc/GMT-3
DB_NAME=reminders.db
SCHEDULER_DB_NAME=scheduler_jobs.db
LOG_LEVEL=INFO
LOG_FILE=bot_log.txt
MAX_CUSTOM_REMINDERS=10
MAX_MESSAGE_LENGTH=500
MISFIRE_GRACE_TIME=3600
CLEANUP_INTERVAL_HOURS=1
DEBUG_MODE=false
EOF
    
    print_success ".env файл создан"
fi

# Шаг 6: Тестовый запуск
print_header "Шаг 6: Тестовый запуск бота"
print_info "Запуск бота для проверки..."
print_warning "Нажмите Ctrl+C через 10 секунд для остановки"
echo ""

timeout 10 python -m app || true

echo ""
print_success "Тестовый запуск завершен"

# Шаг 7: Настройка systemd сервиса
print_header "Шаг 7: Настройка systemd сервиса"

SERVICE_FILE="/etc/systemd/system/water_bot.service"

if [ -f "$SERVICE_FILE" ]; then
    print_warning "Сервис water_bot уже существует"
    read -p "Пересоздать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Пропуск создания сервиса"
    else
        print_info "Создание файла сервиса..."
        cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Water Reminder Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python -m app
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/systemd_output.log
StandardError=append:$PROJECT_DIR/systemd_error.log

[Install]
WantedBy=multi-user.target
EOF
        print_success "Файл сервиса создан"
    fi
else
    print_info "Создание файла сервиса..."
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Water Reminder Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python -m app
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/systemd_output.log
StandardError=append:$PROJECT_DIR/systemd_error.log

[Install]
WantedBy=multi-user.target
EOF
    print_success "Файл сервиса создан"
fi

# Шаг 8: Активация и запуск сервиса
print_header "Шаг 8: Запуск сервиса"

print_info "Перезагрузка конфигурации systemd..."
systemctl daemon-reload

print_info "Включение автозапуска..."
systemctl enable water_bot

print_info "Запуск сервиса..."
systemctl start water_bot

# Пауза для запуска
sleep 3

# Проверка статуса
print_info "Проверка статуса сервиса..."
if systemctl is-active --quiet water_bot; then
    print_success "Сервис успешно запущен!"
    echo ""
    systemctl status water_bot --no-pager -l
else
    print_error "Сервис не запустился. Проверьте логи:"
    echo "  journalctl -u water_bot -n 50"
    exit 1
fi

# Финальные инструкции
print_header "Развертывание завершено!"

print_success "Бот успешно установлен и запущен!"
echo ""
echo "📋 Полезные команды:"
echo ""
echo "  Статус бота:"
echo "    systemctl status water_bot"
echo ""
echo "  Просмотр логов:"
echo "    journalctl -u water_bot -f"
echo "    tail -f $PROJECT_DIR/bot_log.txt"
echo ""
echo "  Управление ботом:"
echo "    systemctl start water_bot    # Запуск"
echo "    systemctl stop water_bot     # Остановка"
echo "    systemctl restart water_bot  # Перезапуск"
echo ""
echo "  Редактирование конфигурации:"
echo "    nano $PROJECT_DIR/.env"
echo ""
echo "  Обновление бота:"
echo "    cd $PROJECT_DIR"
echo "    git pull"
echo "    systemctl restart water_bot"
echo ""
print_success "Откройте бота в Telegram и отправьте /start"
echo ""


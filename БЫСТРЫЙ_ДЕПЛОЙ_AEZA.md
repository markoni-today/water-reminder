# ⚡ Быстрый деплой на Aeza - 5 шагов

Сверхкраткая инструкция для опытных пользователей.

---

## 📋 Что нужно иметь

1. ✅ Telegram Bot Token (от @BotFather)
2. ✅ Аккаунт на [aeza.net](https://aeza.net) с балансом
3. ✅ SSH клиент (PowerShell/Terminal)

---

## 🚀 5 шагов до запуска

### Шаг 1: Аренда VPS (~2 мин)

1. Войдите на [aeza.net](https://aeza.net)
2. **Создать VPS** → **Ubuntu 22.04 LTS**
3. Минимум: **1 CPU, 512MB RAM, 10GB SSD**
4. Сохраните: **IP**, **root пароль**

---

### Шаг 2: Подключение (~1 мин)

```bash
ssh root@YOUR_SERVER_IP
# Введите пароль (символы не видны - это нормально)
```

---

### Шаг 3: Установка бота (~5 мин)

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка зависимостей
apt install python3 python3-pip python3-venv git -y

# Клонирование проекта (замените на ваш URL)
git clone https://github.com/YOUR_USERNAME/water-reminder-bot.git
cd water-reminder-bot

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка пакетов
pip install -r requirements.txt
```

---

### Шаг 4: Настройка (~2 мин)

```bash
# Создание .env файла
nano .env
```

Вставьте (замените токен на свой):

```env
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
DEFAULT_TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
```

Сохраните: `Ctrl+X` → `Y` → `Enter`

---

### Шаг 5: Автозапуск (~3 мин)

```bash
# Создание systemd сервиса
nano /etc/systemd/system/water_bot.service
```

Вставьте (замените пути на свои):

```ini
[Unit]
Description=Water Reminder Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/water-reminder-bot
ExecStart=/root/water-reminder-bot/venv/bin/python -m app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохраните: `Ctrl+X` → `Y` → `Enter`

```bash
# Запуск
systemctl daemon-reload
systemctl enable water_bot
systemctl start water_bot

# Проверка
systemctl status water_bot
```

---

## ✅ Готово!

Бот работает 24/7. Проверьте в Telegram: `/start`

---

## 📊 Полезные команды

```bash
# Статус
systemctl status water_bot

# Логи
journalctl -u water_bot -f
tail -f bot_log.txt

# Управление
systemctl restart water_bot  # Перезапуск
systemctl stop water_bot     # Остановка

# Обновление
cd /root/water-reminder-bot
git pull
systemctl restart water_bot
```

---

## 🔧 Проблемы?

### Бот не запускается

```bash
# Проверьте логи
journalctl -u water_bot -n 50

# Проверьте токен
cat .env

# Ручной запуск для диагностики
cd /root/water-reminder-bot
source venv/bin/activate
python -m app
```

---

## 📚 Подробная документация

Если нужны детали:
- `AEZA_DEPLOYMENT.md` - полная инструкция
- `CHECKLIST_DEPLOYMENT.md` - чеклист
- `README.md` - описание проекта

---

**Время развертывания**: ~15 минут  
**Статус**: ✅ Production Ready


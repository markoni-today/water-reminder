# Быстрый деплой на ВМ

## Вариант 1: Через Git (рекомендуется)

```powershell
# 1. Закоммитить и запушить изменения
git add .
git commit -m "Обновление: упрощение функционала"
git push

# 2. На ВМ выполнить:
ssh -i путь/к/ключу root@your-server-ip "cd /root/water-reminder && git pull && systemctl restart water_bot"
```

## Вариант 2: Прямое копирование через scp

```powershell
# Замените YOUR_SERVER_IP и путь к ключу
$SERVER = "root@YOUR_SERVER_IP"
$KEY = "C:\path\to\your\ssh_key"
$REMOTE_PATH = "/root/water-reminder"

# Копируем только код (без venv, БД и т.д.)
scp -i $KEY -r app "$SERVER`:$REMOTE_PATH/"
scp -i $KEY *.py "$SERVER`:$REMOTE_PATH/"
scp -i $KEY requirements.txt "$SERVER`:$REMOTE_PATH/"

# На сервере перезапускаем
ssh -i $KEY $SERVER "cd $REMOTE_PATH && systemctl restart water_bot"
```

## Вариант 3: Использовать готовый скрипт

```powershell
# Простой вариант через Git
.\deploy-simple.ps1 -Host "root@YOUR_SERVER_IP" -KeyPath "C:\path\to\key"

# Или полный вариант с архивом
.\deploy.ps1 -Host "root@YOUR_SERVER_IP" -KeyPath "C:\path\to\key"
```

## Важно после деплоя:

1. Убедитесь что миграции БД выполнены (они запускаются автоматически при старте)
2. Проверьте логи: `ssh -i ключ root@server "journalctl -u water_bot -n 50"`
3. Проверьте что бот запущен: `ssh -i ключ root@server "systemctl status water_bot"`


# Автоматический скрипт развертывания на сервер
# Требуется: настроенные SSH ключи (см. SETUP_SSH_KEYS.md)
# Использование: .\deploy_auto.ps1

$serverIP = "213.108.21.142"
$serverUser = "root"
$projectPath = "/root/water-reminder"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 Автоматическое развертывание на сервере" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка локальных изменений
Write-Host "[1/5] Проверка локальных изменений..." -ForegroundColor Yellow
$gitStatus = git status --short
if ($gitStatus) {
    Write-Host "  Обнаружены незакоммиченные изменения:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $response = Read-Host "  Продолжить? (y/n)"
    if ($response -ne "y") {
        Write-Host "  Отменено" -ForegroundColor Red
        exit 0
    }
} else {
    Write-Host "  ✅ Нет незакоммиченных изменений" -ForegroundColor Green
}

# Коммит изменений (если есть)
Write-Host "[2/5] Коммит изменений..." -ForegroundColor Yellow
$changes = git diff --name-only
if ($changes) {
    Write-Host "  Обнаружены изменения:" -ForegroundColor Yellow
    Write-Host $changes -ForegroundColor Gray
    $commitMsg = Read-Host "  Введите сообщение коммита (или Enter для пропуска)"
    if ($commitMsg) {
        git add .
        git commit -m $commitMsg
        Write-Host "  ✅ Изменения закоммичены" -ForegroundColor Green
    }
}

# Загрузка на GitHub
Write-Host "[3/5] Загрузка на GitHub..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Ошибка при загрузке на GitHub" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Код загружен на GitHub" -ForegroundColor Green

# Обновление на сервере
Write-Host "[4/5] Обновление кода на сервере..." -ForegroundColor Yellow
$result = ssh -o ConnectTimeout=10 $serverUser@$serverIP "cd $projectPath && git pull"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Ошибка подключения к серверу" -ForegroundColor Red
    Write-Host "  Проверьте SSH ключи (см. SETUP_SSH_KEYS.md)" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✅ Код обновлен на сервере" -ForegroundColor Green

# Перезапуск бота
Write-Host "[5/5] Перезапуск бота..." -ForegroundColor Yellow
ssh $serverUser@$serverIP "systemctl restart water_bot"
Write-Host "  ✅ Бот перезапущен" -ForegroundColor Green

# Проверка статуса
Write-Host ""
Write-Host "Проверка статуса бота:" -ForegroundColor Cyan
ssh $serverUser@$serverIP "systemctl status water_bot --no-pager -l | Select-Object -First 15"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Развертывание завершено успешно!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Полезные команды:" -ForegroundColor Cyan
Write-Host "  Просмотр логов: ssh $serverUser@$serverIP 'journalctl -u water_bot -f'" -ForegroundColor White
Write-Host "  Статус бота:   ssh $serverUser@$serverIP 'systemctl status water_bot'" -ForegroundColor White
Write-Host "  Перезапуск:    ssh $serverUser@$serverIP 'systemctl restart water_bot'" -ForegroundColor White


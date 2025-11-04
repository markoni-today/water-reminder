# Скрипт автоматического развертывания исправлений на сервере
# Использование: .\deploy_fix.ps1

$serverIP = "213.108.21.142"
$serverUser = "root"
$serverPassword = "R8OYdZj4BxDK"
$projectPath = "/root/water-reminder"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Развертывание исправлений на сервере" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка SSH подключения
Write-Host "[1/4] Проверка SSH..." -ForegroundColor Yellow
try {
    $sshCheck = ssh -o ConnectTimeout=5 -o BatchMode=yes $serverUser@$serverIP "echo 'Connected'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Требуется ввод пароля вручную" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Выполните следующие команды на сервере:" -ForegroundColor Green
        Write-Host "  cd $projectPath" -ForegroundColor White
        Write-Host "  git pull" -ForegroundColor White
        Write-Host "  systemctl restart water_bot" -ForegroundColor White
        Write-Host "  systemctl status water_bot" -ForegroundColor White
        Write-Host ""
        Write-Host "Или подключитесь вручную:" -ForegroundColor Green
        Write-Host "  ssh $serverUser@$serverIP" -ForegroundColor White
        Write-Host ""
        exit 0
    }
} catch {
    Write-Host "  Ошибка подключения" -ForegroundColor Red
}

Write-Host "[2/4] Обновление кода на сервере..." -ForegroundColor Yellow
ssh $serverUser@$serverIP "cd $projectPath && git pull"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Ошибка при обновлении кода" -ForegroundColor Red
    Write-Host "  Выполните вручную на сервере:" -ForegroundColor Yellow
    Write-Host "    cd $projectPath" -ForegroundColor White
    Write-Host "    git pull" -ForegroundColor White
    exit 1
}

Write-Host "[3/4] Перезапуск бота..." -ForegroundColor Yellow
ssh $serverUser@$serverIP "systemctl restart water_bot"

Write-Host "[4/4] Проверка статуса..." -ForegroundColor Yellow
ssh $serverUser@$serverIP "systemctl status water_bot --no-pager -l | head -20"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Развертывание завершено!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Для просмотра логов выполните:" -ForegroundColor Cyan
Write-Host "  ssh $serverUser@$serverIP 'journalctl -u water_bot -n 50'" -ForegroundColor White


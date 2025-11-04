# Простой скрипт деплоя через Git
# Использование: .\deploy-simple.ps1 -Host "user@hostname" -KeyPath "C:\path\to\key"

param(
    [Parameter(Mandatory=$true)]
    [string]$Host,
    
    [Parameter(Mandatory=$false)]
    [string]$KeyPath = ""
)

Write-Host "🚀 Быстрый деплой через Git..." -ForegroundColor Green

# Проверяем что есть изменения для коммита
$changes = git status --porcelain
if ($changes) {
    Write-Host "📝 Найдены изменения, создаем коммит..." -ForegroundColor Yellow
    git add .
    git commit -m "Обновление: упрощение функционала, онбординг, фиксированное расписание"
    
    Write-Host "📤 Пушим изменения..." -ForegroundColor Yellow
    git push
} else {
    Write-Host "ℹ️ Нет изменений для коммита" -ForegroundColor Cyan
}

# Определяем SSH опции
$sshOptions = ""
if ($KeyPath -ne "") {
    $sshOptions = "-i `"$KeyPath`""
}

Write-Host "🔄 Обновляем код на сервере..." -ForegroundColor Yellow
ssh $sshOptions $Host "cd /root/water-reminder && git pull && systemctl restart water_bot"

Write-Host "✅ Деплой завершен!" -ForegroundColor Green


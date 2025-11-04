# Скрипт быстрого деплоя на ВМ
# Использование: .\deploy.ps1 -Host "user@hostname" -KeyPath "C:\path\to\key" -RemotePath "/root/water-reminder"

param(
    [Parameter(Mandatory=$true)]
    [string]$Host,
    
    [Parameter(Mandatory=$false)]
    [string]$KeyPath = "",
    
    [Parameter(Mandatory=$false)]
    [string]$RemotePath = "/root/water-reminder"
)

Write-Host "🚀 Начинаем деплой на $Host..." -ForegroundColor Green

# Определяем SSH опции
$sshOptions = ""
if ($KeyPath -ne "") {
    $sshOptions = "-i `"$KeyPath`""
}

# Создаем временный архив с нужными файлами (исключая venv, __pycache__, .git и т.д.)
Write-Host "📦 Создаем архив..." -ForegroundColor Yellow
$tempArchive = "deploy_temp.tar.gz"

# Используем tar для создания архива (если доступен) или копируем через scp
if (Get-Command tar -ErrorAction SilentlyContinue) {
    tar -czf $tempArchive --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='*.log' --exclude='.env' --exclude='reminders.db' --exclude='scheduler_jobs.db' --exclude='deploy_temp.tar.gz' .
    
    Write-Host "📤 Копируем архив на сервер..." -ForegroundColor Yellow
    scp $sshOptions $tempArchive "${Host}:${RemotePath}/deploy_temp.tar.gz"
    
    Write-Host "📥 Распаковываем на сервере..." -ForegroundColor Yellow
    ssh $sshOptions $Host "cd $RemotePath && tar -xzf deploy_temp.tar.gz && rm deploy_temp.tar.gz"
    
    Remove-Item $tempArchive
} else {
    Write-Host "⚠️ tar не найден, используем прямое копирование через scp..." -ForegroundColor Yellow
    Write-Host "📤 Копируем файлы на сервер..." -ForegroundColor Yellow
    
    # Копируем только нужные директории и файлы
    scp $sshOptions -r app "${Host}:${RemotePath}/"
    scp $sshOptions -r *.py "${Host}:${RemotePath}/" 2>$null
    scp $sshOptions -r requirements.txt "${Host}:${RemotePath}/" 2>$null
    scp $sshOptions -r .env.example "${Host}:${RemotePath}/" 2>$null
}

Write-Host "✅ Деплой завершен!" -ForegroundColor Green
Write-Host "💡 Не забудьте на сервере:" -ForegroundColor Cyan
Write-Host "   1. Активировать venv: source venv/bin/activate" -ForegroundColor Cyan
Write-Host "   2. Установить зависимости: pip install -r requirements.txt" -ForegroundColor Cyan
Write-Host "   3. Перезапустить бота: systemctl restart water_bot" -ForegroundColor Cyan


# ============================================================================
# WATER REMINDER BOT - QUICK DEPLOYMENT SCRIPT
# ============================================================================
# Версия: 2.1.0-multiuser-fix
# Дата: 5 ноября 2024
# 
# Описание: Быстрый деплой исправлений многопользовательского режима
# 
# Usage: .\deploy_now.ps1 [-KeyPath "C:\path\to\key"]
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$KeyPath = ""
)

$SERVER = "root@213.108.21.142"
$REMOTE_PATH = "/root/water-reminder"

# Determine SSH options
$sshOptions = ""
$scpOptions = ""
if ($KeyPath -ne "") {
    $sshOptions = "-i `"$KeyPath`""
    $scpOptions = "-i `"$KeyPath`""
} elseif (Test-Path "$env:USERPROFILE\.ssh\id_ed25519") {
    $KeyPath = "$env:USERPROFILE\.ssh\id_ed25519"
    $sshOptions = "-i `"$KeyPath`""
    $scpOptions = "-i `"$KeyPath`""
    Write-Host "Using SSH key: $KeyPath" -ForegroundColor Green
} else {
    Write-Host "SSH key not specified and not found in standard location" -ForegroundColor Yellow
    Write-Host "Using connection without key (password may be required)" -ForegroundColor Yellow
}

Write-Host "`nStarting deploy to $SERVER..." -ForegroundColor Green

# Check for changes
$changes = git status --porcelain
if ($changes) {
    Write-Host "`nFound changes:" -ForegroundColor Yellow
    git status --short
    
    $response = Read-Host "`nCreate commit and push? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "`nCreating commit..." -ForegroundColor Yellow
        git add .
        git commit -m "Fix: многопользовательский режим - изоляция пользователей, исправление диапазона времени 23:00, улучшенное логирование"
        
        Write-Host "Pushing changes..." -ForegroundColor Yellow
        git push
        
        Write-Host "`nUpdating code on server..." -ForegroundColor Yellow
        $result = ssh $sshOptions $SERVER "cd $REMOTE_PATH && git pull 2>&1"
        Write-Host $result
        
        Write-Host "`nRunning migrations..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "cd $REMOTE_PATH && source venv/bin/activate && python run_migrations.py"
        
        Write-Host "`nRestarting bot..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "systemctl restart water_bot"
        
        Start-Sleep -Seconds 2
        
        Write-Host "`nChecking bot status..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "systemctl status water_bot --no-pager -l"
        
        Write-Host "`n" + ("=" * 80) -ForegroundColor Green
        Write-Host "  DEPLOY COMPLETED!" -ForegroundColor Green
        Write-Host ("=" * 80) -ForegroundColor Green
        Write-Host "`nUseful commands:" -ForegroundColor Cyan
        Write-Host "   View logs:   ssh $sshOptions $SERVER 'journalctl -u water_bot -n 100 -f'" -ForegroundColor Gray
        Write-Host "   Check DB:    ssh $sshOptions $SERVER 'cd $REMOTE_PATH && python test_multiuser_qa.py'" -ForegroundColor Gray
        Write-Host "   Bot status:  ssh $sshOptions $SERVER 'systemctl status water_bot'" -ForegroundColor Gray
    } else {
        Write-Host "`nCopying files directly via scp..." -ForegroundColor Yellow
        
        Write-Host "   Copying app/..." -ForegroundColor Gray
        scp $scpOptions -r app "${SERVER}:${REMOTE_PATH}/"
        
        Write-Host "   Copying *.py..." -ForegroundColor Gray
        Get-ChildItem *.py | ForEach-Object {
            scp $scpOptions $_.FullName "${SERVER}:${REMOTE_PATH}/"
        }
        
        if (Test-Path "requirements.txt") {
            Write-Host "   Copying requirements.txt..." -ForegroundColor Gray
            scp $scpOptions requirements.txt "${SERVER}:${REMOTE_PATH}/"
        }
        
        Write-Host "`nRunning migrations..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "cd $REMOTE_PATH && source venv/bin/activate && python run_migrations.py"
        
        Write-Host "`nRestarting bot..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "cd $REMOTE_PATH && systemctl restart water_bot"
        
        Start-Sleep -Seconds 2
        
        Write-Host "`nChecking bot status..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "systemctl status water_bot --no-pager -l"
        
        Write-Host "`n" + ("=" * 80) -ForegroundColor Green
        Write-Host "  DEPLOY COMPLETED!" -ForegroundColor Green
        Write-Host ("=" * 80) -ForegroundColor Green
    }
} else {
    Write-Host "`nNo local changes to deploy" -ForegroundColor Cyan
    
    $response = Read-Host "`nForce deploy anyway? Pull latest from git and restart (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "`nUpdating code on server..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "cd $REMOTE_PATH && git pull"
        
        Write-Host "`nRunning migrations..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "cd $REMOTE_PATH && source venv/bin/activate && python run_migrations.py"
        
        Write-Host "`nRestarting bot..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "systemctl restart water_bot"
        
        Start-Sleep -Seconds 2
        
        Write-Host "`nChecking bot status..." -ForegroundColor Yellow
        ssh $sshOptions $SERVER "systemctl status water_bot --no-pager -l"
        
        Write-Host "`n" + ("=" * 80) -ForegroundColor Green
        Write-Host "  DEPLOY COMPLETED!" -ForegroundColor Green
        Write-Host ("=" * 80) -ForegroundColor Green
    } else {
        Write-Host "`nNo action taken" -ForegroundColor Yellow
    }
}

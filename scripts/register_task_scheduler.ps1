# Регистрирует 3 ежедневных запуска мониторинга в Планировщике задач Windows
# в 08:00 / 13:00 / 17:00 — время машины уже совпадает с Asia/Qyzylorda
# (проверено: Get-TimeZone -> "Qyzylorda Standard Time").
#
# Запускать один раз вручную (от имени пользователя, под которым будет
# выполняться задача), из корня проекта:
#   powershell -ExecutionPolicy Bypass -File scripts\register_task_scheduler.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunScript = Join-Path $ProjectRoot "run.py"

if (-not (Test-Path $PythonExe)) {
    throw "Не найден venv: $PythonExe. Сначала создайте venv и установите зависимости (см. README.md)."
}

$TaskNamePrefix = "KostanayAppointmentsMonitor"
$Times = @("08:00", "13:00", "17:00")

foreach ($Time in $Times) {
    $TaskName = "$TaskNamePrefix-$($Time -replace ':','')"

    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$RunScript`"" -WorkingDirectory $ProjectRoot
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $Settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -DontStopOnIdleEnd `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -Description "Мониторинг кадровых назначений в Костанайской области ($Time)" `
        -Force | Out-Null

    Write-Host "Зарегистрирована задача: $TaskName ($Time ежедневно)"
}

Write-Host ""
Write-Host "Готово. Проверить: Get-ScheduledTask -TaskName '$TaskNamePrefix*'"
Write-Host "-StartWhenAvailable гарантирует, что пропущенный из-за выключенного"
Write-Host "компьютера запуск выполнится сразу при следующем включении (раздел 7.1 PRD)."

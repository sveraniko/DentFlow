$ErrorActionPreference = "SilentlyContinue"

# Kill any running patient bot / app.main processes from DentFlow
Get-Process python | Where-Object { $_.CommandLine -like "*DentFlow*" } | Stop-Process -Force

Start-Sleep -Seconds 2

# Restart bots in background
$env:APP_RUN_MODE = "polling"
$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = "python"
$pinfo.Arguments = "-m app.main"
$pinfo.WorkingDirectory = "C:\Users\UraJura\DentFlow"
$pinfo.UseShellExecute = $true
$pinfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized

$env:APP_RUN_MODE = "polling"
$process = [System.Diagnostics.Process]::Start($pinfo)
Write-Host "Bot process started: PID $($process.Id)"

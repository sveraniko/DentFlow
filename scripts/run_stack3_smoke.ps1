Set-Location C:\Users\UraJura\DentFlow
$python = "C:\Users\UraJura\DentFlow\.venv\Scripts\python.exe"
$log = "C:\Users\UraJura\DentFlow\scripts\stack3_smoke_output.txt"
"" | Out-File $log

function Run-Step {
    param([string]$label, [string[]]$args)
    "=== $label ===" | Tee-Object -Append $log
    & $python @args 2>&1 | Tee-Object -Append $log
    if ($LASTEXITCODE -ne 0) {
        "FAILED: $label" | Tee-Object -Append $log
        exit 1
    }
    "PASSED: $label" | Tee-Object -Append $log
}

Run-Step "db-bootstrap"       @("scripts/db_bootstrap.py")
Run-Step "seed-stack1"        @("scripts/seed_stack1.py")
Run-Step "seed-stack2"        @("scripts/seed_stack2.py")
Run-Step "seed-stack3"        @("scripts/seed_stack3_booking.py")
Run-Step "smoke-import"       @("scripts/smoke_import_app.py")
Run-Step "smoke-settings"     @("scripts/smoke_settings.py")
Run-Step "smoke-worker-modes" @("scripts/smoke_worker_modes.py")
Run-Step "smoke-dispatcher"   @("scripts/smoke_dispatcher.py")

$env:APP_RUN_MODE = "bootstrap"
Run-Step "run-bootstrap"      @("-m", "app.main")

"=== ALL STEPS PASSED ===" | Tee-Object -Append $log

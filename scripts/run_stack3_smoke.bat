@echo off
cd /d C:\Users\UraJura\DentFlow
set PYTHON=C:\Users\UraJura\DentFlow\.venv\Scripts\python.exe

echo === db-bootstrap ===
%PYTHON% scripts/db_bootstrap.py
if errorlevel 1 goto :fail

echo === seed-stack1 ===
%PYTHON% scripts/seed_stack1.py
if errorlevel 1 goto :fail

echo === seed-stack2 ===
%PYTHON% scripts/seed_stack2.py
if errorlevel 1 goto :fail

echo === seed-stack3-booking ===
%PYTHON% scripts/seed_stack3_booking.py
if errorlevel 1 goto :fail

echo === smoke-import ===
%PYTHON% scripts/smoke_import_app.py
if errorlevel 1 goto :fail

echo === smoke-settings ===
%PYTHON% scripts/smoke_settings.py
if errorlevel 1 goto :fail

echo === smoke-worker-modes ===
%PYTHON% scripts/smoke_worker_modes.py
if errorlevel 1 goto :fail

echo === smoke-dispatcher ===
%PYTHON% scripts/smoke_dispatcher.py
if errorlevel 1 goto :fail

echo === run-bootstrap ===
set APP_RUN_MODE=bootstrap
%PYTHON% -m app.main
if errorlevel 1 goto :fail

echo === ALL PASSED ===
exit /b 0

:fail
echo === FAILED at step above ===
exit /b 1

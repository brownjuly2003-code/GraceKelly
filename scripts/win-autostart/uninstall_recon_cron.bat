@echo off
setlocal

net session >nul 2>&1
if errorlevel 1 (
    echo Administrator privileges are required.
    echo Right-click uninstall_recon_cron.bat and choose Run as administrator.
    exit /b 1
)

schtasks /Delete /TN "GraceKelly Selectors Recon" /F
if errorlevel 1 (
    echo Failed to remove "GraceKelly Selectors Recon".
    exit /b 1
)

echo Removed "GraceKelly Selectors Recon" from Task Scheduler.
exit /b 0

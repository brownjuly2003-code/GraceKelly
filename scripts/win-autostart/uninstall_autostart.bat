@echo off
setlocal

net session >nul 2>&1
if errorlevel 1 (
    echo Administrator privileges are required.
    echo Right-click uninstall_autostart.bat and choose Run as administrator.
    exit /b 1
)

schtasks /Delete /TN "GraceKelly Autostart" /F
if errorlevel 1 (
    echo Failed to remove "GraceKelly Autostart".
    exit /b 1
)

echo Removed "GraceKelly Autostart".
exit /b 0

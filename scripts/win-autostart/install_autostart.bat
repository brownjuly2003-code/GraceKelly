@echo off
setlocal

net session >nul 2>&1
if errorlevel 1 (
    echo Administrator privileges are required.
    echo Right-click install_autostart.bat and choose Run as administrator.
    exit /b 1
)

schtasks /Create /TN "GraceKelly Autostart" /XML "%~dp0gracekelly_autostart.xml" /F
if errorlevel 1 (
    echo Failed to install "GraceKelly Autostart".
    exit /b 1
)

echo Installed "GraceKelly Autostart".
echo It will start GraceKelly on localhost:8011 at the next Windows logon.
exit /b 0

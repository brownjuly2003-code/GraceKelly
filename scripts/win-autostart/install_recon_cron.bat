@echo off
setlocal

net session >nul 2>&1
if errorlevel 1 (
    echo Administrator privileges are required.
    echo Right-click install_recon_cron.bat and choose Run as administrator.
    exit /b 1
)

set "TEMPLATE=%~dp0recon-task.xml"
set "RENDERED=%~dp0recon-task.rendered.xml"
set "USER_ACCOUNT=%USERDOMAIN%\%USERNAME%"

powershell -NoProfile -Command "(Get-Content -LiteralPath '%TEMPLATE%' -Encoding UTF8) -replace '__USER__', '%USER_ACCOUNT%' ^| Set-Content -LiteralPath '%RENDERED%' -Encoding UTF8"
if errorlevel 1 (
    echo Failed to render task XML for current user.
    exit /b 1
)

schtasks /Create /TN "GraceKelly Selectors Recon" /XML "%RENDERED%" /F
set "RC=%ERRORLEVEL%"
del "%RENDERED%" >nul 2>&1

if not "%RC%"=="0" (
    echo Failed to install "GraceKelly Selectors Recon" (rc=%RC%).
    exit /b %RC%
)

echo Installed "GraceKelly Selectors Recon" — runs every Friday at 03:00 local time.
echo Drift flag : D:\GraceKelly\.workflow\state\perplexity-selectors-drift.flag
echo Drift log  : D:\GraceKelly\logs\recon-drift.jsonl
exit /b 0

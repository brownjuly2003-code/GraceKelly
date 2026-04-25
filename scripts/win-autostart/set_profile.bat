@echo off
setlocal

if "%~2" neq "" goto usage
if "%~1"=="" goto usage

if /I "%~1"=="dry-run" (
    set "PROFILE=dry-run"
    goto setprofile
)
if /I "%~1"=="api-only" (
    set "PROFILE=api-only"
    goto setprofile
)
if /I "%~1"=="hybrid" (
    set "PROFILE=hybrid"
    goto setprofile
)

goto usage

:setprofile
set "GRACEKELLY_DIR=%LOCALAPPDATA%\GraceKelly"
if not exist "%GRACEKELLY_DIR%\" mkdir "%GRACEKELLY_DIR%"

> "%GRACEKELLY_DIR%\profile.env" echo GRACEKELLY_EXECUTION_PROFILE=%PROFILE%
if errorlevel 1 (
    echo Failed to write "%GRACEKELLY_DIR%\profile.env".
    exit /b 1
)

echo GraceKelly execution profile set to %PROFILE%.
echo Restart "GraceKelly Autostart" for the change to take effect.
exit /b 0

:usage
echo Usage: %~nx0 dry-run^|api-only^|hybrid
exit /b 1

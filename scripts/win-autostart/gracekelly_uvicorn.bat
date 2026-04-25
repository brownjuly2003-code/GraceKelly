@echo off
setlocal

cd /d D:\GraceKelly

set "GRACEKELLY_DIR=%LOCALAPPDATA%\GraceKelly"
if not exist "%GRACEKELLY_DIR%\" mkdir "%GRACEKELLY_DIR%"

set "GRACEKELLY_EXECUTION_PROFILE=dry-run"
if exist "%GRACEKELLY_DIR%\profile.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%GRACEKELLY_DIR%\profile.env") do (
        if /I "%%A"=="GRACEKELLY_EXECUTION_PROFILE" set "GRACEKELLY_EXECUTION_PROFILE=%%B"
    )
)

.\.venv\Scripts\python.exe -m uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011 >> "%GRACEKELLY_DIR%\uvicorn.log" 2>&1
set "UVICORN_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %UVICORN_EXIT_CODE%

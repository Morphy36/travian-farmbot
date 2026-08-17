@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo   Bot este nie je nainstalovany - spusti najprv install.bat
    pause
    exit /b 1
)

".venv\Scripts\python.exe" run.py --list
echo.
set "TASK="
set /p TASK="Nazov ulohy na jednorazove spustenie (Enter = koniec): "
if "%TASK%"=="" goto end

".venv\Scripts\python.exe" run.py --once "%TASK%"

:end
echo.
pause

@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   Bot este nie je nainstalovany - spusti najprv install.bat
    echo.
    pause
    exit /b 1
)
if not exist "config.yaml" (
    echo.
    echo   Chyba config.yaml - spusti install.bat alebo skopiruj config.example.yaml
    echo.
    pause
    exit /b 1
)

echo.
echo   Spustam Travian Farmbot...  (ukoncenie: Ctrl+C)
echo   Dashboard: http://127.0.0.1:8777
echo.

".venv\Scripts\python.exe" run.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if not "%EXITCODE%"=="0" echo   Bot skoncil s chybou (kod %EXITCODE%). Pozri logs\bot.log
pause
exit /b %EXITCODE%

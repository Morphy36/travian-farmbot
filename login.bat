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

echo.
echo   Otvaram prehliadac na jednorazove rucne prihlasenie.
echo   Prihlas sa do hry a nechaj okno otvorene, kym nestlacis Enter v tomto okne.
echo.

".venv\Scripts\python.exe" run.py --browser
pause

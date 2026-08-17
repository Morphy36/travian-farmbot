@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo ==========================================================
echo   Travian Farmbot - instalacia
echo ==========================================================
echo.

where python >nul 2>nul
if errorlevel 1 goto no_python

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)"
if errorlevel 1 goto old_python

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Vytvaram virtualne prostredie...
    python -m venv .venv
    if errorlevel 1 goto venv_failed
) else (
    echo [1/5] Virtualne prostredie uz existuje.
)

call ".venv\Scripts\activate.bat"

echo [2/5] Aktualizujem pip...
python -m pip install --upgrade pip --quiet

echo [3/5] Instalujem kniznice (chvilu to potrva)...
pip install -r requirements.txt
if errorlevel 1 goto pip_failed

echo [4/5] Stahujem prehliadac Chromium pre Playwright (~130 MB)...
python -m playwright install chromium
if errorlevel 1 goto pw_failed

echo [5/5] Pripravujem konfiguraciu...
if not exist "config.yaml" (
    copy /y "config.example.yaml" "config.yaml" >nul
    echo      Vytvoreny config.yaml
) else (
    echo      config.yaml uz existuje - nechavam ho tak.
)
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
)

echo.
echo ==========================================================
echo   Hotovo!
echo.
echo   1. Uprav config.yaml (server, meno, heslo, casovac)
echo   2. Spusti login.bat a prihlas sa raz rucne
echo   3. Spusti start.bat
echo ==========================================================
echo.
choice /c AN /n /m "Otvorit config.yaml teraz? [A/N] "
if errorlevel 2 goto end
notepad config.yaml
goto end

:no_python
echo.
echo   CHYBA: Python sa nenasiel.
echo   Nainstaluj Python 3.10+ z https://www.python.org/downloads/
echo   Pri instalacii ZASKRTNI "Add python.exe to PATH".
echo.
goto fail

:old_python
echo.
echo   CHYBA: Mas prilis stary Python. Potrebny je 3.9 alebo novsi.
echo.
goto fail

:venv_failed
echo.
echo   CHYBA: Nepodarilo sa vytvorit virtualne prostredie (.venv).
goto fail

:pip_failed
echo.
echo   CHYBA: Instalacia kniznic zlyhala. Skontroluj pripojenie na internet.
goto fail

:pw_failed
echo.
echo   CHYBA: Stiahnutie prehliadaca zlyhalo.
echo   Skus rucne:  .venv\Scripts\python -m playwright install chromium
goto fail

:fail
pause
exit /b 1

:end
pause
exit /b 0

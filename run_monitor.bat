@echo off
chcp 65001 > nul

REM ═══ FIX CRITIC: forțează Python să folosească UTF-8 ═══
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM ═══════════════════════════════════════════════════════════════
REM Monitor Oferte - Ruleaza scraper-ul si face push pe GitHub
REM ═══════════════════════════════════════════════════════════════

setlocal

cd /d "C:\Users\Vlad\Desktop\monitor-oferte"
if errorlevel 1 (
    echo [EROARE] Nu pot accesa folderul proiectului.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo [EROARE] Nu gasesc venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "logs" mkdir "logs"

for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd_HH-mm'"`) do set "timestamp=%%a"
set "logfile=logs\run_%timestamp%.log"

echo ===============================================================
echo  Monitor Oferte - Rulare
echo ===============================================================
echo.
echo  Log: %logfile%
echo  Data: %date% %time%
echo.
echo  Se ruleaza scraper-ul (dureaza ~20 minute)...
echo.

venv\Scripts\python.exe src\main.py > "%logfile%" 2>&1
set "exit_code=%errorlevel%"

type "%logfile%"

echo.
echo ===============================================================
echo  Rulare terminata - cod iesire: %exit_code%
echo ===============================================================
echo.
echo  Apasa orice tasta pentru a inchide fereastra...
pause > nul

exit /b %exit_code%
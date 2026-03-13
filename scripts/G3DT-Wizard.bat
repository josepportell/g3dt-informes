@echo off
title G3DT Wizard
echo ============================================
echo   G3DT Wizard - Generador d'Informes
echo ============================================
echo.

:: Check WSL is available
wsl --status >nul 2>&1
if errorlevel 1 (
    echo ERROR: WSL no esta disponible.
    echo Contacta amb suport tecnic.
    pause
    exit /b 1
)

:: Start the web server in WSL (background)
echo Arrancant servidor web...
start "" wsl bash -lc "cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m web"

:: Wait for server to start
echo Esperant que el servidor estigui llest...
timeout /t 4 /nobreak >nul

:: Open browser
echo Obrint navegador...
start http://localhost:8765/review.html

echo.
echo G3DT Wizard actiu a http://localhost:8765
echo.
echo NO tanquis aquesta finestra mentre treballis amb el wizard.
echo Per aturar: tanca aquesta finestra.
pause

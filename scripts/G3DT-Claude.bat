@echo off
title G3DT Claude
echo ============================================
echo   G3DT Claude - Terminal Avancat
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

echo Iniciant Claude Code...
echo.
wsl bash -lc "cd /home/josep/projects/claudecode-job/clients/g3dt && claude"

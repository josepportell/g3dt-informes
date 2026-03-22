@echo off
title G3DT Claude
echo ============================================
echo   G3DT Claude - Terminal Avancat
echo ============================================
echo.

:: Load config (G3DT_PATH)
call "%~dp0G3DT-config.bat"
if not defined G3DT_PATH (
    echo ERROR: No s'ha trobat G3DT-config.bat o G3DT_PATH no definit.
    echo Contacta amb suport tecnic.
    pause
    exit /b 1
)

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
wsl bash -lc "cd %G3DT_PATH% && claude"

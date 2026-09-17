@echo off
title Tornar a entrar a Claude
echo ============================================
echo   Tornar a entrar a Claude
echo ============================================
echo.
echo Fes servir aquesta finestra quan el wizard digui
echo que cal tornar a iniciar sessio a Claude.
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

:: Ja hi som? (claude auth status -> JSON amb loggedIn)
wsl bash -lc "claude auth status 2>/dev/null | grep -qi 'loggedin[^,]*true'"
if not errorlevel 1 (
    echo La sessio de Claude ja esta activa. No cal fer res mes.
    echo Torna al wizard i prem "Preparar".
    echo.
    pause
    exit /b 0
)

echo Obrint la pantalla d'entrada de Claude...
echo.
echo Segueix les instruccions que surtin aqui sota.
echo Si demana obrir una adreca al navegador, copia-la i obre-la.
echo.
wsl bash -lc "cd %G3DT_PATH% && claude auth login"

echo.
:: Comprovar el resultat de debo, no nomes el codi de sortida
wsl bash -lc "claude auth status 2>/dev/null | grep -qi 'loggedin[^,]*true'"
if errorlevel 1 (
    echo No s'ha pogut completar l'entrada.
    echo Torna-ho a provar; si no funciona, contacta amb suport tecnic.
    echo.
    pause
    exit /b 1
)

echo Fet: ja has tornat a entrar a Claude.
echo Tanca aquesta finestra, torna al wizard i prem "Preparar".
echo Els documents ja llegits es conserven.
echo.
pause

@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual de LimpiezaSoft.
    echo Ejecuta estos comandos desde esta carpeta:
    echo.
    echo   py -3.12 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import PySide6, psycopg, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Faltan dependencias. Ejecuta:
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 (
    echo.
    echo LimpiezaSoft finalizo con un error. Revisa el mensaje anterior.
    pause
    exit /b 1
)
exit /b 0

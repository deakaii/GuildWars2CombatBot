@echo off
title Antigrav Bot - Setup Environment
cd /d "%~dp0"

echo ===================================================
echo   Antigrav Screen Monitor Bot - Machine Setup
echo ===================================================
echo.

:: Check for Python
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=py -3
) else (
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PY_CMD=python
    ) else (
        echo [ERROR] Python is not installed or not in your PATH.
        echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
        pause
        exit /b 1
    )
)

echo [1/3] Detected Python:
%PY_CMD% --version

echo.
echo [2/3] Creating virtual environment (.venv)...
if not exist ".venv" (
    %PY_CMD% -m venv .venv
    echo Created .venv successfully.
) else (
    echo Found existing .venv folder.
)

echo.
echo [3/3] Installing required packages from requirements.txt...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo ===================================================
echo [SUCCESS] Setup Complete!
echo You can now launch the bot using 'run_gui.bat'
echo ===================================================
echo.
pause

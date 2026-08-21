@echo off
title Multi-Timeframe SMC/ICT Trading Bot (WITH AI)
color 0A
echo =========================================================================
echo       GOLD TRADING BOT: MULTI-TIMEFRAME SMC/ICT WITH AI MODEL           
echo =========================================================================
echo.

cd /d "%~dp0"

:: Auto-launch MetaTrader 5 if not running
tasklist /FI "IMAGENAME eq terminal64.exe" 2>NUL | find /I /N "terminal64.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [MT5] MetaTrader 5 is not running. Launching MT5 terminal...
    if exist "C:\Program Files\MetaTrader 5\terminal64.exe" (
        start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
        echo [MT5] Launched MetaTrader 5 from C:\Program Files\MetaTrader 5\terminal64.exe
        timeout /t 5 >nul
    ) else (
        echo [WARNING] MetaTrader 5 not found at C:\Program Files\MetaTrader 5\terminal64.exe.
        echo Please open MetaTrader 5 manually.
    )
) else (
    echo [MT5] MetaTrader 5 is already running.
)

:: Check Python availability
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in system PATH.
    echo Please install Python 3.11 or 3.12 from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 1. Check Python Virtual Environment
if not exist "venv\Scripts\python.exe" (
    echo [1/3] Setting up Python virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo [1/3] Activating virtual environment...
    call venv\Scripts\activate.bat
)

:: 2. Verify AI Model & MT5 MCP Engine
echo.
echo [2/3] Verifying AI Model Engine & MT5 MCP Tool Suite...
if not exist "models\trade_validator.joblib" (
    echo [AI ENGINE] Model file missing. Training AI model with historical data...
    python train_model.py
) else (
    echo [AI ENGINE] Testing existing AI Model & MT5 MCP Tool Engine...
    python test_ai_model.py
    python test_mcp_bot.py
)

:: 3. Launch Main Trading Bot
echo.
echo [3/3] Starting Multi-Timeframe SMC/ICT Trading Bot with AI Enabled...
echo =========================================================================
echo Logs are actively recorded in trading_bot.log
echo Active symbols: XAUUSDm, BTCUSDm, EURUSDm
echo AI Validation: ENABLED (14-Feature Random Forest + Quality Filter)
echo Press Ctrl+C to safely stop the bot at any time.
echo =========================================================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo =========================================================================
    echo [NOTICE] If you encounter 'Application Control policy has blocked this file':
    echo.
    echo Windows Smart App Control is blocking C-extension DLLs (.pyd files).
    echo To resolve this on Windows 11:
    echo   1. Open Start Menu -> type "Windows Security"
    echo   2. Click "App & browser control" -> "Smart App Control settings"
    echo   3. Set Smart App Control to "Off" or "Evaluation" mode.
    echo =========================================================================
    echo.
    pause
)

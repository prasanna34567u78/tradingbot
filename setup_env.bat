@echo off
echo Setting up virtual environment and installing requirements for Gold Trading Bot...

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python first.
    exit /b 1
)

:: Check if venv exists, if not create it
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

:: Activate virtual environment and install requirements
echo Activating virtual environment and installing requirements...
call venv\Scripts\activate.bat
venv\Scripts\Activate.ps1
:: Install requirements
:: Try an older version of pandas that might be more compatible
pip install pandas==1.5.3

:: Install other requirements excluding pandas
pip install -r requirements.txt --no-deps

echo.
echo Setup complete! You can now run the bot with: venv\Scripts\python.exe main.py
echo.

pause
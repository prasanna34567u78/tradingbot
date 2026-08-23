@echo off
cd /d "%~dp0"
title TradeBot AI Server
echo Starting TradeBot Server...
call .\venv\Scripts\activate.bat
python trading_app\api_server.py
pause

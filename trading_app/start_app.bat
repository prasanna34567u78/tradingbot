@echo off
title TradeBot AI - Full-Stack App Launcher

echo ============================================================
echo           Starting TradeBot AI Full-Stack App
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/2] Launching FastAPI Backend Server (http://127.0.0.1:8000)...
start "TradeBot API Server (Port 8000)" cmd /k "E:\Trading\venv\Scripts\python.exe api_server.py"

echo [2/2] Launching React Vite Frontend (http://127.0.0.1:5173)...
start "TradeBot Vite Frontend (Port 5173)" cmd /k "cd frontend && npm run dev"

echo.
echo ============================================================
echo TradeBot AI is initializing:
echo  - Backend API and WebSocket: http://127.0.0.1:8000
echo  - Frontend Dashboard UI:     http://127.0.0.1:5173
echo ============================================================
pause

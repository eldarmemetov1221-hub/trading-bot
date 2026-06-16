@echo off
echo === SMC Trader Pro ===
echo Starting API server + Telegram Bot...
echo.

cd /d "%~dp0"

if not exist .env (
    copy .env.example .env
    echo [!] Created .env - fill in your tokens before running!
    pause
    exit /b 1
)

echo [1/2] Starting API server on port 8000...
start "API Server" cmd /k "pip install -r requirements.txt -q && python api/server.py"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Telegram Bot...
start "Telegram Bot" cmd /k "python bot/main.py"

echo.
echo Done! API: http://localhost:8000
echo Mini App: http://localhost:8000
pause

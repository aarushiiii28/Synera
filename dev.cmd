@echo off
rem Starts the SYNERA API (port 8000) and the web app (port 5173) with the project's own Python (.venv),
rem so it works no matter which Python is on your PATH. Close the two windows to stop.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Run: make setup   ^(or: python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[api,ml,dev]"^)
  exit /b 1
)
rem free the ports if an old copy is still running
for %%P in (8000 5173) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do taskkill /PID %%I /F >nul 2>&1
)
start "SYNERA API" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000"
start "SYNERA web" cmd /k "cd frontend && npm run dev"
echo.
echo   API : http://localhost:8000/docs
echo   Web : http://localhost:5173
echo.

@echo off
cd /d "%~dp0"
echo ============================================
echo   Macro Data Tracker - Starting Server
echo   http://localhost:4321
echo   Close this window to stop the server
echo ============================================
echo.
C:\Users\ytqqs\.conda\envs\macro-tracker\python.exe "%~dp0server.py"
pause

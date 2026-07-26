@echo off
cd /d "%~dp0"
echo ============================================
echo   宏观数据跟踪 - 启动服务器
echo   http://localhost:4321
echo   关闭此窗口即停止服务器
echo ============================================
echo.
C:\Users\ytqqs\.conda\envs\macro-tracker\python.exe "%~dp0server.py"
pause

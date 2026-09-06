@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo 此操作会删除本程序的 .venv，然后下次启动重新安装依赖。
choice /c YN /m "继续吗"
if errorlevel 2 exit /b 0
if exist ".venv" rmdir /s /q ".venv"
if exist "startup.log" del /q "startup.log"
echo 已重置。请重新运行 start_windows.bat
pause

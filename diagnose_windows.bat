@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "OUT=%~dp0diagnose.txt"
echo Patent Figure Annotation Studio Diagnostics > "%OUT%"
echo Date: %date% %time% >> "%OUT%"
echo Folder: %CD% >> "%OUT%"
echo. >> "%OUT%"

echo ==== where py ==== >> "%OUT%"
where py >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo ==== py -0p ==== >> "%OUT%"
py -0p >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo ==== where python ==== >> "%OUT%"
where python >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo ==== python version ==== >> "%OUT%"
python --version >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo ==== Tkinter ==== >> "%OUT%"
python -c "import tkinter; print('Tk', tkinter.TkVersion)" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo ==== venv ==== >> "%OUT%"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; print(sys.executable); print(sys.version)" >> "%OUT%" 2>&1
  ".venv\Scripts\python.exe" -c "import PIL,numpy,scipy,fitz; print('all dependencies OK')" >> "%OUT%" 2>&1
) else (
  echo .venv not found >> "%OUT%"
)

echo.
echo 诊断完成：
echo %OUT%
echo.
notepad "%OUT%"

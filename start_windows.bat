@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Patent Figure Annotation Studio V2.1.1

cd /d "%~dp0"
set "LOG=%~dp0startup.log"
echo ================================================== > "%LOG%"
echo Patent Figure Annotation Studio startup >> "%LOG%"
echo Date: %date% %time% >> "%LOG%"
echo Folder: %CD% >> "%LOG%"
echo ================================================== >> "%LOG%"

echo.
echo [1/5] 正在查找可用 Python...
set "PY_CMD="

rem 优先使用 Windows Python Launcher 中稳定的版本
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1 && set "PY_CMD=py -3.12"
    if not defined PY_CMD py -3.11 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1 && set "PY_CMD=py -3.11"
    if not defined PY_CMD py -3.13 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1 && set "PY_CMD=py -3.13"
    if not defined PY_CMD py -3.10 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1 && set "PY_CMD=py -3.10"
)

rem 没有 py 时尝试 python
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1 && set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo [ERROR] 未找到 Python 3.10-3.13。 >> "%LOG%"
    echo.
    echo ============================================================
    echo 启动失败：未找到可用的 Python 3.10-3.13
    echo.
    echo 请安装 python.org 官方 64 位 Python 3.11 或 3.12，
    echo 安装时勾选 "Add python.exe to PATH" 和 "tcl/tk and IDLE"。
    echo ============================================================
    echo.
    echo 详细日志：%LOG%
    pause
    exit /b 10
)

echo Python command: %PY_CMD% >> "%LOG%"
%PY_CMD% -c "import sys; print(sys.executable); print(sys.version)" >> "%LOG%" 2>&1

echo [2/5] 检查 Tkinter...
%PY_CMD% -c "import tkinter; print(tkinter.TkVersion)" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Tkinter 不可用。 >> "%LOG%"
    echo.
    echo ============================================================
    echo 启动失败：当前 Python 没有 Tkinter。
    echo.
    echo 建议重新安装 python.org 官方 Python，
    echo 并确保安装组件 "tcl/tk and IDLE"。
    echo ============================================================
    echo.
    echo 详细日志：%LOG%
    pause
    exit /b 11
)

echo [3/5] 准备本地虚拟环境...
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Creating venv... >> "%LOG%"
    %PY_CMD% -m venv "%~dp0.venv" >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败。 >> "%LOG%"
        echo.
        echo 启动失败：无法创建 .venv
        echo 详细日志：%LOG%
        pause
        exit /b 12
    )
)

echo [4/5] 检查程序依赖...
"%VENV_PY%" -c "import PIL,numpy,scipy,fitz" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo 首次运行需要安装依赖，可能需要几分钟...
    echo Installing dependencies... >> "%LOG%"
    "%VENV_PY%" -m pip install --disable-pip-version-check --upgrade pip >> "%LOG%" 2>&1
    if errorlevel 1 goto :pipfail

    "%VENV_PY%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
    if errorlevel 1 goto :pipfail

    "%VENV_PY%" -c "import PIL,numpy,scipy,fitz; print('Dependencies OK')" >> "%LOG%" 2>&1
    if errorlevel 1 goto :pipfail
)

echo [5/5] 启动界面...
echo Launching app.py... >> "%LOG%"
"%VENV_PY%" "%~dp0app.py" >> "%LOG%" 2>&1
set "APP_RC=%ERRORLEVEL%"

if not "%APP_RC%"=="0" (
    echo [ERROR] app.py exited with %APP_RC% >> "%LOG%"
    echo.
    echo ============================================================
    echo 程序异常退出，错误代码：%APP_RC%
    echo 请把 startup.log 发给我即可定位。
    echo 日志位置：
    echo %LOG%
    echo ============================================================
    echo.
    pause
    exit /b %APP_RC%
)

exit /b 0

:pipfail
echo [ERROR] 依赖安装失败。 >> "%LOG%"
echo.
echo ============================================================
echo 依赖安装失败。
echo.
echo 常见原因：
echo 1. 网络无法访问 PyPI
 echo 2. Python 版本/位数不兼容
 echo 3. 公司网络代理或证书限制
 echo.
echo 请把 startup.log 发给我。
echo 日志位置：
echo %LOG%
echo ============================================================
echo.
pause
exit /b 20

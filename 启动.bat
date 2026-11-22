@echo off
cd /d "%~dp0"
title 高中化学实验室安全助手

set "PY="
python -c "import flask, openai" >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY (
  py -c "import flask, openai" >nul 2>nul
  if not errorlevel 1 set "PY=py"
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY goto nopython

echo 正在启动服务，几秒后浏览器会自动打开页面。
echo 关闭这个黑窗口即结束程序。
echo.
"%PY%" app.py
echo.
echo 程序已退出。
pause
exit /b 0

:nopython
echo.
echo 没有找到已安装 flask 和 openai 的 Python 3.10+。
echo 请先安装 Python，然后在本目录执行：
echo     python -m pip install -r requirements.txt
echo.
pause
exit /b 1
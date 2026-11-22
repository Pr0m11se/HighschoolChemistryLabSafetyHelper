@echo off
cd /d "%~dp0"
title 配置 DeepSeek API Key

set "PY="
python -c "import tkinter" >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY (
  py -c "import tkinter" >nul 2>nul
  if not errorlevel 1 set "PY=py"
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY (
  echo 没有找到可用的 Python，请先安装 Python 3.10+。
  pause
  exit /b 1
)

"%PY%" add_apikey.py
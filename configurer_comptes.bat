@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Lancez d abord installer.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m viky --configurer-comptes

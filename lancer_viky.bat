@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Viky n est pas encore installee : lancez d abord installer.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m viky %*
pause

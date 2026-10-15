@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Installation de Viky ===
where py >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installez Python 3.11 ou plus recent depuis https://www.python.org/downloads/
  echo Pensez a cocher "Add python.exe to PATH" pendant l installation.
  pause
  exit /b 1
)
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 (
  echo Viky a besoin de Python 3.11 ou plus recent.
  pause
  exit /b 1
)
if not exist .venv py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo L installation des dependances a echoue.
  pause
  exit /b 1
)
where nvidia-smi >nul 2>nul
if not errorlevel 1 (
  echo Carte NVIDIA detectee : installation de l acceleration graphique...
  pip install -r requirements-gpu.txt
)
python -c "import tkinter" 2>nul
if errorlevel 1 echo ATTENTION : tkinter manque, l ecran de scene ne marchera pas. Reinstallez Python en cochant "tcl/tk and IDLE".
python -m viky --telecharger-modeles
where ollama >nul 2>nul
if not errorlevel 1 (
  echo Ollama detecte : telechargement de l IA locale qwen2.5:7b ^(environ 4,7 Go^)...
  ollama pull qwen2.5:7b
)
echo.
echo Installation terminee ! Double-cliquez sur lancer_viky.bat pour demarrer Viky.
pause

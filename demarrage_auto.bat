@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Lancez d abord installer.bat
  pause
  exit /b 1
)
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\Viky.lnk'); $s.TargetPath = '%~dp0lancer_viky.bat'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Description = 'Viky'; $s.Save()"
if errorlevel 1 (
  echo Impossible de creer le raccourci de demarrage.
) else (
  echo Viky se lancera automatiquement a chaque demarrage de Windows.
  echo Pour annuler : retirer_demarrage_auto.bat
)
pause

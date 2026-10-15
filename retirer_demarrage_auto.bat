@echo off
chcp 65001 >nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Viky.lnk" 2>nul
echo Viky ne se lancera plus au demarrage de Windows.
pause

@echo off
rem Installation sous Windows : double-cliquer sur ce fichier (Python 3.9 a 3.13 requis, https://www.python.org)
cd /d %~dp0
python -m venv .venv || (echo Python est introuvable : installez-le depuis python.org en cochant "Add Python to PATH". & pause & exit /b 1)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Installation terminee. Double-cliquez sur lancer_windows.bat pour demarrer la detection.
pause

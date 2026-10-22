@echo off
rem Lance la detection sur la webcam. Exemples : lancer_windows.bat --source video.mp4   /   --source 1   /   --voix
cd /d %~dp0
call .venv\Scripts\activate
python app.py %*
pause

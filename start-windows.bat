@echo off
cd /d "%~dp0"
if not exist .venv py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
start "" http://127.0.0.1:8765
.venv\Scripts\python.exe app.py
pause
exit /b
:failed
echo Installation failed. Check Python 3.11+ and your internet connection.
pause

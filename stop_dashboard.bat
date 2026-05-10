@echo off
echo Stopping Dashboard Server...
call .venv\Scripts\activate.bat
python dashboard_server.py --stop
pause

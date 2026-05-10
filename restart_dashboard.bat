@echo off
REM Restart ComfyUI Dashboard (stop all + start new service)

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Restart dashboard server
python dashboard_server.py --restart

pause

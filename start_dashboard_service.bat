@echo off
REM Start ComfyUI Dashboard in Service Mode (Background)

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start dashboard server in service mode
python dashboard_server.py --service

pause

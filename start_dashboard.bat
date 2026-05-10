@echo off
echo ========================================
echo ComfyUI Lite Dashboard
echo ========================================
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat
echo.
echo Starting dashboard server...
echo.
echo Dashboard will be available at:
echo http://127.0.0.1:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python dashboard_server.py

pause

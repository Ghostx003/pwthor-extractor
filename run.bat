@echo off
TITLE PWTHOR Auto Video Downloader
COLOR 0A

echo ===================================================
echo           PWTHOR AUTO VIDEO DOWNLOADER
echo ===================================================
echo.

:: Ensure working directory is the script directory
cd /d "%~dp0"

:: Check Python installation
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.9+ and try again.
    pause
    exit /b 1
)

echo [INFO] Checking Python dependencies...
python -c "import playwright, rich" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing required dependencies...
    python -m pip install -r requirements.txt
    python -m playwright install chromium
)

echo [INFO] Launching Automation Pipeline...
echo.

python src\main.py

echo.
echo ===================================================
echo Execution finished or stopped.
echo ===================================================
pause

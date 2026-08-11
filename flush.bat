@echo off
TITLE Flush JSON Data
COLOR 0C

echo ========================================
echo WARNING: This will clear the contents of
echo download_mapping.json and link_saver.json.
echo ========================================
echo.
pause

cd /d "%~dp0"
python src\flush.py

echo.
pause

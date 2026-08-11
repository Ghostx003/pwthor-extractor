@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   PWTHOR VIDEO RENAMER + CONVERTER
echo ========================================
echo.

:: Determine the script's own directory so we can find rename_downloads.py and download_mapping.json
set "SCRIPT_DIR=%~dp0"

:: Check that rename_downloads.py exists
if not exist "%SCRIPT_DIR%src\rename_downloads.py" (
    echo [ERROR] src\rename_downloads.py not found in:
    echo %SCRIPT_DIR%
    echo.
    pause
    exit /b 1
)

:: Default mapping file location (same folder as this bat file)
set "MAPPING_FILE=%SCRIPT_DIR%download_mapping.json"

if not exist "!MAPPING_FILE!" (
    echo [WARNING] download_mapping.json not found at:
    echo !MAPPING_FILE!
    echo.
    echo The script will still run but no files will be matched.
    echo Make sure the downloader has run at least once first.
    echo.
)

echo ========================================
echo Starting rename + conversion process...
echo ========================================
echo.

python "%SCRIPT_DIR%src\rename_downloads.py" --mapping "!MAPPING_FILE!"

echo.
echo ========================================
echo Done. Press any key to close.
echo ========================================
pause

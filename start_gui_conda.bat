@echo off
cd /d %~dp0

:: Set code page to UTF-8 to fix mojibake
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo [INFO] Using conda env "ocr_time" to start GUI...
echo.

conda run -n ocr_time python app\main.py --gui

echo.
echo [INFO] Process finished. Press any key to exit.
pause >nul


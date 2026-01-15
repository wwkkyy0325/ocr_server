@echo off
cd /d %~dp0

echo [INFO] Using conda env "ocr_time" to start GUI...
echo.

conda run -n ocr_time python app\main.py --gui

echo.
echo [INFO] Process finished. Press any key to exit.
pause >nul


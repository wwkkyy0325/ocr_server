@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%\site_packages;%CD%
if exist "base_env\python.exe" (
    "base_env\python.exe" boot.py
) else (
    echo Error: Python base environment not found.
    pause
)
pause

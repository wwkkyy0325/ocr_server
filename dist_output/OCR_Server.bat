@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%\site_packages;%CD%
if exist "base_env\python.exe" (
    start "" "base_env\python.exe" boot.py
) else (
    echo Error: Python base environment not found in base_env folder.
    echo Please extract python-3.9.x-embed-amd64.zip into base_env folder.
    pause
)

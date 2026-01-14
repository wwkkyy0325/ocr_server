@echo off
setlocal enabledelayedexpansion
title OCR GUI Launcher (conda: ocr_time)

REM 切到脚本所在目录
cd /d %~dp0

echo [INFO] 启动 GUI，使用 conda 环境: ocr_time

REM 激活 conda 环境（尝试常见安装位置与 PATH）
set "TARGET_ENV=ocr_time"
set "CONDA_ACTIVATED="

REM 尝试通过 PATH 激活
call conda activate %TARGET_ENV% >nul 2>&1
if "%CONDA_DEFAULT_ENV%"=="%TARGET_ENV%" set CONDA_ACTIVATED=1

REM 如未激活，尝试常见安装路径
if not defined CONDA_ACTIVATED (
  if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" %TARGET_ENV% >nul 2>&1
  )
)
if "%CONDA_DEFAULT_ENV%"=="%TARGET_ENV%" set CONDA_ACTIVATED=1

if not defined CONDA_ACTIVATED (
  if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" %TARGET_ENV% >nul 2>&1
  )
)
if "%CONDA_DEFAULT_ENV%"=="%TARGET_ENV%" set CONDA_ACTIVATED=1

if not defined CONDA_ACTIVATED (
  echo [ERROR] 未能激活 conda 环境 "%TARGET_ENV%".
  echo         请确认 conda 已安装，且存在该环境。
  pause
  exit /b 1
)

REM 简单检查 Python 是否可用
python -c "import sys;print(sys.version)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 当前环境未找到 Python。请检查 conda 环境配置。
  pause
  exit /b 1
)

REM 关键依赖的最小自检与自动安装（缺啥补啥）
for %%I in (selenium pyqt5 paddleocr requests) do (
  python -c "import pkgutil,sys; sys.exit(0 if pkgutil.find_loader('%%I') else 1)" >nul 2>&1
  if errorlevel 1 (
    echo [INFO] 缺少依赖: %%I ，正在安装...
    pip install %%I
  )
)

REM 准备 ChromeDriver 目录
set "DRIVERS_DIR=%~dp0drivers"
if not exist "%DRIVERS_DIR%" mkdir "%DRIVERS_DIR%"

REM 若不存在 chromedriver.exe，则尝试自动下载匹配当前 Chrome 的版本
if not exist "%DRIVERS_DIR%\chromedriver.exe" (
  echo [INFO] 未检测到 ChromeDriver，尝试自动下载...

  REM 读取 Chrome 版本（优先 HKCU，其次 HKLM）
  set "CHROME_VER="
  for /f "tokens=3 delims= " %%V in ('reg query "HKCU\Software\Google\Chrome\BLBeacon" /v version 2^>nul ^| find "version"') do set "CHROME_VER=%%V"
  if not defined CHROME_VER (
    for /f "tokens=3 delims= " %%V in ('reg query "HKLM\Software\Google\Chrome\BLBeacon" /v version 2^>nul ^| find "version"') do set "CHROME_VER=%%V"
  )

  if defined CHROME_VER (
    for /f "tokens=1 delims=." %%M in ("%CHROME_VER%") do set "MAJOR_VER=%%M"
    echo [INFO] 检测到 Chrome 版本: %CHROME_VER% (主版本: %MAJOR_VER%)
  ) else (
    echo [WARN] 未能检测到 Chrome 版本，将尝试 Selenium 的自动管理或旧版下载策略。
  )

  REM 优先尝试 Chrome for Testing 分发（115+）
  if defined CHROME_VER (
    set "CFT_URL=https://storage.googleapis.com/chrome-for-testing-public/%CHROME_VER%/win64/chromedriver-win64.zip"
    echo [INFO] 尝试下载: %CFT_URL%
    powershell -Command "Try { Invoke-WebRequest -Uri '%CFT_URL%' -OutFile '%DRIVERS_DIR%\chromedriver.zip' -UseBasicParsing } Catch { exit 1 }"
    if exist "%DRIVERS_DIR%\chromedriver.zip" (
      powershell -Command "Try { Expand-Archive -Path '%DRIVERS_DIR%\chromedriver.zip' -DestinationPath '%DRIVERS_DIR%' -Force } Catch { exit 1 }"
      if exist "%DRIVERS_DIR%\chromedriver-win64\chromedriver.exe" (
        copy /y "%DRIVERS_DIR%\chromedriver-win64\chromedriver.exe" "%DRIVERS_DIR%\chromedriver.exe" >nul
      )
      del /f /q "%DRIVERS_DIR%\chromedriver.zip" >nul 2>&1
    )
  )

  REM 若仍不存在，则回退到旧分发（<115）：LATEST_RELEASE_{major}
  if not exist "%DRIVERS_DIR%\chromedriver.exe" (
    if defined MAJOR_VER (
      echo [INFO] 尝试查询旧版 ChromeDriver 版本 (major=%MAJOR_VER%)...
      powershell -Command "$u='https://chromedriver.storage.googleapis.com/LATEST_RELEASE_%MAJOR_VER%'; Try{ $v=(Invoke-WebRequest -Uri $u -UseBasicParsing).Content.Trim(); Write-Output $v }Catch{''}" > "%DRIVERS_DIR%\latest.txt"
      set "DRIVER_VER="
      for /f "usebackq tokens=* delims=" %%L in ("%DRIVERS_DIR%\latest.txt") do set "DRIVER_VER=%%L"
      del /f /q "%DRIVERS_DIR%\latest.txt" >nul 2>&1
      if defined DRIVER_VER (
        set "LEGACY_URL=https://chromedriver.storage.googleapis.com/%DRIVER_VER%/chromedriver_win32.zip"
        echo [INFO] 尝试下载旧版: %LEGACY_URL%
        powershell -Command "Try { Invoke-WebRequest -Uri '%LEGACY_URL%' -OutFile '%DRIVERS_DIR%\chromedriver_legacy.zip' -UseBasicParsing } Catch { exit 1 }"
        if exist "%DRIVERS_DIR%\chromedriver_legacy.zip" (
          powershell -Command "Try { Expand-Archive -Path '%DRIVERS_DIR%\chromedriver_legacy.zip' -DestinationPath '%DRIVERS_DIR%' -Force } Catch { exit 1 }"
          del /f /q "%DRIVERS_DIR%\chromedriver_legacy.zip" >nul 2>&1
        )
      )
    )
  )

  REM 兼容不同解压路径：若仍在子目录，复制到 drivers 根
  if exist "%DRIVERS_DIR%\chromedriver-win32\chromedriver.exe" (
    copy /y "%DRIVERS_DIR%\chromedriver-win32\chromedriver.exe" "%DRIVERS_DIR%\chromedriver.exe" >nul
  )

  if exist "%DRIVERS_DIR%\chromedriver.exe" (
    echo [INFO] ChromeDriver 就绪: %DRIVERS_DIR%\chromedriver.exe
  ) else (
    echo [WARN] 未能自动获取 ChromeDriver。将尝试由 Selenium 自行管理（如果版本支持）。
  )
)

REM 将 drivers 加入 PATH，方便 Selenium 查找
set "PATH=%DRIVERS_DIR%;%PATH%"

REM 启动 GUI（入口：app\main.py --gui）
echo [INFO] 启动应用 GUI...
python "app\main.py" --gui

REM 保持窗口，便于查看日志
echo [INFO] 进程结束。
pause


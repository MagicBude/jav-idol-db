@echo off
setlocal enabledelayedexpansion

rem Switch to the script's directory (repo root)
cd /d "%~dp0"

set "PY=C:\Users\Admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] Python not found: %PY%
    pause
    exit /b 1
)
set "LOG=.workbuddy\logs\fill_series.log"
if not exist ".workbuddy\logs" mkdir ".workbuddy\logs"

echo ==========================================
echo IDOL DB - series backfill tool
echo Only works missing series. Sources: javmenu + javbus + javdb
echo Working dir: %CD%
echo ==========================================
echo.

echo [1/5] Dry-run preview (count only, no writes)...
"%PY%" scripts\update_metadata.py --missing series --sources javmenu,javbus,javdb --dry-run
if errorlevel 1 (
    echo.
    echo Preview failed. Check the errors above.
    pause
    exit /b 1
)
echo.
choice /C YN /M "Start full fetch now? (some sources need Cloudflare, slow)"
if errorlevel 2 (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo [2/5] Fetching missing series (~1670 works)...
echo Log file: %LOG%
"%PY%" scripts\update_metadata.py --missing series --sources javmenu,javbus,javdb > "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo Fetch failed. See %LOG%
    pause
    exit /b 1
)

echo.
echo [3/5] Sweeping format noise and protecting attribution fields...
"%PY%" scripts\sweep_works.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo Sweep failed. See %LOG%
    pause
    exit /b 1
)

echo.
echo [4/5] Rebuilding site index...
"%PY%" scripts\build_index.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo Index build failed. See %LOG%
    pause
    exit /b 1
)

echo.
echo [5/5] Done!
git status --short
echo.

choice /C YN /M "Commit and push results?"
if errorlevel 2 (
    echo No commit. Finished.
    pause
    exit /b 0
)

git add data\works data\index.json site\assets\js\data.js
git commit -m "data(works): backfill series via javmenu+javbus+javdb" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo Commit failed or nothing to commit.
    pause
    exit /b 1
)

rem Prefer SSH over 443 (port 22 may be blocked on some networks)
set "GIT_SSH_COMMAND=ssh -p 443 -o Hostname=ssh.github.com -o StrictHostKeyChecking=no"
git push origin main >> "%LOG%" 2>&1
if errorlevel 1 (
    echo SSH-443 push failed, trying normal SSH...
    set "GIT_SSH_COMMAND="
    git push origin main
)

echo.
echo All done. Log: %LOG%
pause


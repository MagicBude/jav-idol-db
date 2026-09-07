@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 切到脚本所在目录（仓库根目录）
cd /d "%~dp0"

set "PY=C:\Users\Admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
set "LOG=.workbuddy\logs\fill_series.log"
if not exist ".workbuddy\logs" mkdir ".workbuddy\logs"

echo ==========================================
echo IDOL DB - 本地 series 补全工具
echo 仅处理缺 series 的作品，使用 javbus + javdb
echo 当前目录：%CD%
echo ==========================================
echo.

:: 先预览，确认命中范围
echo [1/5] 预览 --dry-run（只统计，不写库）...
"%PY%" scripts\update_metadata.py --missing series --sources javbus,javdb --dry-run
if %errorlevel% neq 0 (
    echo.
    echo 预览失败，请检查上面的错误信息。
    pause
    exit /b 1
)
echo.
choice /C YN /M "是否继续正式抓取（会过 Cloudflare，耗时较长）"
if %errorlevel% neq 1 (
    echo 已取消。
    pause
    exit /b 0
)

:: 正式抓取：只补 series，只用 javbus + javdb
echo.
echo [2/5] 正式抓取 javbus + javdb（缺 series 的 1670 部左右）...
echo 日志写入：%LOG%
"%PY%" scripts\update_metadata.py --missing series --sources javbus,javdb > "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 抓取失败，请查看 %LOG%
    pause
    exit /b 1
)

:: 跑后清扫：格式噪声、归属保护、冲突 cast 回退
echo.
echo [3/5] 清扫格式噪声并保护归属字段...
"%PY%" scripts\sweep_works.py >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 清扫失败，请查看 %LOG%
    pause
    exit /b 1
)

:: 重建索引
echo.
echo [4/5] 重建站点索引...
"%PY%" scripts\build_index.py >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 索引失败，请查看 %LOG%
    pause
    exit /b 1
)

echo.
echo [5/5] 抓取完成！
git status --short
echo.

choice /C YN /M "是否提交并推送结果"
if %errorlevel% neq 1 (
    echo 不提交，结束。
    pause
    exit /b 0
)

git add data\works data\index.json site\assets\js\data.js
git commit -m "data(works): 补全 series（javbus+javdb）" >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 提交失败或无改动。
    pause
    exit /b 1
)

:: 优先走 SSH over 443，部分网络下 22 会被拦截
set "GIT_SSH_COMMAND=ssh -p 443 -o Hostname=ssh.github.com -o StrictHostKeyChecking=no"
git push origin main >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo SSH-443 推送失败，尝试普通 SSH...
    set "GIT_SSH_COMMAND="
    git push origin main
)

echo.
echo 全部完成。日志：%LOG%
pause

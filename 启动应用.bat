@echo off
chcp 65001 >nul
echo ========================================
echo   FoodGuardian AI - 智能食谱助手
echo ========================================
echo.
echo 正在启动程序...
echo.

REM 使用系统默认的 Python 3.11.9
python "%~dp0food_guardian_ai.py"

if errorlevel 1 (
    echo.
    echo 程序运行出错！
    pause
)

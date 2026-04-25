@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   FoodGuardian AI v2.0 - 启动程序
echo ========================================
echo.
echo 正在检查依赖...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [安装] Flask 未安装,正在安装...
    pip install flask
) else (
    echo [OK] Flask 已安装
)

echo.
echo 正在启动服务器...
echo.
python food_guardian_ai_2.py

pause

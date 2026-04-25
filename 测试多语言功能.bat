@echo off
chcp 65001 >nul
echo.
echo ====================================================================
echo   FoodGuardian AI - 多语言功能快速验证脚本
echo ====================================================================
echo.

echo [1/5] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python,请先安装Python 3.7+
    pause
    exit /b 1
)
echo ✅ Python环境正常

echo.
echo [2/5] 检查依赖包...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Flask未安装,正在安装...
    pip install flask requests pillow
) else (
    echo ✅ Flask已安装
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  requests未安装,正在安装...
    pip install requests
) else (
    echo ✅ requests已安装
)

python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Pillow未安装,正在安装...
    pip install pillow
) else (
    echo ✅ Pillow已安装
)

echo.
echo [3/5] 检查关键文件...
if not exist "food_guardian_ai_2.py" (
    echo ❌ 错误: 找不到 food_guardian_ai_2.py
    pause
    exit /b 1
)
echo ✅ food_guardian_ai_2.py 存在

if not exist "templates\index.html" (
    echo ❌ 错误: 找不到 templates\index.html
    pause
    exit /b 1
)
echo ✅ templates\index.html 存在

if not exist "static\js\i18n.js" (
    echo ❌ 错误: 找不到 static\js\i18n.js
    pause
    exit /b 1
)
echo ✅ static\js\i18n.js 存在

if not exist "locales\zh-CN.json" (
    echo ❌ 错误: 找不到 locales\zh-CN.json
    pause
    exit /b 1
)
echo ✅ locales\zh-CN.json 存在

if not exist "locales\en-US.json" (
    echo ❌ 错误: 找不到 locales\en-US.json
    pause
    exit /b 1
)
echo ✅ locales\en-US.json 存在

echo.
echo [4/5] 检查端口占用...
netstat -ano | findstr ":5000" >nul
if not errorlevel 1 (
    echo ⚠️  端口5000已被占用,可能需要先关闭之前的进程
    echo    按 Ctrl+C 可以取消启动
    timeout /t 3 >nul
) else (
    echo ✅ 端口5000可用
)

echo.
echo [5/5] 启动应用...
echo.
echo ====================================================================
echo   🍽️  FoodGuardian AI v2.0 正在启动...
echo ====================================================================
echo.
echo 📋 验证清单:
echo   ☐ 浏览器访问 http://localhost:5000
echo   ☐ 按F12打开开发者工具
echo   ☐ 检查Console显示 "✅ i18n initialized"
echo   ☐ 点击国旗按钮测试语言切换
echo   ☐ 生成食谱测试AI多语言输出
echo.
echo 💡 详细测试步骤请参考: 多语言功能测试指南.md
echo.
echo ====================================================================
echo.

python food_guardian_ai_2.py

pause

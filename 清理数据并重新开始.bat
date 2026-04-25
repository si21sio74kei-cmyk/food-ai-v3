@echo off
chcp 65001 >nul
echo ========================================
echo   FoodGuardian AI - 数据清理工具
echo ========================================
echo.

:: 备份旧数据
if exist fgai_local_data.json (
    echo [1/3] 备份旧数据文件...
    copy fgai_local_data.json fgai_local_data_backup_%date:~0,4%%date:~5,2%%date:~8,2%.json >nul
    echo      ✅ 已备份到: fgai_local_data_backup_%date:~0,4%%date:~5,2%%date:~8,2%.json
) else (
    echo [1/3] 没有旧数据文件，跳过备份
)

echo.
echo [2/3] 删除旧数据文件...
del /f /q fgai_local_data.json
echo      ✅ 已删除 fgai_local_data.json

echo.
echo [3/3] 创建新的空白数据文件...
(
echo {
echo   "nickname": "",
echo   "waste_reduced": 0,
echo   "water_saved": 0,
echo   "co2_reduced": 0,
echo   "population_group": "adults",
echo   "daily_intake_records": [],
echo   "fridge_inventory": [],
echo   "generation_count": 0
echo }
) > fgai_local_data.json
echo      ✅ 已创建新的空白数据文件

echo.
echo ========================================
echo   ✅ 数据清理完成！
echo ========================================
echo.
echo 下一步操作：
echo 1. 启动服务器：python food_guardian_ai_2.py
echo 2. 打开浏览器：http://localhost:5000
echo 3. 按 F12 打开控制台查看日志
echo 4. 开始测试食谱生成功能
echo.
pause

# -*- coding: utf-8 -*-
"""
FoodGuardian AI - 国际化功能快速测试
"""

import subprocess
import time
import webbrowser
import os

def main():
    print("="*70)
    print("🚀 FoodGuardian AI - 国际化功能测试")
    print("="*70)
    
    print("\n📋 测试步骤:")
    print("1. 启动Flask服务器")
    print("2. 自动打开浏览器")
    print("3. 手动测试以下功能:")
    print("   ✅ 点击右上角语言切换按钮")
    print("   ✅ 在AI对话中输入问题,检查回复语言")
    print("   ✅ 生成食谱,检查输出语言")
    print("   ✅ 营养分析,检查结果语言")
    print("   ✅ 采购清单,检查结果语言")
    
    input("\n⏎ 按回车键启动服务器...")
    
    # 启动Flask服务器
    print("\n🌐 正在启动服务器...")
    try:
        process = subprocess.Popen(
            ['python', 'food_guardian_ai_2.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待服务器启动
        print("⏳ 等待服务器就绪...")
        time.sleep(3)
        
        # 打开浏览器
        url = "http://localhost:5000"
        print(f"\n✅ 服务器已启动!")
        print(f"🌍 访问地址: {url}")
        print("\n💡 提示:")
        print("   - 按 Ctrl+C 停止服务器")
        print("   - 查看控制台输出了解AI调用详情")
        
        webbrowser.open(url)
        
        # 保持进程运行
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
        process.terminate()
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n💡 请手动运行: python food_guardian_ai_2.py")

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
HTML国际化自动化工具
为index.html中的静态文本元素添加data-i18n属性
"""

import re

def process_html():
    """处理HTML文件,添加data-i18n属性"""
    
    html_path = 'templates/index.html'
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"📄 读取HTML文件: {html_path}")
    print(f"   文件大小: {len(content)} 字符")
    
    # 定义需要替换的文本映射 (中文文本 -> data-i18n键)
    replacements = [
        # 页面标题
        (r'<title>FoodGuardian AI - 智能食谱助手</title>', 
         '<title data-i18n="app.title">FoodGuardian AI - 智能食谱助手</title>'),
        
        # 导航栏
        (r'(<div class="nav-item"[^>]*>)首页', 
         r'\1<span data-i18n="nav.home">首页</span>'),
        (r'(<div class="nav-item"[^>]*>)食谱', 
         r'\1<span data-i18n="nav.recipe">食谱</span>'),
        (r'(<div class="nav-item"[^>]*>)营养', 
         r'\1<span data-i18n="nav.nutrition">营养</span>'),
        (r'(<div class="nav-item"[^>]*>)冰箱', 
         r'\1<span data-i18n="nav.fridge">冰箱</span>'),
        (r'(<div class="nav-item"[^>]*>)我的', 
         r'\1<span data-i18n="nav.profile">我的</span>'),
        (r'(<div class="nav-item"[^>]*>)AI助手', 
         r'\1<span data-i18n="nav.chat">AI助手</span>'),
        (r'(<div class="nav-item"[^>]*>)语音', 
         r'\1<span data-i18n="nav.voice">语音</span>'),
        (r'(<div class="nav-item"[^>]*>)采购', 
         r'\1<span data-i18n="nav.shopping">采购</span>'),
    ]
    
    # 执行替换
    modified_count = 0
    for pattern, replacement in replacements:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            modified_count += 1
            print(f"   ✅ 已替换: {pattern[:50]}...")
    
    # 保存修改后的文件
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✨ 完成! 共修改 {modified_count} 处")
    print(f"💡 提示: 这只是示例,完整实现需要手动检查所有文本元素")

if __name__ == '__main__':
    process_html()

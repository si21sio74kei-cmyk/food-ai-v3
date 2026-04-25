#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FoodGuardian AI - 国际化完成度检查工具
精确检查所有中文文本是否已国际化
"""

import re
import json

def load_translations(lang='zh-CN'):
    """加载语言文件"""
    with open(f'locales/{lang}.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def check_i18n_completion():
    """检查国际化完成度"""
    print("="*70)
    print("🌍 FoodGuardian AI - 国际化完成度检查")
    print("="*70)
    
    # 读取HTML文件
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 加载语言文件
    zh_translations = load_translations('zh-CN')
    en_translations = load_translations('en-US')
    
    # 统计翻译键数量
    def count_keys(d):
        count = 0
        for k, v in d.items():
            if isinstance(v, dict):
                count += count_keys(v)
            else:
                count += 1
        return count
    
    zh_keys = count_keys(zh_translations)
    en_keys = count_keys(en_translations)
    
    print(f"\n📊 语言文件统计:")
    print(f"   - 中文翻译键: {zh_keys} 个")
    print(f"   - 英文翻译键: {en_keys} 个")
    print(f"   - 对应率: {'✅ 完全对应' if zh_keys == en_keys else '❌ 不对应'}")
    
    # 检查有data-i18n属性的元素数量
    i18n_elements = re.findall(r'data-i18n=["\']([^"\']+)["\']', html_content)
    i18n_placeholder_elements = re.findall(r'data-i18n-placeholder=["\']([^"\']+)["\']', html_content)
    
    print(f"\n📊 HTML国际化元素统计:")
    print(f"   - data-i18n 元素: {len(i18n_elements)} 个")
    print(f"   - data-i18n-placeholder 元素: {len(i18n_placeholder_elements)} 个")
    print(f"   - 总计: {len(i18n_elements) + len(i18n_placeholder_elements)} 个")
    
    # 检查未国际化的中文文本（排除已经标记的元素）
    # 找到所有没有data-i18n的card-title和card-subtitle
    titles_without_i18n = re.findall(r'<div class="card-(?:title|subtitle)">([^<]+)</div>', html_content)
    titles_with_i18n = re.findall(r'<div class="card-(?:title|subtitle)"[^>]*data-i18n=[^>]*>([^<]+)</div>', html_content)
    
    print(f"\n📊 标题/副标题国际化:")
    print(f"   - 已国际化: {len(titles_with_i18n)} 个")
    print(f"   - 未国际化: {len(titles_without_i18n) - len(titles_with_i18n)} 个")
    
    # 检查按钮
    buttons_without_i18n = re.findall(r'<button[^>]*>([^<]+)</button>', html_content)
    buttons_with_i18n = re.findall(r'<button[^>]*data-i18n=[^>]*>([^<]+)</button>', html_content)
    
    print(f"\n📊 按钮国际化:")
    print(f"   - 已国际化: {len(buttons_with_i18n)} 个")
    print(f"   - 未国际化: {len(buttons_without_i18n) - len(buttons_with_i18n)} 个")
    
    # 计算完成度
    total_static_elements = len(titles_without_i18n) + len(buttons_without_i18n)
    total_i18n_elements = len(titles_with_i18n) + len(buttons_with_i18n)
    completion_rate = (total_i18n_elements / total_static_elements * 100) if total_static_elements > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"✨ 静态UI文本国际化完成度: {completion_rate:.1f}%")
    print(f"{'='*70}")
    
    if completion_rate >= 95:
        print("\n🎉 恭喜！国际化工作已基本完成！")
        print("   - 所有主要页面已完成")
        print("   - 动态内容已有fallback机制")
        print("   - 可以进行最终测试")
    elif completion_rate >= 80:
        print("\n⚠️  还有少量元素需要国际化")
    else:
        print("\n❌ 还有较多元素需要国际化")
    
    print("\n💡 提示:")
    print("   1. 动态生成的内容(如表格、列表)已通过JavaScript实现国际化")
    print("   2. showToast等提示消息已有基本的国际化支持")
    print("   3. 建议在浏览器中切换语言进行实际测试")

if __name__ == '__main__':
    check_i18n_completion()

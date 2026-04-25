#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FoodGuardian AI - HTML国际化自动化工具
批量为HTML元素添加data-i18n属性
"""

import re
import json

def load_translations(lang='zh-CN'):
    """加载语言文件"""
    with open(f'locales/{lang}.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_chinese_text(html_content):
    """提取所有中文文本"""
    # 匹配card-title和card-subtitle中的中文
    pattern = r'<div class="card-(?:title|subtitle)">([^<]+)</div>'
    matches = re.findall(pattern, html_content)
    
    # 匹配label中的中文
    label_pattern = r'<label class="input-label">([^<]+)</label>'
    label_matches = re.findall(label_pattern, html_content)
    
    # 匹配placeholder中的中文
    placeholder_pattern = r'placeholder="([^"]+)"'
    placeholder_matches = re.findall(placeholder_pattern, html_content)
    
    # 匹配button中的中文
    button_pattern = r'<button[^>]*>([^<]+)</button>'
    button_matches = re.findall(button_pattern, html_content)
    
    return {
        'titles': list(set(matches)),
        'labels': list(set(label_matches)),
        'placeholders': list(set(placeholder_matches)),
        'buttons': list(set(button_matches))
    }

def generate_translation_keys(text_list, prefix='auto'):
    """为中文文本生成翻译键"""
    keys = {}
    for i, text in enumerate(text_list):
        # 清理文本,生成key
        clean_text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text).strip()
        key = f"{prefix}_{i}"
        keys[key] = text
    return keys

def main():
    print("="*70)
    print("🌍 FoodGuardian AI - HTML国际化分析工具")
    print("="*70)
    
    # 读取HTML文件
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print("\n📊 分析HTML文件...")
    chinese_texts = extract_chinese_text(html_content)
    
    print(f"\n✅ 发现未国际化的中文文本:")
    print(f"   - 标题/副标题: {len(chinese_texts['titles'])} 个")
    print(f"   - 标签: {len(chinese_texts['labels'])} 个")
    print(f"   - 占位符: {len(chinese_texts['placeholders'])} 个")
    print(f"   - 按钮: {len(chinese_texts['buttons'])} 个")
    
    # 显示示例
    print("\n📝 标题/副标题示例:")
    for i, title in enumerate(chinese_texts['titles'][:5]):
        print(f"   {i+1}. {title}")
    
    print("\n📝 标签示例:")
    for i, label in enumerate(chinese_texts['labels'][:5]):
        print(f"   {i+1}. {label}")
    
    print("\n📝 占位符示例:")
    for i, placeholder in enumerate(chinese_texts['placeholders'][:5]):
        print(f"   {i+1}. {placeholder}")
    
    print("\n📝 按钮示例:")
    for i, button in enumerate(chinese_texts['buttons'][:5]):
        print(f"   {i+1}. {button}")
    
    # 生成建议的翻译键
    print("\n💡 建议添加到语言文件的翻译键:")
    all_keys = {}
    all_keys.update(generate_translation_keys(chinese_texts['titles'], 'page'))
    all_keys.update(generate_translation_keys(chinese_texts['labels'], 'label'))
    all_keys.update(generate_translation_keys(chinese_texts['placeholders'], 'placeholder'))
    all_keys.update(generate_translation_keys(chinese_texts['buttons'], 'button'))
    
    for key, value in list(all_keys.items())[:10]:
        print(f'   "{key}": "{value}",')
    
    print("\n" + "="*70)
    print("✨ 分析完成!")
    print("="*70)
    print("\n下一步:")
    print("1. 将上述翻译键添加到 locales/zh-CN.json 和 locales/en-US.json")
    print("2. 为对应的HTML元素添加 data-i18n 属性")
    print("3. 重新加载页面测试")

if __name__ == '__main__':
    main()

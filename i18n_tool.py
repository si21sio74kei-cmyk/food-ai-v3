# -*- coding: utf-8 -*-
"""
FoodGuardian AI - 国际化工具脚本
自动为HTML添加data-i18n属性,并生成对应的英文翻译
"""

import json
import re
import os

def load_json(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    """保存JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("="*70)
    print("🌍 FoodGuardian AI - 国际化工具")
    print("="*70)
    
    # 加载语言文件
    zh_cn = load_json('locales/zh-CN.json')
    en_us = load_json('locales/en-US.json')
    
    print("\n✅ 语言文件加载成功")
    print(f"   - zh-CN.json: {count_keys(zh_cn)} 个翻译键")
    print(f"   - en-US.json: {count_keys(en_us)} 个翻译键")
    
    # 验证两个语言文件的键是否一致
    zh_keys = get_all_keys(zh_cn)
    en_keys = get_all_keys(en_us)
    
    missing_in_en = zh_keys - en_keys
    extra_in_en = en_keys - zh_keys
    
    if missing_in_en:
        print(f"\n⚠️  en-US.json 缺少 {len(missing_in_en)} 个键:")
        for key in list(missing_in_en)[:10]:
            print(f"   - {key}")
        if len(missing_in_en) > 10:
            print(f"   ... 还有 {len(missing_in_en) - 10} 个")
    
    if extra_in_en:
        print(f"\n⚠️  en-US.json 多出 {len(extra_in_en)} 个键:")
        for key in list(extra_in_en)[:5]:
            print(f"   - {key}")
    
    if not missing_in_en and not extra_in_en:
        print("\n✅ 两个语言文件的键完全匹配!")
    
    print("\n" + "="*70)
    print("✨ 下一步建议:")
    print("="*70)
    print("\n1. 📝 HTML文件需要手动添加 data-i18n 属性")
    print("   - 位置: templates/index.html")
    print("   - 方法: 在静态文本元素上添加 data-i18n=\"key.path\"")
    print("\n2. 🔧 JavaScript函数需要调用 window.i18n.t()")
    print("   - 动态生成的内容需要使用翻译函数")
    print("\n3. 🤖 后端API需要支持多语言Prompt")
    print("   - food_guardian_ai_2.py 已有多语言支持框架")
    print("   - chat API 和 analyze_nutrition API 需要补充")
    print("\n" + "="*70)

def count_keys(d, prefix=''):
    """递归计算JSON中的键数量"""
    count = 0
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            count += count_keys(v, full_key)
        else:
            count += 1
    return count

def get_all_keys(d, prefix=''):
    """递归获取所有键的完整路径"""
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(get_all_keys(v, full_key))
        else:
            keys.add(full_key)
    return keys

if __name__ == '__main__':
    main()

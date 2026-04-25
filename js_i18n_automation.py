# -*- coding: utf-8 -*-
"""
JavaScript国际化自动化工具
为index.html中的JavaScript函数添加多语言支持
"""

import re

def process_javascript():
    """处理HTML文件中的JavaScript代码,添加多语言支持"""
    
    html_path = 'templates/index.html'
    
    print("="*70)
    print("🔧 JavaScript 国际化工具")
    print("="*70)
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"\n📄 读取HTML文件: {html_path}")
    print(f"   文件大小: {len(content)} 字符")
    
    # 定义需要替换的模式 (旧代码 -> 新代码)
    replacements = [
        # 1. updateWelcomeMessage 函数
        (r"(welcomeEl\.textContent = `)欢迎回来,\$\{appData\.nickname\}!今天也一起为地球省下一点点资源吧。(`;)",
         r"""\1${window.i18n ? window.i18n.t('home.welcome_back', {nickname: appData.nickname}) : `欢迎回来,${appData.nickname}!今天也一起为地球省下一点点资源吧。`}\2"""),
        
        # 2. saveNickname - 错误提示
        (r"(showToast\(')请输入一个昵称('\);)",
         r"\1${window.i18n ? window.i18n.t('common.nickname_required') : '请输入一个昵称'}\2"),
        
        # 3. saveNickname - 成功提示
        (r"(showToast\(')✅ 昵称已保存('\);)",
         r"\1${window.i18n ? window.i18n.t('common.nickname_saved') : '✅ 昵称已保存'}\2"),
        
        # 4. resetStats - confirm消息
        (r"(if \(confirm\(')确定要清零本机的所有环保统计吗\?此操作不可恢复。\('\))",
         r"const confirmMsg = window.i18n ? window.i18n.t('common.confirm_reset') : '确定要清零本机的所有环保统计吗?此操作不可恢复。';\n            if (confirm(confirmMsg))"),
        
        # 5. resetStats - 成功提示
        (r"(showToast\(')✅ 统计已重置('\);)",
         r"\1${window.i18n ? window.i18n.t('common.stats_reset_success') : '✅ 统计已重置'}\2"),
        
        # 6. resetGenerationCounter - confirm消息 (简化版,避免复杂正则)
        # 这个需要手动处理,因为文本太长
        
        # 7. 食材验证错误提示
        (r"(showToast\(')请至少输入一种食材('\);)",
         r"\1${window.i18n ? window.i18n.t('common.ingredient_required') : '请至少输入一种食材'}\2"),
    ]
    
    modified_count = 0
    for pattern, replacement in replacements:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content, count=1)
            modified_count += 1
            print(f"   ✅ 已替换模式 #{modified_count}")
        else:
            print(f"   ⚠️  未找到模式: {pattern[:60]}...")
    
    # 保存修改后的文件
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✨ 完成! 共修改 {modified_count} 处")
    print(f"\n💡 提示:")
    print(f"   - 这只是部分自动化修改")
    print(f"   - 还需要手动处理API调用中的language参数")
    print(f"   - 建议查看 I18N_IMPLEMENTATION_PLAN.md 获取完整清单")

if __name__ == '__main__':
    process_javascript()

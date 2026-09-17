# -*- coding: utf-8 -*-
"""改造后完整性验证（临时脚本）"""
import re, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
html = open('templates/index.html', encoding='utf-8').read()

# 1. CSS 括号平衡
css = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
o, c = css.count('{'), css.count('}')
print(f'1. CSS 括号: {o}/{c} 平衡: {o == c}')

# 2. i18n key 引用完整性
zh = json.load(open('locales/zh-CN.json', encoding='utf-8'))
en = json.load(open('locales/en-US.json', encoding='utf-8'))
def flat(d, p=''):
    ks = set()
    for k, v in d.items():
        ks.add(p + k)
        if isinstance(v, dict):
            ks |= flat(v, p + k + '.')
    return ks
zhk, enk = flat(zh), flat(en)
used = set(re.findall(r'data-i18n(?:-placeholder|-title)?="([^"]+)"', html))
used |= set(re.findall(r"i18n\.t\('([^']+)'\)", html))
missing_zh = {k for k in used if k not in zhk}
missing_en = {k for k in used if k not in enk}
print(f'2. i18n 引用 {len(used)} 个 key：zh 缺失 {len(missing_zh)} {sorted(missing_zh)[:5]}，en 缺失 {len(missing_en)} {sorted(missing_en)[:5]}')

# 3. 中文间双空格残留
dbl = [ln.strip()[:80] for ln in html.split('\n') if re.search(r'[\u4e00-\u9fff]  +[\u4e00-\u9fff]', ln)]
print(f'3. 中文间双空格残留: {len(dbl)} 行')
for d in dbl[:5]:
    print('   ', d)

# 4. SVG 图标数量
print(f'4. SVG 图标: {html.count("<svg ")} 个')

# 5. 残余 emoji
E = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]')
print(f'5. 残余 emoji: {len(E.findall(html))} 个')

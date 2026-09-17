# -*- coding: utf-8 -*-
"""检测 emoji 风险点：逻辑依赖 / 纯 emoji 元素内容（临时脚本）"""
import re, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

E = '[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u2728\u2705\u274C\u2757\u3030]'
html = open('templates/index.html', encoding='utf-8').read()
lines = html.split('\n')

print('==== A. 逻辑依赖 emoji 的代码行（startsWith/includes/indexOf/split/=== 等）====')
for i, ln in enumerate(lines, 1):
    if re.search(r"(startsWith|includes|indexOf|split|endsWith|===|!==)\s*\(.{0,4}'[^']*" + E, ln):
        print(f'{i}: {ln.strip()[:110]}')

print('\n==== B. 纯 emoji 内容的元素（>EMOJI< 模式，按钮会变空）====')
for i, ln in enumerate(lines, 1):
    m = re.search(r'>\s*(' + E + r'{1,2})\s*<', ln)
    if m:
        print(f'{i}: [{m.group(1)}] {ln.strip()[:110]}')

print('\n==== C. JS 设置纯 emoji 的 textContent/innerHTML ====')
for i, ln in enumerate(lines, 1):
    if re.search(r"(textContent|innerHTML)\s*=\s*'[^']*" + E, ln):
        print(f'{i}: {ln.strip()[:110]}')

print('\n==== D. i18n.js 里的 emoji 逻辑 ====')
try:
    i18n = open('static/js/i18n.js', encoding='utf-8').read()
    for i, ln in enumerate(i18n.split('\n'), 1):
        if re.search(E, ln) and re.search(r'(flag|Flag|current-lang|textContent|innerHTML|===|return)', ln):
            print(f'{i}: {ln.strip()[:110]}')
except FileNotFoundError:
    print('static/js/i18n.js 不存在')

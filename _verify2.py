# -*- coding: utf-8 -*-
"""最终 i18n 校验（临时脚本）"""
import re, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
html = open('templates/index.html', encoding='utf-8').read()
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
print(f'i18n 引用 {len(used)} key，zh 缺失 {len(used - zhk)}，en 缺失 {len(used - enk)}')
assert not (used - zhk) and not (used - enk), '仍有缺失 key'
print('JSON 合法: OK')

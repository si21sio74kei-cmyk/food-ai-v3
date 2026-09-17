# -*- coding: utf-8 -*-
"""批量清理 locale 文案 emoji（修正版：key 结构校验函数独立）"""
import re, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

E = '[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u2728\u2705\u274C\u2757\u3030]'

def clean(text):
    text = re.sub(E + ' ', '', text)   # "✅ 文字" → "文字"
    text = re.sub(' ' + E, '', text)   # "文字 ✅" → "文字"
    text = re.sub(E, '', text)         # 孤立 emoji 兜底
    return text

def keys_of(d, prefix=''):
    ks = set()
    if isinstance(d, dict):
        for k, v in d.items():
            ks.add(prefix + k)
            ks |= keys_of(v, prefix + k + '.')
    return ks

for f in ['locales/zh-CN.json', 'locales/en-US.json']:
    raw = open(f, encoding='utf-8').read()
    kb = keys_of(json.loads(raw))
    new_raw = clean(raw)
    ka = keys_of(json.loads(new_raw))
    assert kb == ka, f'{f} key 结构被破坏！'
    open(f, 'w', encoding='utf-8').write(new_raw)
    print(f'{f}: 清理 {len(re.findall(E, raw))} 个 emoji，JSON 合法且 key 结构无损（{len(kb)} 个 key）')

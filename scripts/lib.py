"""Caliper Bench 快照解析共用工具。

排行榜页面把全部数据内嵌成一个 `const DATA = [...]` 的 JSON 数组。
直接数括号会因转义引号而解析失败，所以必须用字符串感知的扫描。
"""
import json
import re

MOE_RE = re.compile(r'\bA\d+(?:\.\d+)?B\b|\bMoE\b|mixture', re.I)


def load_snapshot(path):
    """读取快照文件，返回 (generated_utc, models)。

    generated_utc 形如 '2026-11-21 09:26'，取不到时为 '?'。
    注意：站点时钟有偏移（曾观测到比真实 UTC 超前约 19 小时），
    时间戳只用于排序，不要当成真实抓取时刻。
    """
    h = open(path, encoding='utf-8', errors='ignore').read()
    m = re.search(r'generated (\d{4}-\d\d-\d\d \d\d:\d\d) UTC', h)
    marker = 'const DATA = '
    i = h.index(marker) + len(marker)
    depth, instr, esc = 0, False, False
    for j in range(i, len(h)):
        c = h[j]
        if instr:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c in '[{':
                depth += 1
            elif c in ']}':
                depth -= 1
                if depth == 0:
                    return (m.group(1) if m else '?'), json.loads(h[i:j + 1])
    raise ValueError('未找到内嵌的 const DATA')


def num(x, key, default=0):
    """取数值字段，缺失/非数值时返回 default。榜单用 0 表示无数据。"""
    v = x.get(key)
    return v if isinstance(v, (int, float)) else default


def is_moe(x):
    """按显示名和 lineage 判断是否 MoE。榜单没有独立字段。"""
    blob = (x.get('display_name') or '') + ' ' + (x.get('lineage') or '')
    return bool(MOE_RE.search(blob))


def under40(models, limit=40):
    """筛出 ≤40B 的开源模型。

    Proprietary 类没有可信参数量，一律排除；evaluation_tier != 1.0 的是
    低置信度条目，也排除，避免噪声污染排名。
    """
    out = []
    for x in models:
        if x.get('model_class') == 'Proprietary':
            continue
        if num(x, 'parameter_count_b', 99) > limit:
            continue
        if x.get('evaluation_tier') != 1.0:
            continue
        out.append(x)
    return out


def spec(x):
    """人类可读的规格串，如 '31B Finetune' / '闭源 Proprietary'。"""
    pc = num(x, 'parameter_count_b')
    cls = (x.get('model_class') or '?')[:3]
    return f'{pc:.0f}B {cls}' if pc else f'闭源 {cls}'


def table(rows, headers):
    """把行列表渲染成 Markdown 表格。"""
    out = ['| ' + ' | '.join(headers) + ' |',
           '|' + '|'.join(['---'] * len(headers)) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(str(c) for c in r) + ' |')
    return '\n'.join(out)

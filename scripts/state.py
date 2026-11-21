#!/usr/bin/env python3
"""把完整快照压缩成可入库的状态文件，并对比两个状态。

原始 HTML 每期约 3.4 MB，逐期入库会让仓库一年涨到 1 GB 量级。
所以 CI 里只提交 state.json.gz（约 40 KB）与差分报告，HTML 走 artifact。

用法：
    python3 scripts/state.py build archive/2026-11-21_0926.html data/state.json.gz
    python3 scripts/state.py diff data/state.json.gz /tmp/state.json.gz
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_snapshot, num, spec

FIELDS = ['combined_v3', 'combined_se_v3', 'cw_score_v3', 'rp_score_v3',
          'erp_score_v3', 'drp_score_v3', 'slop_combo_v3', 'literal_combo_v3',
          'nsfw_v3', 'darkness_v3']
TRACKED = ['combined_v3', 'rp_score_v3', 'erp_score_v3', 'drp_score_v3',
           'cw_score_v3', 'slop_combo_v3', 'literal_combo_v3']
DRIFT = 0.5


def build(path):
    ts, models = load_snapshot(path)
    rows = {}
    for x in models:
        rec = {'n': x.get('display_name', ''), 'c': x.get('model_class', ''),
               'p': num(x, 'parameter_count_b'), 't': x.get('evaluation_tier')}
        for f in FIELDS:
            rec[f] = num(x, f)
        rows[x['slug']] = rec
    return {'generated': ts, 'count': len(models), 'models': rows}


def row_md(rec, delta=None):
    d = f'{delta:+.1f}' if delta is not None else '—'
    spec_s = (f"{rec['p']:.0f}B {rec['c'][:3]}" if rec['p']
              else f"闭源 {rec['c'][:3]}")
    return (f"| {rec['combined_v3']:.1f} | {d} | {rec['combined_se_v3']:.2f} | "
            f"{rec['nsfw_v3']:.2f} | {rec['rp_score_v3']:.1f} | "
            f"{rec['erp_score_v3']:.1f} | {rec['drp_score_v3']:.1f} | "
            f"{rec['slop_combo_v3']:.1f} | {spec_s} | {rec['n'][:44]} |")


HDR = ('| 综合 | Δ | ± | nsfw | RP | ERP | DRP | slop | 规格 | 模型 |\n'
       '|---|---|---|---|---|---|---|---|---|---|')


def diff(old, new):
    o, n = old['models'], new['models']
    added = [n[s] for s in n if s not in o]
    removed = [o[s] for s in o if s not in n]
    out = [f"快照 {old['generated']} → {new['generated']}　"
           f"{old['count']} → {new['count']}（{new['count'] - old['count']:+d}）", '']

    if added:
        out += [f'### 新增 {len(added)} 个', '', HDR]
        for r in sorted(added, key=lambda y: -y['combined_v3']):
            out.append(row_md(r))
        out.append('')

    if removed:
        out += [f'### 消失 {len(removed)} 个', '', HDR]
        for r in sorted(removed, key=lambda y: -y['combined_v3']):
            out.append(row_md(r))
        out.append('')

    changed = []
    for s in n:
        if s not in o:
            continue
        d = n[s]['combined_v3'] - o[s]['combined_v3']
        if abs(d) >= DRIFT:
            changed.append((d, n[s]))
    if changed:
        out += [f'### 分数变动 {len(changed)} 个（≥{DRIFT}）', '', HDR]
        for d, r in sorted(changed, key=lambda t: -abs(t[0]))[:40]:
            out.append(row_md(r, d))
        out.append('')

    if not (added or removed or changed):
        out.append('无变化（纯抓取，模型与分数均未动）')
    return '\n'.join(out)


def load_state(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def save_state(state, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    raw = json.dumps(state, ensure_ascii=False, separators=(',', ':')).encode()
    with gzip.GzipFile(path, 'wb', compresslevel=9, mtime=0) as f:
        f.write(raw)
    return len(raw)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == 'build':
        st = build(sys.argv[2])
        size = save_state(st, sys.argv[3])
        print(f"state: {st['count']} models, {size / 1024:.0f} KB raw → {sys.argv[3]}")
    elif cmd == 'diff':
        print(diff(load_state(sys.argv[2]), load_state(sys.argv[3])))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()

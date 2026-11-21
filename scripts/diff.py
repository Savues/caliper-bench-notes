#!/usr/bin/env python3
"""对比两个快照：新增/消失的模型，以及分数变动的旧模型。

用法：
    python3 scripts/diff.py                       # 自动取 archive/ 里最新两期
    python3 scripts/diff.py old.html new.html

关于「重评」的口径：综合分变化 < 0.5 的多半只是归一化漂移（榜单每次
抓取会重算 combined 的百分位），只有 > 0.5 才视为模型真的被重新评分。
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_snapshot, num, spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIFT = 0.5          # 小于此值视为归一化漂移
TRIVIAL = 0.05       # 小于此值视为完全没动


def pick_last_two():
    files = sorted(glob.glob(os.path.join(ROOT, 'archive', '*.html')))
    if len(files) < 2:
        sys.exit('archive/ 里不足两期快照，先跑 scripts/fetch.py')
    return files[-2], files[-1]


def line(x, delta=None):
    d = f'{delta:+6.1f}' if delta is not None else '     —'
    return (f"#{num(x, 'rank'):>4} 综{num(x, 'combined_v3'):5.1f}±{num(x, 'combined_se_v3'):4.2f} "
            f"Δ{d} CW{num(x, 'cw_score_v3'):5.1f} RP{num(x, 'rp_score_v3'):5.1f} "
            f"ERP{num(x, 'erp_score_v3'):5.1f} DRP{num(x, 'drp_score_v3'):5.1f} "
            f"错{num(x, 'literal_combo_v3'):4.1f} slop{num(x, 'slop_combo_v3'):4.1f} "
            f"{spec(x):>12}  {x['display_name'][:44]}")


def main():
    old_p, new_p = (sys.argv[1], sys.argv[2]) if len(sys.argv) >= 3 else pick_last_two()
    ts_old, old = load_snapshot(old_p)
    ts_new, new = load_snapshot(new_p)
    o = {x['slug']: x for x in old}
    n = {x['slug']: x for x in new}

    print(f'旧 {ts_old}  {len(old)} 个   →   新 {ts_new}  {len(new)} 个')

    added = [n[s] for s in n if s not in o]
    removed = [o[s] for s in o if s not in n]
    if added:
        print(f'\n== 新增 {len(added)} 个 ==')
        for x in sorted(added, key=lambda y: -num(y, 'combined_v3')):
            print(line(x))
    if removed:
        print(f'\n== 消失 {len(removed)} 个 ==')
        for x in sorted(removed, key=lambda y: -num(y, 'combined_v3')):
            print(line(x))

    changed, repriced = [], []
    for s in n:
        if s not in o:
            continue
        d = num(n[s], 'combined_v3') - num(o[s], 'combined_v3')
        if abs(d) >= TRIVIAL:
            changed.append((d, n[s]))
            if abs(d) >= DRIFT:
                repriced.append((d, n[s]))

    print(f'\n== 分数变动 {len(changed)} 个（其中真重评 {len(repriced)} 个 ≥{DRIFT}）==')
    for d, x in sorted(repriced, key=lambda t: -abs(t[0]))[:30]:
        print(line(x, d))
    if not repriced:
        print('  （无：纯增量更新，旧模型一个没动）')


if __name__ == '__main__':
    main()

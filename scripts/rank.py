#!/usr/bin/env python3
"""按指定指标排行。默认输出 ≤40B 开源模型的综合前 10。

用法：
    python3 scripts/rank.py                              # ≤40B 综合前 10
    python3 scripts/rank.py --key erp_score_v3           # 按 NSFW 能力分
    python3 scripts/rank.py --key drp_score_v3 --top 5   # 按暗黑分
    python3 scripts/rank.py --moe                        # 只看 ≤40B MoE
    python3 scripts/rank.py --under 12                   # 只看 ≤12B
    python3 scripts/rank.py --all                        # 不限参数量（含闭源、大模型）
    python3 scripts/rank.py --key slop_combo_v3 --asc    # slop 从低到高
    python3 scripts/rank.py archive/xxx.html ...         # 指定快照

指标字段（v3，默认视图）：
    combined_v3   综合      cw_score_v3  创意写作
    rp_score_v3   角色扮演   erp_score_v3 露骨内容能力（0–100，越高越会写）
    drp_score_v3  暗黑       slop_combo_v3 AI 腔（越低越干净）
    literal_combo_v3 错误    darkness_v3  暗黑投递比   nsfw_v3 露骨投递比
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import is_moe, load_snapshot, num, spec, table

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ['combined_v3', 'cw_score_v3', 'rp_score_v3', 'erp_score_v3',
        'drp_score_v3', 'slop_combo_v3', 'literal_combo_v3']


def latest():
    files = sorted(glob.glob(os.path.join(ROOT, 'archive', '*.html')))
    if not files:
        sys.exit('archive/ 为空，先跑 scripts/fetch.py')
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('snapshot', nargs='?', default=None)
    ap.add_argument('--key', default='combined_v3', choices=KEYS)
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--under', type=float, default=40)
    ap.add_argument('--moe', action='store_true', help='只保留 MoE')
    ap.add_argument('--dense', action='store_true', help='只保留稠密')
    ap.add_argument('--all', action='store_true', help='不限参数量、含闭源')
    ap.add_argument('--asc', action='store_true', help='从小到大（slop/错误 用）')
    ap.add_argument('--md', action='store_true', help='输出 Markdown 表格')
    a = ap.parse_args()

    path = a.snapshot or latest()
    ts, models = load_snapshot(path)

    pool = models
    if not a.all:
        pool = [x for x in pool if x.get('model_class') != 'Proprietary'
                and num(x, 'parameter_count_b', 99) <= a.under
                and x.get('evaluation_tier') == 1.0]
    if a.moe:
        pool = [x for x in pool if is_moe(x)]
    if a.dense:
        pool = [x for x in pool if not is_moe(x)]

    pool.sort(key=lambda x: num(x, a.key), reverse=not a.asc)
    rows = [(i, f"{num(x, a.key):.1f}", f"±{num(x, 'combined_se_v3'):.2f}",
             f"{num(x, 'nsfw_v3'):.2f}", f"{num(x, 'rp_score_v3'):.1f}",
             f"{num(x, 'erp_score_v3'):.1f}", f"{num(x, 'drp_score_v3'):.1f}",
             f"{num(x, 'slop_combo_v3'):.1f}", spec(x), x['display_name'][:44])
            for i, x in enumerate(pool[:a.top], 1)]

    scope = '全部' if a.all else f'≤{a.under:g}B'
    scope += ' MoE' if a.moe else (' 稠密' if a.dense else '')
    print(f'# {ts} UTC · {scope} · 按 {a.key} {"升序" if a.asc else "降序"} · 共 {len(pool)} 个\n')
    if a.md:
        print(table(rows, ['#', a.key, '±', 'nsfw', 'RP', 'ERP', 'DRP', 'slop', '规格', '模型']))
    else:
        for r in rows:
            print(f"{r[0]:>3}. {r[1]:>5} {r[2]:>6} nsfw{r[3]} RP{r[4]:>5} ERP{r[5]:>5} "
                  f"DRP{r[6]:>5} slop{r[7]:>5} {r[8]:>12}  {r[9]}")


if __name__ == '__main__':
    main()

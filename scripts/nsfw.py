#!/usr/bin/env python3
"""导出全榜的 NSFW 数据，两种排序各一张表。

    python3 scripts/nsfw.py > docs/nsfw-full.md

⚠️ 两个字段含义完全不同，别混用：

    nsfw_v3   内容投递比（不是分数）。>1 = 比要求更露骨，1 = 按要求，
              <1 = 会净化。全站范围约 0.57–1.78，中位 ~0.92。
              它只描述语气倾向，**不计入综合分**。

    erp_score_v3  露骨内容能力分（0–100）。**这个才是「会不会写」的指标**，
                  中位约 41.6，p90 约 61.6。

投递比高 ≠ 会写：前排被一堆 RP 归零的模型占着，它们只是「不管你要不要
都硬塞」。选模型请看 ERP。
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_snapshot, num, spec, table

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = ['#', '排序值', 'nsfw比', 'ERP', '暗黑比', 'RP', 'DRP', '综合', '±', '规格', '模型']


def latest():
    files = sorted(glob.glob(os.path.join(ROOT, 'archive', '*.html')))
    if not files:
        sys.exit('archive/ 为空，先跑 scripts/fetch.py')
    return files[-1]


def rows(models, key):
    out = []
    for i, x in enumerate(sorted(models, key=lambda y: -num(y, key)), 1):
        out.append((i, f"{num(x, key):.2f}", f"{num(x, 'nsfw_v3'):.2f}",
                    f"{num(x, 'erp_score_v3'):.1f}", f"{num(x, 'darkness_v3'):.2f}",
                    f"{num(x, 'rp_score_v3'):.1f}", f"{num(x, 'drp_score_v3'):.1f}",
                    f"{num(x, 'combined_v3'):.1f}", f"{num(x, 'combined_se_v3'):.2f}",
                    spec(x), x['display_name'][:44]))
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else latest()
    ts, models = load_snapshot(path)
    vals = sorted(num(x, 'nsfw_v3') for x in models)
    erp = sorted(num(x, 'erp_score_v3') for x in models)
    n = len(vals)

    print(f'# Caliper Bench · NSFW 数据全表\n')
    print(f'快照 {ts} UTC · 共 {n} 个模型\n')
    print('## 字段说明\n')
    print('- **nsfw比**：内容投递比。>1.0 比要求更露骨 / 1.0 按要求 / <1.0 会净化。'
          f'范围 {vals[0]:.2f}–{vals[-1]:.2f}，中位 {vals[n // 2]:.2f}。**不计入综合分**。')
    print(f'- **ERP**：露骨内容能力分（0–100）。中位 {erp[n // 2]:.1f}，'
          f'p90 {erp[int(n * .9)]:.1f}，最高 {erp[-1]:.1f}。**选模型看这个**。')
    print('- **暗黑比**：darkness_v3，同投递比口径的暗黑内容版本。\n')
    print('---\n')
    print('## A. 按 nsfw 投递比降序\n')
    print(table(rows(models, 'nsfw_v3'), HDR))
    print('\n## B. 按 ERP 能力分降序\n')
    print(table(rows(models, 'erp_score_v3'), HDR))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""GitHub Actions 用的单次更新流程。

1. 抓当前榜单 → archive/（不入库，由 workflow 上传为 artifact）
2. 压缩成 data/state.json.gz（约 40 KB，入库）
3. 与上一份 state 对比，有变化就写 docs/diffs/<stamp>.md 并追加到 docs/changelog-auto.md
4. 维护 data/last_check.json 心跳（防止仓库 60 天无活动导致定时任务被停）

输出最后一行 `CHANGED=0|1`，由 workflow 决定是否提交。
"""
import datetime
import gzip
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from fetch import fetch  # noqa: E402
from state import build, diff, load_state, save_state  # noqa: E402

STATE = os.path.join(ROOT, 'data', 'state.json.gz')
CHECK = os.path.join(ROOT, 'data', 'last_check.json')
DIFFDIR = os.path.join(ROOT, 'docs', 'diffs')
AUTO = os.path.join(ROOT, 'docs', 'changelog-auto.md')
HEARTBEAT_DAYS = 7


def sh(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def save_html(html, stamp):
    d = os.path.join(ROOT, 'archive')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, stamp + '.html')
    if os.path.exists(path):
        old = open(path, 'rb').read()
        if len(old) > len(html):
            # 同期已有更完整的归档，保留它，后续从它构建状态
            print(f'保留更完整的归档 {path}（{len(old) / 1e6:.2f} MB）')
            return path
    with open(path, 'wb') as f:
        f.write(html)
    return path


def main():
    # CI 调试用：指定本地快照可跳过网络
    local = os.environ.get('CALIPER_LOCAL_SNAPSHOT')
    if local:
        html = open(local, 'rb').read()
        print(f'使用本地快照 {local}')
    else:
        html = fetch('https://caliperbench.com/')
    text = html.decode('utf-8', 'ignore')
    m = re.search(r'generated (\d{4}-\d\d-\d\d \d\d:\d\d) UTC', text)
    stamp = (m.group(1) if m else 'unknown').replace(' ', '_').replace(':', '')
    path = save_html(html, stamp)
    print(f'快照 {stamp}  {len(html) / 1e6:.1f} MB → {path}')

    new = build(path)
    old = load_state(STATE) if os.path.exists(STATE) else None

    # stamp 前进就说明站点出过新一期，无论分数是否变动都必须把新状态入库，
    # 否则下一次会拿更早的基线做对比，报出来的「增量」会累积成跨期值。
    stamp_advanced = old is None or old.get('generated') != new['generated']

    if not stamp_advanced:
        print(f"页面未更新（仍是 {new['generated']}），跳过")
        changed = False
    else:
        report = diff(old, new) if old else \
            f"首次建立状态：{new['count']} 个模型，快照 {new['generated']}"
        os.makedirs(DIFFDIR, exist_ok=True)
        with open(os.path.join(DIFFDIR, stamp + '.md'), 'w', encoding='utf-8') as f:
            f.write(f'# {stamp}\n\n{report}\n')
        print(report)
        changed = bool(
            set(new['models']) ^ set(old['models'])
            or any(abs(new['models'][s]['combined_v3'] - old['models'][s]['combined_v3']) >= 0.5
                   for s in new['models'] if s in old['models'])) if old else True
        if old:
            note = (f"{new['count'] - old['count']:+d} 个模型　{old['count']} → {new['count']}"
                    if changed else f"{new['count']} 个模型　仅归一化漂移，无实质变动")
            with open(AUTO, 'a', encoding='utf-8') as f:
                f.write(f"\n## {stamp}\n\n{note}\n")

    save_state(new, STATE)
    with open(CHECK, 'w', encoding='utf-8') as f:
        json.dump({'generated': new['generated'], 'count': new['count'],
                   'checked_at': datetime.datetime.now(datetime.timezone.utc)
                   .strftime('%Y-%m-%dT%H:%M:%SZ')}, f, ensure_ascii=False)

    # 无变化时，最多每 7 天提交一次心跳，避免定时任务因仓库不活跃被 GitHub 停掉
    commit = stamp_advanced
    if not commit:
        last = sh('git', 'log', '-1', '--format=%ct', '--', 'data/last_check.json')
        days = 999
        if last.isdigit():
            days = (datetime.datetime.now().timestamp() - int(last)) / 86400
        commit = days >= HEARTBEAT_DAYS

    print(f'CHANGED={1 if commit else 0}')


if __name__ == '__main__':
    main()

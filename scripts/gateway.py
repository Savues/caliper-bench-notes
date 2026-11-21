#!/usr/bin/env python3
"""把一个 OpenAI 兼容网关的模型列表，对照排行榜评分。

    export CALIPER_GW_BASE=http://your-host:port/v1
    export CALIPER_GW_KEY=your-key
    python3 scripts/gateway.py            # 按 ERP 排序
    python3 scripts/gateway.py --key rp_score_v3

只读取 /v1/models，不发起任何推理请求。

⚠️ 匹配的坑：网关里很多 ID（`*/free`、`@cf/*`、带 provider 前缀的）指向
**官方基座**，而榜单上同名的往往是**社区越狱微调版**，分数会虚高几十分。
RULES 里已按「官方基座」校正，遇到新 ID 请照此原则补充，不要图省事用模糊
匹配，否则会把 Heretic/Uncensored 版的分数安到官方模型头上。
"""
import argparse
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_snapshot, num, spec, table

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 网关 ID 正则 -> 榜单 display_name 正则（None = 该模型榜单上无对应官方条目）
RULES = [
    (r'deepseek-v4-pro',                        r'DeepSeek V4 Pro 0813$'),
    (r'^DeepSeek-V4-Flash$|/deepseek-v4-flash$|^deepseek-v4-flash$|0731free',
                                                r'DeepSeek V4 Flash 2026-07-01 snapshot \(DeepSeek'),
    (r'v4\.1-flash|DeepSeek-V4\.1-Flash',       r'DeepSeek V4\.1 Flash 1017 \(DeepSeek'),
    (r'^deepseek-3\.2$|kiro/deepseek-3\.2',     r'DeepSeek V3\.2 Thinking'),
    (r'gemini-4-argon',                         r'Gemini 4 Argon$'),
    (r'glm-5\.3-flash',                         r'GLM-5\.3 Flash Thinking \(ZAI'),
    (r'glm-5\.2',                               r'GLM-5\.2 Thinking'),
    (r'^glm-5$',                                r'GLM-5 \('),
    (r'claude-sonnet-5-5',                      r'Claude Sonnet 5\.5 \(Anthropic\)'),
    (r'claude-opus-5-5',                        r'Claude Opus 5\.5 \(Anthropic\)'),
    (r'claude-sonnet-4\.5',                     r'Claude Sonnet 4\.6 \(Anthropic\)'),
    (r'claude-haiku-4\.5',                      r'Claude Haiku 5\.5 \(Anthropic\)'),
    (r'gpt-6\.1-sol',                           r'GPT-6\.1 Sol \(OpenAI'),
    (r'gpt-6\.1-terra',                         r'GPT-6\.1 Terra \(OpenAI'),
    (r'gpt-6-astra',                            r'GPT-6 Astra \(OpenAI'),
    (r'^gpt-6-sol$',                            r'GPT-6 Sol \(OpenAI'),
    (r'^gpt-6-luna$|codex/gpt-6-luna',          r'GPT-6 Luna \(OpenAI'),
    (r'gpt-5\.6-luna',                          r'GPT-5\.6 Luna Pro \(OpenAI'),
    (r'gpt-5\.6-terra',                         r'GPT-5\.6 Terra Pro \(OpenAI'),
    (r'gpt-5\.6-sol',                           r'GPT-5\.6 Sol Pro \(OpenAI'),
    (r'nemotron-3-ultra',                       r'Nemotron-3 Ultra 550B-A55B \(NVIDIA\)'),
    (r'nemotron-3\.5-super-vl',                 r'Nemotron 3\.5 Super VL 120B-A12B \(NVIDIA\)'),
    (r'nemotron-3\.5-lightning',                r'Nemotron 3\.5 Lightning 30B-A3B \(NVIDIA\)'),
    (r'minimax-m3\.1',                          r'MiniMax M3\.1 Flash Preview Thinking'),
    (r'minimax-m2\.5',                          r'MiniMax m2\.7 Thinking'),
    (r'mimo-v2\.6|MiMo-V2\.6',                  r'MiMo V2\.6 Flash \(Xiaomi\)'),
    (r'step-5-preview|stepfun',                 r'StepFun Step 3\.7 Flash'),
    (r'beam-free',                              r'Beam 1\.0'),
    (r'inkling-2-small',                        r'Inkling 975B'),
    (r'ling-3\.2',                              r'Ling 3\.1 Flash Thinking'),
    (r'longcat-2\.5',                           r'Longcat'),
    (r'ernie-5\.5',                             r'Ernie'),
    (r'exaone',                                 r'Exaone'),
    (r'particle-1',                             r'Particle'),
    (r'sensenova-6-8-flash-lite',               r'SenseNova'),
    (r'sensenova',                              r'SenseNova'),
    (r'sea-lion',                               r'Sea Lion'),
    (r'qwq-32b',                                r'QwQ'),
    (r'qwen3-30b-a3b',                          r'Qwen3 30B'),
    (r'qwen3\.8-27b',                           r'Qwen3\.8 27B Base Thinking \(Alibaba'),
    (r'gemma-4-26b-a4b',                        r'Gemma-4 26B-A4B Base \(google\)'),
    (r'gpt-oss-120b',                           r'gpt oss 120B'),
    (r'gpt-oss-20b',                            r'gpt oss 20B'),
    (r'llama-4-scout',                          r'Llama 4 Scout'),
    (r'llama-3\.3-70b',                         None),   # 只有越狱微调版在榜
    (r'mistral-small-3\.1-24b',                 r'Mistral Small 3\.1 24B Instruct'),
    (r'granite',                                r'Granite 4\.2 30B \(IBM\)'),
]


def get_models(base, key):
    req = urllib.request.Request(base.rstrip('/') + '/models',
                                 headers={'Authorization': 'Bearer ' + key})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    return sorted({m['id'] for m in payload.get('data', [])})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', default='erp_score_v3')
    ap.add_argument('--snapshot', default=None)
    a = ap.parse_args()

    base = os.environ.get('CALIPER_GW_BASE')
    key = os.environ.get('CALIPER_GW_KEY')
    if not base or not key:
        sys.exit('请先设置 CALIPER_GW_BASE 和 CALIPER_GW_KEY 环境变量')

    files = sorted(__import__('glob').glob(os.path.join(ROOT, 'archive', '*.html')))
    if not files:
        sys.exit('archive/ 为空，先跑 scripts/fetch.py')
    ts, models = load_snapshot(a.snapshot or files[-1])

    ids = get_models(base, key)
    matched, seen, unmatched = [], set(), []
    for gid in ids:
        hit = None
        for gpat, lpat in RULES:
            if not re.search(gpat, gid, re.I):
                continue
            if lpat is None:
                unmatched.append((gid, '榜单无官方条目'))
                hit = 'skip'
                break
            cands = [x for x in models if re.search(lpat, x['display_name'], re.I)]
            if cands:
                hit = max(cands, key=lambda y: num(y, 'combined_v3'))
            else:
                unmatched.append((gid, '未匹配'))
                hit = 'skip'
            break
        if hit == 'skip':
            continue
        if hit is None:
            unmatched.append((gid, '未匹配'))
            continue
        if hit['slug'] in seen:
            continue
        seen.add(hit['slug'])
        matched.append((gid, hit))

    matched.sort(key=lambda t: -num(t[1], a.key))
    rows = [(f"{num(x, a.key):.1f}", f"{num(x, 'nsfw_v3'):.2f}",
             f"{num(x, 'rp_score_v3'):.1f}", f"{num(x, 'erp_score_v3'):.1f}",
             f"{num(x, 'drp_score_v3'):.1f}", f"{num(x, 'combined_v3'):.1f}",
             f"±{num(x, 'combined_se_v3'):.2f}", spec(x),
             x['display_name'][:36], gid) for gid, x in matched]

    print(f'# 网关 {len(ids)} 个 ID → 匹配 {len(matched)} 个榜单模型（快照 {ts} UTC）\n')
    print(table(rows, [a.key, 'nsfw', 'RP', 'ERP', 'DRP', '综合', '±', '规格', '榜单模型', '网关 ID']))
    if unmatched:
        print(f'\n## 未匹配 {len(unmatched)} 个\n')
        for gid, why in unmatched:
            print(f'- `{gid}` — {why}')


if __name__ == '__main__':
    main()

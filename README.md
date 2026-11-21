# Caliper Bench 笔记

[Caliper Bench](https://caliperbench.com/) 是一个针对创意写作与角色扮演的 LLM 排行榜。本仓库存放历次快照的差分记录、可复用的稳定结论，以及把榜单数据拉出来做分析的脚本。

当前快照 **912 个模型**（2026-11-21 页面标注时间），本地留有 11 期历史快照。

## 目录

| 路径 | 内容 |
|---|---|
| `scripts/` | 抓取、差分、排行、NSFW 导出、网关对照 |
| `docs/结论速查.md` | 按用途分类的选型结论（持续更新） |
| `docs/changelog.md` | 每期快照变化记录 |
| `docs/字段说明.md` | 榜单列的含义与坑 |
| `archive/` | 历史快照（不入库，见下） |

## 快速开始

```sh
python3 scripts/fetch.py                              # 抓最新一期到 archive/
python3 scripts/diff.py                               # 最近两期差分
python3 scripts/rank.py --top 10                      # ≤40B 综合前 10
python3 scripts/rank.py --key erp_score_v3 --top 10   # 按 NSFW 能力分
python3 scripts/rank.py --moe --under 40              # ≤40B MoE
python3 scripts/nsfw.py > docs/nsfw-full.md           # 全榜 NSFW 双表
```

网关对照需要环境变量，仓库里不含任何地址或密钥：

```sh
export CALIPER_GW_BASE=http://your-host:port/v1
export CALIPER_GW_KEY=your-key
python3 scripts/gateway.py --key erp_score_v3
```

## 五个必须知道的坑

| 坑 | 说明 |
|---|---|
| `rank` 是 CW 排名 | 总榜名次按创意写作分排，不是综合分。按 `rank` 读实力会误判（曾有综合 32.9 的模型排第 3） |
| `nsfw_v3` 不是分数 | 它是内容投递比：>1 比要求更露骨，1 按要求，<1 会净化。范围 0.57–1.78，不计入综合分 |
| `slop` 低不等于写得好 | 只测套路程度（850 条规则库），不测质量。最低的几个模型 RP 只有 20 上下 |
| 社区微调版分数虚高 | 榜单上同名条目常是 Heretic/Uncensored 微调；网关或官方 API 给的是基座，实际差几十分 |
| 时间戳有偏移 | 站点 `generated` 曾观测到比真实 UTC 超前约 19 小时，只用于排序 |

细节见 [docs/字段说明.md](docs/字段说明.md)。

## 脚本设计要点

榜单把全部数据内嵌成 HTML 里的 `const DATA = [...]`，解析必须用字符串感知的扫描（`scripts/lib.py` 的 `load_snapshot`），直接数括号会因转义引号失败。

`diff.py` 把综合分变化分两档：`< 0.5` 视为归一化漂移（每次抓取重算 combined 百分位造成），`≥ 0.5` 才算模型真被重新评分。历次更新里绝大多数是前者。

## 关于快照

`archive/*.html` 每期约 3.4 MB，不入库。本地需要历史对比时先自己抓：

```sh
for i in 1 2 3; do python3 scripts/fetch.py; sleep 3600; done
```

早期 11 期快照的模型数如下，可作为回填参照：

| 页面标注时间 (UTC) | 模型数 | 增量 |
|---|---|---|
| 2026-11-04 08:06 | 792 | — |
| 2026-11-06 07:51 | 809 | +17 |
| 2026-11-07 15:31 | 823 | +14 |
| 2026-11-08 17:20 | 831 | +8 |
| 2026-11-13 05:20 | 862 | +31 |
| 2026-11-14 04:22 | 871 | +9 |
| 2026-11-16 00:48 | 879 | +8 |
| 2026-11-16 18:11 | 882 | +3 |
| 2026-11-18 02:35 | 894 | +12 |
| 2026-11-19 09:08 | 903 | +9 |
| 2026-11-21 09:26 | 912 | +9 |

## 授权

脚本为分析工具，榜单数据版权归 Caliper Bench。
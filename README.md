<div align="center">

# 🎬 video-engine

**Agent 当导演和剪辑师，而且每一刀都有理由**

实拍为主的短视频生产插件：分镜 → AI 参考片 → 对照拍摄 → 可审计精剪 → 剪映草稿 + 成片

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Skills](https://img.shields.io/badge/Agent_Skills-open_standard-purple.svg)](https://github.com/anthropics/skills)
[![Base](https://img.shields.io/badge/base-VectCutAPI-orange.svg)](https://github.com/sun-guannan/VectCutAPI)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/xinzhuwang-wxz/video-engine/pulls)

**中文** | [English](README_EN.md)

<img src="assets/demo.gif" width="240" alt="15s 唯美卡点 demo:分镜/previz/剪辑全部由 agent 完成">

*↑ 这条 15 秒卡点片的分镜、AI 参考片、剪辑决策全部由 agent 完成，人只点了三次头，花费 ¥6*

</div>

---

## 这是什么

传统短视频生产：文字脚本 → 靠想象拍 → 剪辑师在几十分钟素材里捞点 → 反复返工。

video-engine 把它重塑为——

```
📝 分镜(人过目) → 🎞 AI 参考片("会动的拍摄标准") → 📷 人对照拍摄
→ ✂️ agent 精剪(每刀带理由,自己看自己改) → 🎬 剪映草稿 + 成片(人确认发布)
```

人在整条链上只做三件事：**过目分镜、拍摄、发布前确认**。

**核心信念：AI 剪的片必须可以被人审阅、质疑和复现。** 所以剪辑决策不藏在魔法里——它是一份叫**剪单（cutlist）**的 JSON，每一刀都写着为什么。

## ✨ 能力（纯能力，不构成固定流水线）

三个决策技能（SKILL.md 开放标准，Claude Code / Codex / Hermes / OpenClaw 通用）：

| 技能 | 会做什么 | 最少需要什么 |
|---|---|---|
| `video-storyboard` | 写专业分镜：景别/运镜/旁白/节拍网格，含宣称合规闸与同质化检测 | 一句主旨 |
| `video-previz` | 逐段生成 AI 参考视频（Seedance，`SEEDANCE_MODEL` 可换任意模型；480p 参考级省钱） | 每段一句画面描述 |
| `video-editing` | 出剪单 → 带手艺的剪映草稿（转场/滤镜/关键帧/BGM/字幕）+ ffmpeg 直出成片 | 素材（连意图都可以缺） |

**入口无关，按手头有什么开工**：想法先行、素材先行、AI/实拍混剪，都只是编排组合，由 agent 现场决定；分镜、参考片、命名规约全部是"可选先验——有则增质，缺则降级自建"。

引擎脚本（stdlib + ffmpeg，均可独立使用）：

```
doctor.py     环境体检(开工前,失败早暴露)     status.py     工作台探针(有什么/缺什么/下一步/花费/停滞)
validate_cutlist.py 剪单校验(+--probe 素材深校验)  promise_check.py 交付承诺门(分镜↔剪单对账)
beat_align.py 重音对齐(切点吸真实鼓点)          seedance_gen.py 生成(断点续跑/绕代理/成本可算)
cutlist_to_vectcut.py 物化剪映草稿(全手艺)      render_cutlist.py / produce_cutlist.py ffmpeg出片(一键:验→对齐→渲→收尾→报告)
```

## 🚦 四道质量门（可对账是灵魂）

```
① 分镜校验闸                ② 素材深校验(--probe)         ③ 交付承诺门                ④ 自审回环
宣称合规/结构完整/           ffprobe 逐素材验可读/          分镜=承诺,剪单=交付:         agent 渲预览→抽帧亲眼看→
同质化检测(空泛prompt        时长/流,坏料别进渲染           段覆盖/时长契约/字幕承诺,     对照分镜改剪单,≤3轮
在花钱前被抓)                                              幻灯片感风险提示
```

每道门可显式关闭、有正反用例焊在回归里。实测战绩：自审回环抓过"切掉关键眼神帧"和"转场挂错位"；同质化检测对真实分镜零误报。

## 🧾 剪单长什么样（本项目的灵魂概念）

```json
{ "seq": 8,
  "main": {"file": ".../S08.mp4", "in": 1.8, "out": 3.8, "transition": "叠化"},
  "subtitle": "回头那一眼,是江南",
  "rationale": "自审R1:原窗0.2-2.2s裁掉了抬头瞬间;实测3.5s处才是眼神交流帧,改取1.8-3.8s" }
```

## 🚀 快速开始

```bash
git clone https://github.com/xinzhuwang-wxz/video-engine.git && cd video-engine
bash setup.sh     # 克隆基座 → 打补丁 → 建环境 → 体检 → 冒烟
make demo         # 零 key 演示:20 秒看完整产线(校验→渲染→硬字幕/柔光/闪白→报告)
```

然后对你的 agent 说人话：

> "素材在 ~/Desktop/素材，剪个 15 秒发抖音，唯美一点，配古风音乐"

生成能力需要在 `.env` 填 `ARK_API_KEY`（火山方舟）；**纯剪辑零 key 可用**。
剪映草稿出口需起引擎：`make server`（:9001）。

## 🤖 接入你的 Agent

| Agent | 接入方式 |
|---|---|
| **Claude Code** | 直接打开本仓库，或 `ln -s $PWD/skills/* ~/.claude/skills/` |
| **Codex** | 仓库内直接可用（读 `AGENT.md`/`CODEX.md`），或 skills 放入 `~/.codex/skills` |
| **Hermes** | `ln -s $PWD/skills/* ~/.hermes/skills/` |
| **OpenClaw / 其它** | 凡支持 SKILL.md 标准的，挂进其技能目录即可 |

操作手册：[`AGENT.md`](AGENT.md) · 直接可抄的提示词：[`PROMPT_GALLERY.md`](PROMPT_GALLERY.md)

## 🎬 实测战绩

| Demo | 内容 | 花费 | 人的参与 |
|---|---|---|---|
| 全 AI 参考片 | 9 镜分镜 → 24s 参考成片，自审回环修 2 处人眼级问题 | ¥17.6 | 0 |
| 实拍+AI 混剪 | 5 条 4K → 15s 抖音卡点：AI 元素 17%、清澈滤镜、叠化×4、重音对齐、旁白字幕 | ¥6.0 | 3 次点头 |

成本全程可对账：`status.py` 一屏显示这条笔记花了多少钱，生产报告自带 tokens→¥ 快照。

## 🆚 与 OpenMontage 的关系

[OpenMontage](https://github.com/calesthio/OpenMontage)（33k★，AGPL）是出色的**生成式**视频生产系统，也是本项目多个机制的思想来源（preflight/状态看板/交付承诺门/同质化检测——均为原创重实现，无代码迁移）。定位差异：

- **它强在**：生成式/解说式内容、免费素材检索、Remotion 动效、12 条现成管线
- **我们强在**：实拍素材的可审计剪辑、剪映生态出口（人可精修+曲库+中文平台规格）、宣称合规与发布红线、Apache-2.0 商用友好、轻依赖

做英文生成式内容选它；做中文实拍品牌短视频、要人审可控、要商用集成，选这里。

## 🔒 设计红线

绝不自动发布 · 原素材只读 · 默认本地零外发（云预览是显式 opt-in）· 烧钱前分镜必须给人过目 · 每个剪辑决策必须带 rationale · AI 内容按平台要求声明

## 🧯 FAQ

- **先跑什么？** `make doctor`——环境体检会告诉你缺什么、怎么补、哪些是可降级的可选项
- **剪映打不开草稿？** `vendor/CapCutAPI/config.json` 的 `draft_profile` 按剪映版本选（10.x 用 `jianying_pro_10`）
- **生成报 duration 无效？** Seedance mini 时长下限 4s——策略是"生成留余量，剪单裁精确"，1s 快切照样支持
- **本机挂代理生成失败？** 已内置绕代理直连+退避重试+断点续跑，单段失败不拖死整批
- **字幕没烧进画面？** 无 libass 时自动切 Pillow PNG 硬字幕（无需重装 ffmpeg）

## 🛣️ Roadmap

- [ ] TTS 旁白配音进管线（目前配音留给剪映"文本朗读"一键）
- [ ] 免费素材检索（开放素材库索引，科普类内容的 B 线）
- [ ] 云预览通路（自有 OSS，网页看时间线）
- [ ] 成片级 AI 段工作流（1080p 生成+审帧）
- [ ] DaVinci Resolve 物化器（专业调色场景）

## 🙏 致谢

[VectCutAPI](https://github.com/sun-guannan/VectCutAPI)（剪辑执行基座）· [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)（草稿格式层）· [OpenMontage](https://github.com/calesthio/OpenMontage)（多项机制的思想启发）· Seedance / 火山方舟（生成）

## 📄 License

[Apache-2.0](LICENSE)（与上游基座一致）

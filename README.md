<div align="center">

# 🎬 video-engine

**让 Agent 当导演和剪辑师：一句想法 → 分镜 → AI 参考片 → 对照拍摄 → 自动精剪成片**

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Skills](https://img.shields.io/badge/Agent_Skills-open_standard-purple.svg)](https://github.com/anthropics/skills)
[![Base](https://img.shields.io/badge/base-VectCutAPI-orange.svg)](https://github.com/sun-guannan/VectCutAPI)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/xinzhuwang-wxz/video-engine/pulls)

**中文** | [English](README_EN.md)

<img src="assets/demo.gif" width="240" alt="15s 唯美卡点 demo:分镜/previz/剪辑全部由 agent 完成">

*↑ 这条 15 秒卡点片的分镜、AI 参考片、剪辑决策全部由 agent 完成,人只点了三次头*

</div>

---

## 这是什么

传统短视频生产:文字脚本 → 靠想象拍 → 剪辑师在几十分钟素材里捞点 → 反复返工。
**video-engine 把流程重塑为**:

```
想法/素材 → 📝 分镜(人过目) → 🎞 AI 参考片(previz,"会动的拍摄标准")
         → 📷 人对照拍摄 → ✂️ agent 自动精剪(自审回环) → 🎬 剪映草稿+成片(人确认发布)
```

人在整条流水线上只做三件事:**过目分镜、拍摄、发布前确认**。

## ✨ 功能特性

- 🧠 **三个决策技能**(SKILL.md 开放标准,跨 agent 通用)
  - `video-storyboard`:一句想法 → 专业分镜(景别/运镜/旁白/节拍网格,含宣称合规闸)
  - `video-previz`:分镜 → 逐段 AI 参考视频(Seedance,模型可换;480p 参考级省钱)
  - `video-editing`:素材+意图 → 剪单 → 带手艺的剪映草稿(转场/滤镜/关键帧/BGM/字幕)
- 🧾 **剪单契约(cutlist)**:agent 的每一刀都是 JSON 里的一条决策,**必须带 rationale**——可人审、可复现、可追溯
- 👀 **自审回环**:agent 渲低清预览 → 抽帧亲眼看 → 发现问题改剪单重渲(≤3 轮);实测抓住过"切掉关键眼神"和"转场挂错位"这类人眼级问题
- 🥁 **重音对齐**:检测 BGM 真实能量峰,切点吸附真实重音(理论 BPM 网格会骗人)
- 🎨 **风格白名单**:引擎 362 转场/468 滤镜机器 dump 成枚举表,agent 永远不会幻觉出不存在的滤镜名;选型靠判断规则,不写死审美
- 🔀 **双出口**:剪映草稿(人微调+导出,全手艺)/ ffmpeg 直出(无人值守粗版)
- ♻️ **工作区制度**:`01-原始拍摄|02-AI生成|03-成片|04-工作台`,存在即状态、manifest 留痕、素材复用查表即得
- 🤝 **不造轮子**:剪辑执行 100% 走开源基座 [VectCutAPI](https://github.com/sun-guannan/VectCutAPI)(2k★),本仓库只做基座没有的决策层

## 🔒 设计红线

绝不自动发布 · 原素材只读 · 默认本地零外发(云预览是显式 opt-in) · 烧钱前分镜必须给人过目 · AI 内容按平台要求声明

## 🚀 快速开始

```bash
git clone https://github.com/xinzhuwang-wxz/video-engine.git && cd video-engine
bash setup.sh        # 克隆基座 → 打补丁 → 建环境 → 冒烟自检
cp .env.example .env # 填 ARK_API_KEY(只有"生成"需要;纯剪辑不用)
cd vendor/CapCutAPI && .venv/bin/python capcut_server.py &   # 起剪辑引擎 :9001
```

然后对你的 agent 说人话即可:

> "素材在 ~/Desktop/素材,剪个 15 秒发抖音,唯美一点,配古风音乐"

## 🤖 接入你的 Agent

| Agent | 接入方式 |
|---|---|
| **Claude Code** | `ln -s $PWD/skills/* ~/.claude/skills/`,或直接打开本仓库 |
| **Codex** | 仓库内直接可用(读 `AGENT.md`);或 skills 放入 `~/.codex/skills` |
| **Hermes** | `ln -s $PWD/skills/* ~/.hermes/skills/` |
| **OpenClaw / 其它** | 凡支持 SKILL.md 标准的,挂进其技能目录即可 |

Agent 侧完整操作手册见 [`AGENT.md`](AGENT.md)。

## 🧾 剪单长什么样(本项目的灵魂概念)

```json
{ "seq": 8,
  "main": {"file": ".../S08.mp4", "in": 1.8, "out": 3.8, "transition": "叠化"},
  "subtitle": "回头那一眼,是江南",
  "rationale": "自审R1:原窗0.2-2.2s裁掉了抬头瞬间;实测3.5s处才是眼神交流帧,改取1.8-3.8s" }
```

每个字段都是决策,每个决策都有理由——这让"AI 剪的片"变成可以被人类审阅、质疑和改进的东西。

## 🎬 实测战绩

| Demo | 内容 | 花费 | 人的参与 |
|---|---|---|---|
| 全 AI 参考片 | 9 镜分镜 → 24s 参考成片(自审修 2 处) | ¥17.6 | 0(纯参考片) |
| 实拍+AI 混剪 | 5 条 4K → 15s 卡点片:AI 元素 17%、滤镜、叠化×4、重音对齐、旁白字幕 | ¥6.0 | 3 次点头 |

## 🧯 FAQ

- **剪映打不开草稿?** `vendor/CapCutAPI/config.json` 的 `draft_profile` 按剪映版本选(10.x 用 `jianying_pro_10`)
- **生成报 duration 无效?** Seedance mini 时长下限 4s——本引擎策略是"生成留余量,剪单裁精确",1s 快切照样支持
- **本机挂代理生成失败?** 已内置绕代理直连+退避重试+断点续跑;单段失败不拖死整批
- **字幕没烧进画面?** ffmpeg 精简版无 libass 时自动降级软字幕轨;装完整版 ffmpeg 即硬烧

## 🛣️ Roadmap

- [ ] 云预览通路(自有 OSS,网页看时间线)
- [ ] TTS 旁白配音进管线
- [ ] 成片级 AI 段工作流(1080p 生成+审帧)
- [ ] DaVinci Resolve 物化器(专业调色场景)

## 🙏 致谢

[VectCutAPI](https://github.com/sun-guannan/VectCutAPI)(剪辑执行基座) · [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)(草稿格式层) · Seedance / 火山方舟(生成)

## 📄 License

[Apache-2.0](LICENSE)(与上游基座一致)

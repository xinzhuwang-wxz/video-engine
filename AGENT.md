# AGENT.md · video-engine(AI 驱动的短视频生产插件)

> 任何 agent(Claude Code / Codex / Hermes / OpenClaw / 自建)挂载本插件,先读这份。
> `$VE` = 本文件所在目录(插件根)。

## 这是什么

**成熟基座 + 决策层二开**的短视频生产插件:从「一句想法/一堆素材」到「带手艺的剪映草稿 + 成片」,
制作环节人不参与,人只做:过目分镜、拍摄、发布前确认。

| 层 | 是什么 | 来源 |
|---|---|---|
| 决策层 | 3 个技能(分镜/生成/剪辑)+ 剪单契约(每个决定带 rationale,可人审可复现) | 本插件自研 |
| 执行层 | [VectCutAPI](https://github.com/sun-guannan/VectCutAPI)(2039★):362转场/468滤镜/关键帧/音轨,HTTP :9001 | setup.sh 克隆 + patches/ |
| 生成层 | Seedance(火山方舟,`SEEDANCE_MODEL` 可换任意模型) | `scripts/seedance_gen.py` |
| 前端 | 剪映(本地,人看/改/导出) 或 VectCut 云预览(需自有 OSS,opt-in) | 基座自带 |

## 技能(skills/,SKILL.md 开放标准,跨 agent 通用)

- **video-storyboard**:想法 → 专业分镜(人读表+机器JSON;旁白显式决策;宣称校验闸)
- **video-previz**:分镜 → 逐段 AI 示例视频(拍摄参考;成本闸,烧钱前分镜必须过目)
- **video-editing**:素材+意图 → 剪单 → 自审回环 → 带手艺的剪映草稿 + 成片(双出口)

三技能入口无关、自由组合(想法先行/素材先行/AI实拍混合都是编排,不固化流程);
先验(分镜/参考片/命名规约)全部可选注入,缺则降级自建。

## 安装到各 agent

```bash
git clone https://github.com/xinzhuwang-wxz/video-engine.git && cd video-engine && bash setup.sh
```
- **Claude Code**:`ln -s $PWD/skills/* ~/.claude/skills/` (或整仓作为项目直接打开)
- **Codex**:项目内可用(读本 AGENT.md);或 skills 放入 `~/.codex/skills`
- **Hermes**:`ln -s $PWD/skills/* ~/.hermes/skills/`
- **OpenClaw / 其它**:凡支持 SKILL.md 标准的,把 skills/ 挂进其技能目录即可
- 配置:`.env` 填 `ARK_API_KEY`(生成用;不填也能剪);起引擎:`cd vendor/CapCutAPI && .venv/bin/python capcut_server.py`

## 工作区形态与纪律(详见 README.md)

`素材库/{SKU}/01-原始拍摄|02-AI生成|03-成片|04-工作台/{NOTE}/`;
存在即状态、manifest 是索引不是事实、引用优先不搬运、命名规约 `{SKU}-{NOTE}-S{n}_{AI|实拍}.mp4`。

## 红线(所有 agent 必须遵循)

1. **绝不自动发布**;成片停在"待人确认"。
2. **原素材只读**;剪辑只发生在草稿/渲染层。
3. **默认本地零外发**;云预览是显式 opt-in。
4. **烧钱前人先看**:新拟分镜必须过目;生成预算超 50 元必须确认。
5. **决策必须留痕**:剪单每刀带 rationale;手艺名过 `style-presets/enums.json` 白名单;转场挂前段。
6. AI 生成内容发布时按平台要求做 AI 声明(调用方职责,本插件在汇报中提醒)。

## 常用命令(Makefile)

`make doctor` 环境体检(开工前) · `make smoke` 回归(改动后必跑) · `make test` 单元测试 ·
`make server` 起引擎 · `make produce CUTLIST=… OUT=… BGM=…` 一键出片 ·
`python3 scripts/status.py <工作台目录>` 接手任何笔记先跑这个(有什么/缺什么/下一步/停滞检测)。

## 回归

改动后必跑:`make smoke`(零 API 零网络;引擎服务在跑时会额外覆盖物化断言)+ `make test`。
vendor 升级流程见 `patches/README.md`。

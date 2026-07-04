---
name: video-editing
description: agent 主剪:把「AI参考片 + 实拍分段素材」剪成成片——用分镜先验 + ffprobe/抽帧分析算出剪单(cutlist,每段入出点+理由),ffmpeg 低清渲染后 agent 抽帧回看自审(≤3轮迭代改剪单),直出成片到 03-成片/;同时物化一份剪映双轨草稿(实拍/AI参考画中画/字幕)作为人的观察与介入窗口——人不介入也能出片,人只做发布前确认。字幕加不加由 agent 自主决定。支持 AI/实拍混剪。Use when 用户说『按AI示例剪实拍 / 帮我剪成片 / 拼草稿 / 出剪单 / previz拍完了帮我剪』,或给了一组按 {SKU}-{排期编号}-S{n}_{AI|实拍}.mp4 命名的分段素材要成片时。本技能不生成AI视频(video-previz 的事)、绝不自动发布。
license: MIT
---
> **路径约定**:`$VE` = 本插件根目录(含 `AGENT.md`/`cutlist.schema.json` 的那层)。独立部署时 `VE=仓库根`;作为子目录挂载时 `VE=<挂载路径>`。


# video-editing · 剪单驱动的 AI 剪辑

> 一项**纯能力**:`分段素材 → 剪单(cutlist) → 剪映双轨草稿`。
> 剪单是决策契约(`$VE/cutlist.schema.json`):agent 决策(选哪段、切哪里、为什么)与
> 物化(剪映/Resolve)分离——换剪辑引擎不换决策,换生成模型不影响本技能(素材是什么模型生成的无所谓,守命名规约即可)。

## 红线(铁律)

1. **绝不改动原素材文件**:剪辑只发生在草稿层(素材被复制进草稿 assets),原片只读。
2. **默认本地,零外发**:物化走 VectCutAPI 本地服务(:9001),素材不出机器;云预览(上传自有OSS)是显式 opt-in(issue #16)。
3. **剪单每段必须写 `rationale`**(为什么选这个窗口)——人审时要看得懂 agent 的剪辑意图。
4. **字幕可选,agent 自主决定**;但只要加,文本只能来自该笔记的既有脚本/文案(storyboard 的 subtitle 列),绝不现编卖点;宣称类措辞转人审。
5. **绝不自动发布**:成片就绪后停在"待人确认",发布动作永远归人。剪辑本身不需要人。

## 输入

**必备只有一样:任意视频素材(任何来源、任何命名)+ 一句剪辑意图**(意图也可以缺——agent 看完素材自拟并报告)。
其余全部是**可选先验,有则用之增质,缺则降级自建**:
- 命名规约 `{SKU}-{排期编号}-S{n}_{AI|实拍}.mp4` → 有则直接配对;**没有则步骤0 agent 自己抽帧理解每条内容、归位进素材库并按规约命名**(登记原名→新名对照);
- 分镜脚本(storyboard) → 有则作段意图/字幕先验;没有则从意图自拟结构;
- AI 参考片 → 有则对照剪;没有则按素材质量与节奏直接剪;
- SKU/排期编号 → 没有则用 `_通用/{日期-主题}` 归位。

## 工作流

### 0) 盘点与归位
```bash
cat <素材库>/{SKU}/04-工作台/{排期编号}/manifest.jsonl 2>/dev/null   # 有索引先读索引
ls <素材目录>/                                                        # 没有就扫目录(存在即状态,manifest 可重建)
```
守规约的素材按段号直接配对;不守规约的:每条抽 1-2 帧看内容 → 判断角色(实拍/AI/背景空镜)与合理段序。
**引用优先,不搬运**:素材留在用户指定的原位,把「原地址 + 判定角色 + 段序 + 规约化名」逐条登记进
`04-工作台/{NOTE}/manifest.jsonl`——地址在 manifest 里 = 素材已在空间中(剪单/渲染本来就按路径取件)。
仅当原位易失(如 ~/Downloads、外接盘即将拔走)才建议复制进 01-原始拍摄/ 并在 manifest 记两个地址。
**完成判据**:每个段号的可用素材在 manifest 有登记;缺料照实报告(可用 AI 片顶或留空)。

### 1) 分析素材
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 <文件>          # 每条时长
ffmpeg -v error -ss <秒> -i <文件> -frames:v 1 /tmp/kf_<段>_<秒>.jpg       # 关键帧抽样(每条抽2-4帧)
```
agent 看关键帧判断:有效内容窗口(掐掉起手/收尾的整理动作,一般头 0.3~0.5s 手抖)、哪条实拍最贴对应 AI 段的构图。**完成判据**:每段有「候选入点/出点 + 依据」。

### 2) 产出剪单
按 `$VE/cutlist.schema.json` 写 cutlist JSON,规则:
- 每段目标时长 ≈ 对应 AI 段时长(分镜先验);实拍不够长就整段用+微调变速。
- `main` 选实拍;空镜/氛围段实拍缺失或质量差时,`main` 直接用 AI 片(混剪)。
- 有实拍的段把 AI 片放 `ai_ref`(画中画参考,便于人精修对照);纯 AI 段 `ai_ref: null`。
- `subtitle` 从分镜脚本取;`rationale` 每段必填。
剪单保存到工作台 `素材库/{SKU}/04-工作台/{排期编号}/cutlist.json`(工作区形态见 `$VE/README.md`),然后过校验闸:
```bash
python3 $VE/scripts/validate_cutlist.py <cutlist路径>
```
**完成判据**:校验器输出 `✓ 剪单合格`(它查:必填/段序/in<out/文件存在/rationale 非空)。不合格按报错修剪单重校,最多 2 轮。

### 3) 低清预渲(给自己看的)
```bash
python3 $VE/scripts/render_cutlist.py <cutlist路径> --preview
```
**完成判据**:输出 preview mp4,时长 = 剪单各段之和(±0.5s)。

### 4) 自审回环(agent 剪、agent 看,≤3 轮)
```bash
ffmpeg -v error -ss <各段中点/接缝点> -i <preview.mp4> -frames:v 1 /tmp/review_<点>.jpg
```
逐帧**亲眼看**(多模态),对照三样东西:分镜的段意图(storyboard)、AI 示例片对应帧、剪单的 rationale。查:
段序对不对、入出点是否切进废动作、景别节奏(相邻段避免同景别连跳)、明显穿帮/黑场/糊帧。
发现问题 → 改剪单(带上新 rationale)→ 回步骤 2 校验 → 重物化重渲。**最多 3 轮,收敛不了如实报告剩余问题**。
**完成判据**:最后一轮抽帧全部与分镜意图一致,或已达 3 轮上限并列明遗留。

### 4.5) 手艺设计(收敛后、物化前)
按 `$VE/style-presets/presets.md` 的**判断规则**给剪单加手艺字段——
`grade`(全片滤镜+强度)、`main.transition`(慢段间转场)、`push_in`(静态段缓推)、`bgm`(音乐+音量);
有 BGM 时先跑重音对齐:
```bash
python3 $VE/scripts/beat_align.py <cutlist路径> <bgm文件> --write   # 切点吸附真实重音(±0.15s)
```
**铁律**:转场/滤镜名必须存在于 `$VE/style-presets/enums.json`;每个手艺选择写 rationale;
**转场挂在前面的片段上**(引擎语义:S1→S2 的叠化写在 S1 的 main.transition,写错一格转场就错位一段)。

### 5) 物化(基座:VectCutAPI 官方引擎)+ 双出口
```bash
# 前置(一次):cd $VE/vendor/CapCutAPI && .venv/bin/python capcut_server.py &   # 官方服务:9001
python3 $VE/scripts/cutlist_to_vectcut.py <cutlist路径>    # 剪单→带手艺的剪映草稿(转场/滤镜/关键帧/BGM轨)
```
**双出口,按需选**:
- **质量出口(默认)**:上面生成的剪映草稿 → 人打开剪映确认/微调 → 点导出(手艺全保留,也是发抖音选曲库配乐的入口);
- **无人值守出口**:`render_cutlist.py --out …_成片.mp4 --bgm <bgm>`(ffmpeg 直出,**无转场滤镜等手艺**,适合快速交付/批量粗版)。
(注意:写草稿时别让剪映开着同一草稿;新草稿在剪映首页刷新后可见。首次装引擎:`uv venv .venv && uv pip install -r requirements.txt`,upstream 升级后按 `$VE/patches/README.md` 重放补丁。)
**完成判据**:草稿目录含 `draft_content.json`,实拍轨段数与剪单一致,transitions/effects/audios 素材非空(有相应手艺时)。

### 6) 登记 + 汇报(停在"待人确认发布")
本次全部产物(cutlist/preview/成片/草稿)逐个 append 进 `04-工作台/{排期编号}/manifest.jsonl`
(`{"role":..,"path":..,"by":"agent"}`,行序即时间线);自审各轮写 `review.jsonl`。
然后汇报:成片路径 + 草稿路径(想动手就开剪映找 `dfd_cat_*`,不动手成片即用)+ 剪单路径 +
每段一句 rationale + 自审回环记录(每轮改了什么)+ 缺料/降级说明。
落库回填(成片/草稿路径写回笔记表)是独立工位步骤,由调用方经 `lib/feishu_workbench.py` 完成,本技能不碰飞书。

## 输出契约

`{ "final_mp4": str, "draft_dir": str, "cutlist_path": str, "review_rounds": [{"round", "changes"}], "segments": [{"seq", "main_source": "实拍|AI", "rationale"}], "gaps": [缺实拍的段号] }`

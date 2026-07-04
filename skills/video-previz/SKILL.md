---
name: video-previz
description: 把分镜脚本变成逐段 AI 示例视频(previz/动态分镜)——每段用该 SKU 的实拍图当首帧、分镜描述当提示词,调视频生成模型(默认 Seedance,可换)产出拍摄参考片,按 {SKU}-{排期编号}-S{n}_AI.mp4 落进素材库。拍摄的人照着示例逐段拍,拍完交给 video-editing 技能剪。Use when 用户说『给这条笔记生成示例视频 / 生成previz / 出动态分镜 / 分镜转视频 / 拍摄参考片』,或分镜脚本已定、准备安排拍摄时。本技能不剪辑(video-editing 的事)、不写飞书、不自动发布。
license: Apache-2.0
---
> **路径约定**:`$VE` = 本插件根目录(含 `AGENT.md`/`cutlist.schema.json` 的那层)。独立部署时 `VE=仓库根`;作为子目录挂载时 `VE=<挂载路径>`。


# video-previz · 分镜 → AI 示例视频

> 一项**纯能力**:`分镜段 + 首帧图 → 守命名规约的参考 mp4`。
> 示例视频是**拍摄标准**不是成片:告诉拍摄的人"这段拍成这样"。生成模型可换
> (SEEDANCE_MODEL env / 换 adapter),下游剪辑技能只认文件名,不关心哪个模型生成。

## 红线(铁律)

1. **成本闸**:默认 720p、每段 ≤5 秒;一条笔记的 previz 预算 ≈ 每秒 1 元上下,生成前把「段数 × 时长 × 预估花费」报给用户,**超过 50 元必须先确认**。
2. **首帧必须用该 SKU 的真实素材图**(上身图/商品图),不得拿别家衣服或凭空生成的首帧——示例里必须是"这件衣服"。
3. **提示词只描述镜头与动作,不写品牌宣称**(示例片不出街,但防止被误用为成片)。
4. **产出只落素材库目录,不覆盖已有文件**;同段重生成加 `-v2` 后缀,人选后手动改名。

## 输入

**必备只有一样:每段一句画面描述**(哪怕用户只给一句总意图,agent 先自拟分段再生成)。其余全部是可选先验:
- **video-storyboard 的输出 JSON**(首选,字段直接映射:`previz_prompt→prompt / duration→duration / first_frame_hint→选图`);
- 首帧图 → 有产品/人物实拍图则锚定主体(红线2:涉及具体产品必须用真图);**纯氛围/空镜/通用内容可无首帧纯文生**;
- SKU/排期编号 → 没有则落 `素材库/_通用/{日期-主题}/`,命名规约不变;
- 档位:默认 720p 参考级(previz);**用户明确要"AI 段直接进成片"时用 `--resolution 1080p` 成片级,生成后必须逐段审帧,不过关重生成**(场景:AI/实拍混剪,见 issue #15)。

## 工作流

### 1) 组装 segments JSON
agent 把分镜脚本整理成:
```json
[{"seq":1, "prompt":"<该段画面描述,镜头语言化>", "first_frame":"<该SKU上身图路径>", "duration":5}]
```
提示词写法:主体(模特/衣服)+动作+运镜+光线+质感,一段一镜头,不贪长。
**完成判据**:每段有 prompt;有实拍图可用的段都填了 first_frame;总预算已口头报给用户;
**分镜若是本次新拟的(非用户给定),必须先把分镜表展示给用户过目、得到认可后才开始生成**(2026-07-04 用户反馈:烧钱前人先看)。

### 2) 先 dry-run 再真跑
```bash
python3 $VE/scripts/seedance_gen.py --segments segs.json --sku GY-003 --note PQ-012 --dry-run   # 免费预检
python3 $VE/scripts/seedance_gen.py --segments segs.json --sku GY-003 --note PQ-012             # 真实生成(需 ARK_API_KEY)
```
落盘:`{素材库根}/{SKU}/02-AI生成/{SKU}-{排期编号}-S{nn}_AI.mp4`(根目录 `--out-root` 或 `ASSET_ROOT`,默认 `~/素材库`)。
**完成判据**:结果 JSON 全部 `ok:true`;失败段报给用户(可单段重试)。

### 3) 登记 + 汇报
生成的每段 append 进 `04-工作台/{排期编号}/manifest.jsonl`(`role:"ai_ref"`,工作区形态见 `$VE/README.md`)。
汇报每段:文件路径 + 提示词摘要 + token 消耗。提醒拍摄侧:照着示例逐段拍,实拍按
`{SKU}-{排期编号}-S{nn}_实拍.mp4` 命名放进 `01-原始拍摄/`,拍完喊 video-editing 剪。

## 输出契约

`{ "note_id": str, "files": [{"seq", "path", "tokens"}], "failed": [段号], "cost_estimate": str }`

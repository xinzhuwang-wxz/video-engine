# video-engine · AI 驱动的视频剪辑层

> **架构(2026-07-04 定):成熟基座 + 二次开发。**
> 基座 = [VectCutAPI](https://github.com/sun-guannan/VectCutAPI)(原名 CapCutAPI,2039★):剪辑执行引擎
> (362转场/468滤镜/关键帧/蒙版/音轨,HTTP :9001 + MCP,官方 vectcut-api 技能已装,云预览前端 vectcut.com)。
> 我们的二次开发 = 决策层与生产制度:**剪单契约**(决策记录,engine-agnostic)+ 分镜/生成/自审技能 +
> 工作区制度 + 风格判断规则 + 合规红线。前端:剪映(本地默认)/ VectCut 云预览(opt-in,#16)。
> 已退役:自研直连物化器(cutlist_to_draft/smoke_dual_track);render_cutlist 降级为自审预览+无人值守粗版出口。

## 目录

```
video-engine/
  cutlist.schema.json      # 剪单契约(手艺字段:grade/transition/push_in/bgm)
  style-presets/           # enums.json=引擎枚举白名单(机器dump) + presets.md=选型判断规则
  patches/                 # vendor 补丁(0001滤镜透传)+重放纪律
  scripts/
    cutlist_to_vectcut.py  # 剪单 → 官方引擎(:9001) → 带手艺的剪映草稿【主物化器】
    beat_align.py          # BGM 重音检测→切点吸附
    render_cutlist.py      # ffmpeg:自审预览(--preview)/无人值守粗版(无手艺)
    seedance_gen.py        # previz/AI元素/BGM 生成(方舟,模型可换)
    validate_cutlist.py    # 剪单校验闸
  testdata/                # 冒烟测试素材
  vendor/CapCutAPI/        # 基座克隆(remote=VectCutAPI upstream;venv 在其 .venv/)
```

## 用法

```bash
# 起基座服务(一次)
cd $VE/vendor/CapCutAPI && .venv/bin/python capcut_server.py &   # :9001
# 物化剪单(带手艺)
python3 scripts/cutlist_to_vectcut.py <cutlist.json>
# 自审预览 / 无人值守粗版
python3 scripts/render_cutlist.py <cutlist.json> --preview
```

## 标准工作区形态(目录即状态机)

```
素材库/
  {SKU}/                          # 无SKU内容 → _通用/{日期-主题}/
    01-原始拍摄/  {SKU}-{NOTE}-S{n}_实拍.mp4   (+该SKU可复用图/视频)
    02-AI生成/    {SKU}-{NOTE}-S{n}_AI.mp4
    03-成片/      {NOTE}_成片.mp4
    04-工作台/{NOTE}/               # 每条笔记一个工作目录(文档类产物都在这)
        storyboard.md / storyboard.json    # 分镜(video-storyboard 产)
        cutlist.json                       # 剪单(video-editing 产)
        preview_v1.mp4, preview_v2.mp4 …   # 自审各轮低清渲染
        review.jsonl                       # 自审记录(每轮一行:看了什么/改了什么)
        manifest.jsonl                     # 产物登记(见下)
```

**三条纪律:**
1. **存在即状态,不用时间戳**:agent 接手任何笔记,先看目录里有什么——有 storyboard 没 AI 片=该生成;
   有实拍没 cutlist=该剪;有成片=待人确认发布。先后顺序(先脚本还是先素材)不影响推断,缺哪补哪。
2. **manifest.jsonl 是索引不是事实**:每产出一个文件 append 一行
   `{"role":"storyboard|ai_ref|footage|cutlist|preview|final","path":"<相对素材库根>","seq":N,"by":"agent|human"}`
   ——行序即时间线。**文件是真相**:manifest 缺失/过期时,agent 扫描目录+抽帧即可重建它。
3. **文件角色不全有、顺序不定,都正常**:工作区不是流水线,是黑板——谁先来谁先写,agent 看黑板决定下一步。
4. **"在空间中有" = 物理存在 或 地址被登记**:原始素材可以留在用户指定的任何位置,manifest 记地址即入空间
   (引用优先,不搬运;剪单/渲染按路径取件)。复制仅在原位易失时做,且两个地址都登记。

## 安全与配置

- 基座本地流程零外发(save 走内存缓存;作者云函数仅 script_data=None 恢复路径触发,我们不走)。
- 云预览 = 上传**自有** OSS(`is_upload_draft`,默认关,opt-in 见 issue #16)。
- `config.json`: `draft_profile=jianying_pro_10`(对应本机剪映 10.9)。
- vendor 升级流程与补丁重放:`patches/README.md`;升级后必跑 `bash evals/video_smoke.sh`。

## 开放事项(GitHub issues)

#16 云预览OSS(等拍板) · #13 完整版ffmpeg(硬字幕) · #8 Resolve备选 · #9 飞书回填 · #14 OpenCut观察哨

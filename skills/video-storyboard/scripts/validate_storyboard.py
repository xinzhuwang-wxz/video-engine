#!/usr/bin/env python3
"""分镜脚本校验器(仅标准库):video-storyboard 第 3 步的完成判据。

errors(不过闸): note_id/segments 缺失、seq 不从1连续、每段必填字段缺
              (scene/duration/first_frame_hint/previz_prompt,line 与 subtitle 至少一)、
              段时长出 [2,8]s、钩子段(seq=1)>3s、总时长与 total_duration 偏差>30%。
warnings(过闸但提示人审): 台词/字幕命中宣称敏感词(应同时出现在 claims_to_review)。
用法: python3 validate_storyboard.py <storyboard.json>
"""
import json
import sys
from pathlib import Path

REQUIRED = ("scene", "duration", "first_frame_hint", "previz_prompt")
CLAIM_WORDS = ("最", "第一", "顶级", "100%", "永不", "治", "抗菌", "正宗", "正统", "唯一")
FRAME_HINTS = {"商品图", "形象图", "细节图", "上身视频截帧", "上身图", "搭配图", "空镜·场景",
               "工艺特写", "制作过程视频截帧", "面料·纹理特写", "文物原图", "文物对照图"}


def validate(sb: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    if not sb.get("note_id"):
        errs.append("缺 note_id")
    segs = sb.get("segments")
    if not isinstance(segs, list) or not segs:
        return errs + ["segments 缺失或为空"], warns

    reviewed = set(sb.get("claims_to_review") or [])
    total = 0.0
    for i, seg in enumerate(segs):
        tag = f"段[{i}](seq={seg.get('seq')})"
        if seg.get("seq") != i + 1:
            errs.append(f"{tag}: seq 必须从1连续(期望 {i+1})")
        for k in REQUIRED:
            v = seg.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                errs.append(f"{tag}: 缺 {k}(机器契约不省略)")
        if not ((seg.get("line") or "").strip() or (seg.get("subtitle") or "").strip()):
            warns.append(f"{tag}: 纯画面段(无台词无字幕)——快切/落版合法,确认是有意设计")
        dur = seg.get("duration")
        if isinstance(dur, (int, float)):
            total += dur
            if not (1 <= dur <= 8):  # 下限1s:快切镜是真实分镜语言(如开箱快切过渡)
                errs.append(f"{tag}: 段时长 {dur}s 出界(1-8s)")
            if i == 0 and dur > 3:
                errs.append(f"{tag}: 钩子段必须 ≤3s(现 {dur}s)")
        hint = seg.get("first_frame_hint")
        if hint and hint not in FRAME_HINTS:
            warns.append(f"{tag}: first_frame_hint '{hint}' 不在素材表12类枚举(下游可能取不到图)")
        text = f"{seg.get('line','')} {seg.get('subtitle','')}"
        # 序数词排除:「第一件/次/天/步/个/人称/眼/章」是叙述不是宣称
        import re
        text_c = re.sub(r"第一(?=[件次天步个人眼章])", "", text)
        for w in CLAIM_WORDS:
            if w in text_c:
                sent = (seg.get("line") or seg.get("subtitle") or "").strip()
                if sent not in reviewed:
                    warns.append(f"{tag}: 命中宣称敏感词「{w}」且未列入 claims_to_review → 必须人审")

    want = sb.get("total_duration")
    if isinstance(want, (int, float)) and want > 0 and abs(total - want) / want > 0.3:
        errs.append(f"总时长 {total:.0f}s 与目标 {want}s 偏差超 30%")
    return errs, warns


def main():
    if len(sys.argv) != 2:
        print("用法: validate_storyboard.py <storyboard.json>", file=sys.stderr)
        sys.exit(1)
    try:
        sb = json.loads(Path(sys.argv[1]).read_text())
    except Exception as e:
        print(f"✗ 读取/解析失败: {e}", file=sys.stderr)
        sys.exit(1)
    errs, warns = validate(sb)
    for w in warns:
        print(f"  ⚠ {w}", file=sys.stderr)
    if errs:
        print("✗ 分镜不合格:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    segs = sb["segments"]
    total = sum(s.get("duration", 0) for s in segs)
    print(f"✓ 通过: {len(segs)} 段 / 共 {total:.0f}s" + (f" / {len(warns)} 条宣称提示待人审" if warns else ""))


if __name__ == "__main__":
    main()

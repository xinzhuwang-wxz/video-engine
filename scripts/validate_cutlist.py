#!/usr/bin/env python3
"""剪单校验器(仅标准库):video-editing 技能第 2 步的完成判据。

检查:必填字段 / 段序为正且不重复 / in<out / speed>0 / 素材文件存在 / rationale 非空(红线3)。
用法: python3 validate_cutlist.py <cutlist.json> [--asset-root <素材库根>] [--probe]
      --probe: 深校验(预渲染门):ffprobe 逐素材验证 可读/时长≥out/有视频流;无音频流给 warning。
退出码: 0=通过, 1=不通过(stderr 列出全部问题)。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def probe_asset(p):
    """返回 (dur, has_video, has_audio) 或 None(不可读)。"""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration:stream=codec_type", "-of", "json", str(p)],
                           capture_output=True, text=True, timeout=30)
        d = json.loads(r.stdout)
        kinds = {s0.get("codec_type") for s0 in d.get("streams", [])}
        return float(d["format"]["duration"]), "video" in kinds, "audio" in kinds
    except Exception:
        return None

def validate(cl: dict, asset_root: Path | None) -> list[str]:
    errs = []
    if not cl.get("note_id"):
        errs.append("缺 note_id")
    segs = cl.get("segments")
    if not isinstance(segs, list) or not segs:
        return errs + ["segments 缺失或为空"]

    seen = set()
    for i, seg in enumerate(segs):
        tag = f"段[{i}](seq={seg.get('seq')})"
        seq = seg.get("seq")
        if not isinstance(seq, int) or seq < 1:
            errs.append(f"{tag}: seq 必须是正整数")
        elif seq in seen:
            errs.append(f"{tag}: seq 重复")
        else:
            seen.add(seq)

        if not (seg.get("rationale") or "").strip():
            errs.append(f"{tag}: rationale 必填(红线:人审要看得懂剪辑理由)")

        for role in ("main", "ai_ref"):
            clip = seg.get(role)
            if clip is None:
                if role == "main":
                    errs.append(f"{tag}: 缺 main")
                continue
            f = clip.get("file")
            if not f:
                errs.append(f"{tag}.{role}: 缺 file")
            else:
                p = Path(f)
                if not p.is_absolute() and asset_root:
                    p = asset_root / p
                if not p.exists():
                    errs.append(f"{tag}.{role}: 文件不存在 {p}")
            _in, _out = clip.get("in"), clip.get("out")
            if not (isinstance(_in, (int, float)) and isinstance(_out, (int, float))):
                if role == "main":
                    errs.append(f"{tag}.{role}: in/out 必须是数字")
            elif _in >= _out:
                errs.append(f"{tag}.{role}: 要求 in < out (现 {_in} >= {_out})")
            if role == "main" and clip.get("speed") is not None and clip["speed"] <= 0:
                errs.append(f"{tag}.main: speed 必须 > 0")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cutlist")
    ap.add_argument("--asset-root", default=None)
    ap.add_argument("--probe", action="store_true", help="深校验:ffprobe 逐素材验可读/时长/流")
    args = ap.parse_args()
    try:
        cl = json.loads(Path(args.cutlist).read_text())
    except Exception as e:
        print(f"✗ 读取/解析失败: {e}", file=sys.stderr)
        sys.exit(1)
    errs = validate(cl, Path(args.asset_root) if args.asset_root else None)
    if args.probe and not errs:
        root = Path(args.asset_root) if args.asset_root else None
        for i, seg in enumerate(cl.get("segments", [])):
            for role in ("main", "ai_ref"):
                clip = seg.get(role)
                if not clip or not clip.get("file"):
                    continue
                fp = Path(clip["file"])
                if not fp.is_absolute() and root:
                    fp = root / fp
                info = probe_asset(fp)
                tag = f"段[{i}](seq={seg.get('seq')}).{role}"
                if info is None:
                    errs.append(f"{tag}: ffprobe 不可读 {fp}")
                    continue
                dur, has_v, has_a = info
                if clip.get("out") and dur + 0.05 < float(clip["out"]):
                    errs.append(f"{tag}: 素材实际时长 {dur:.2f}s < out={clip['out']}s")
                if not has_v:
                    errs.append(f"{tag}: 无视频流")
                if role == "main" and not has_a:
                    print(f"  ⚠ {tag}: 无音频流(拼接后成片可能无声;建议配 BGM)", file=sys.stderr)
    if errs:
        print("✗ 剪单不合格:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    n = len(cl["segments"])
    total = sum((s["main"]["out"] - s["main"]["in"]) / s["main"].get("speed", 1.0) for s in cl["segments"])
    print(f"✓ 剪单合格: {n} 段, 预计成片 {total:.1f}s")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""剪单物化(直出成片):cutlist JSON → ffmpeg 无头渲染 mp4。agent 自剪自审用,不经剪映。

同一份剪单的第三个物化器(与 cutlist_to_draft.py 平行):
- 逐段裁切(main.in/out)+ 变速 + 统一编码(画布分辨率/30fps/yuv420p)
- 按段序拼接;音频保留各段原声(volume 0 则静音)
- 字幕:探测 ffmpeg 能力——有 subtitles/libass 就硬烧;没有则软字幕轨(mov_text)+警告
- ai_ref 不进成片(它是参考,只进剪映草稿给人看)

用法: python3 render_cutlist.py <cutlist.json> [--out <输出mp4>] [--height 1920] [--preview]
      --preview: 低清快渲(540x960/crf 32),给 agent 回看迭代用,快且省
输出: stdout 最后一行 = 成片路径。仅标准库+ffmpeg。
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ORIG_CWD = Path.cwd()


def run(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败: {' '.join(map(str, cmd[:8]))}...\n{r.stderr[-800:]}")


def has_filter(name: str) -> bool:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return any(f" {name} " in line for line in r.stdout.splitlines())


def fmt_srt_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):06.3f}".replace(".", ",")


def render(cutlist: dict, out: Path, width: int, height: int, crf: int) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="render_"))
    parts, srt_lines, cursor = [], [], 0.0

    for i, seg in enumerate(cutlist["segments"]):
        m = seg["main"]
        f = Path(m["file"])
        if not f.is_absolute():
            f = ORIG_CWD / f
        speed = m.get("speed", 1.0)
        dur = (m["out"] - m["in"]) / speed
        part = tmp / f"part{i:02d}.mp4"
        vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
        if speed != 1.0:
            vf += f",setpts=PTS/{speed}"
        vol = m.get("volume", 1.0)
        af = f"atempo={speed}," if speed != 1.0 else ""
        af += f"volume={vol}"
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(m["in"]), "-to", str(m["out"]), "-i", str(f),
             "-vf", vf, "-af", af, "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(part)])
        parts.append(part)
        sub = (seg.get("subtitle") or "").strip()
        if sub:
            srt_lines.append(f"{len(srt_lines)+1}\n{fmt_srt_time(cursor)} --> {fmt_srt_time(cursor+dur)}\n{sub}\n")
        cursor += dur

    concat_txt = tmp / "concat.txt"
    concat_txt.write_text("".join(f"file '{p}'\n" for p in parts))
    merged = tmp / "merged.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
         "-c", "copy", str(merged)])

    out.parent.mkdir(parents=True, exist_ok=True)
    if srt_lines:
        srt = tmp / "subs.srt"
        srt.write_text("\n".join(srt_lines), encoding="utf-8")
        if has_filter("subtitles"):  # 硬烧(需 libass)
            run(["ffmpeg", "-v", "error", "-y", "-i", str(merged), "-vf", f"subtitles={srt}",
                 "-c:v", "libx264", "-crf", str(crf), "-c:a", "copy", str(out)])
        else:  # 软字幕轨降级(issue #13:装全功能 ffmpeg 后自动硬烧)
            print("  ⚠ ffmpeg 无 subtitles 滤镜,字幕走软轨(mov_text);硬烧见 issue #13", file=sys.stderr)
            run(["ffmpeg", "-v", "error", "-y", "-i", str(merged), "-i", str(srt),
                 "-c", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=chi", str(out)])
    else:
        merged.rename(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cutlist")
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--preview", action="store_true", help="低清快渲(agent 回看迭代用)")
    ap.add_argument("--bgm", default=None, help="背景音乐文件:整轨替换原声,自动截齐并尾部淡出1s")
    args = ap.parse_args()

    p = Path(args.cutlist)
    if not p.is_absolute():
        p = ORIG_CWD / p
    cutlist = json.loads(p.read_text())
    canvas = cutlist.get("canvas") or {}
    w = args.width or canvas.get("width", 1080)
    h = args.height or canvas.get("height", 1920)
    crf = 23
    if args.preview:
        w, h, crf = w // 2, h // 2, 32
    note = cutlist.get("note_id", "out")
    out = Path(args.out) if args.out else p.parent / f"{note}_{'preview' if args.preview else '成片'}.mp4"
    if not out.is_absolute():
        out = ORIG_CWD / out
    result = render(cutlist, out, w, h, crf)
    if args.bgm:
        bgm = Path(args.bgm)
        if not bgm.is_absolute():
            bgm = ORIG_CWD / bgm
        total = sum((s["main"]["out"] - s["main"]["in"]) / s["main"].get("speed", 1.0)
                    for s in cutlist["segments"])
        tmp_out = result.with_name(result.stem + "_bgm" + result.suffix)
        run(["ffmpeg", "-v", "error", "-y", "-i", str(result), "-i", str(bgm),
             "-map", "0:v", "-map", "1:a",
             "-af", f"atrim=0:{total},afade=t=out:st={max(0,total-1)}:d=1",
             "-c:v", "copy", "-c:a", "aac", str(tmp_out)])
        tmp_out.replace(result)
        print(f"  ♪ BGM 已合入(截齐{total:.1f}s+尾部淡出)", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()

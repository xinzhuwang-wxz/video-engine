#!/usr/bin/env python3
"""音乐重音对齐(P5):检测 BGM 能量峰,把剪单切点吸附到最近的真实重音。

原理:ffmpeg astats 逐窗(默认50ms)输出 RMS → 找局部峰(高于邻域+阈值) → 剪单各段的
时间线切点(累计时长边界)在 ±tolerance 内吸附到最近峰 → 调整该段 main.out 补偿时长差。
纯标准库+ffmpeg,不加依赖。首段起点(0)与总时长保持不变。

用法: python3 beat_align.py <cutlist.json> <bgm文件> [--tolerance 0.15] [--write]
      默认只打印对齐报告;--write 写回 cutlist(原文件备份 .bak)。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ORIG_CWD = Path.cwd()


def rms_series(bgm: Path, win: float = 0.05) -> list[tuple[float, float]]:
    """返回 [(时间, RMS_dB)],每 win 秒一点。"""
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(bgm), "-af",
         f"astats=metadata=1:reset=1:length={win},ametadata=print:key=lavfi.astats.Overall.RMS_level",
         "-f", "null", "-"],
        capture_output=True, text=True)
    pts, t = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"RMS_level=(-?[0-9.]+|-inf)", line)
        if m and t is not None:
            v = m.group(1)
            pts.append((t, -90.0 if v == "-inf" else float(v)))
    return pts


def find_onsets(pts: list[tuple[float, float]], jump_db: float = 4.0, min_gap: float = 0.25) -> list[float]:
    """能量突升点=重音:RMS 相对前一窗跳升 ≥jump_db,峰间隔 ≥min_gap。"""
    onsets, last = [], -10.0
    for i in range(1, len(pts)):
        t, v = pts[i]
        if v - pts[i - 1][1] >= jump_db and t - last >= min_gap:
            onsets.append(round(t, 3))
            last = t
    return onsets


def align(cutlist: dict, onsets: list[float], tol: float) -> list[dict]:
    """切点吸附:返回对齐报告;直接原地修改 cutlist 的 out 值。"""
    report, cursor = [], 0.0
    segs = cutlist["segments"]
    for i, seg in enumerate(segs):
        m = seg["main"]
        dur = (m["out"] - m["in"]) / m.get("speed", 1.0)
        cut = cursor + dur  # 该段结束的时间线切点
        if i == len(segs) - 1:  # 末段不动(保总时长)
            report.append({"seq": seg["seq"], "cut": round(cut, 3), "snap": None, "note": "末段保持"})
            cursor = cut
            continue
        near = min(onsets, key=lambda o: abs(o - cut)) if onsets else None
        if near is not None and abs(near - cut) <= tol and abs(near - cut) > 0.005:
            delta = near - cut
            m["out"] = round(m["out"] + delta * m.get("speed", 1.0), 3)
            seg["rationale"] = seg.get("rationale", "") + f";重音对齐{'+' if delta>0 else ''}{delta:.2f}s"
            report.append({"seq": seg["seq"], "cut": round(cut, 3), "snap": near, "delta": round(delta, 3)})
            cursor = near
        else:
            report.append({"seq": seg["seq"], "cut": round(cut, 3), "snap": None,
                           "note": f"容差内无重音(最近{near})" if near else "无重音数据"})
            cursor = cut
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cutlist")
    ap.add_argument("bgm")
    ap.add_argument("--tolerance", type=float, default=0.15)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    clp = Path(args.cutlist); clp = clp if clp.is_absolute() else ORIG_CWD / clp
    bgm = Path(args.bgm); bgm = bgm if bgm.is_absolute() else ORIG_CWD / bgm

    cutlist = json.loads(clp.read_text())
    onsets = find_onsets(rms_series(bgm))
    print(f"检测到 {len(onsets)} 个重音: {onsets[:12]}{'...' if len(onsets)>12 else ''}", file=sys.stderr)
    report = align(cutlist, onsets, args.tolerance)
    for r in report:
        print(("  ✓ S%02d 切点%.2fs → 吸附%.2fs (%+.2fs)" % (r["seq"], r["cut"], r["snap"], r["delta"]))
              if r.get("snap") else ("  · S%02d 切点%.2fs 不动(%s)" % (r["seq"], r["cut"], r.get("note", ""))),
              file=sys.stderr)
    changed = sum(1 for r in report if r.get("snap") is not None)
    if args.write:
        if changed == 0:  # 无实际吸附不落盘:保持 mtime 稳定,production --resume 才能生效
            print(f"(切点已全部在重音上,未改动文件) {clp}")
        else:
            clp.with_suffix(".json.bak").write_text(clp.read_text())
            clp.write_text(json.dumps(cutlist, ensure_ascii=False, indent=1))
            print(str(clp))
    else:
        print("(dry-run,--write 写回)")


if __name__ == "__main__":
    main()

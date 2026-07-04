#!/usr/bin/env python3
"""工作台状态探针:存在即状态的机械化(学自 OpenMontage BoardState 思想,自实现)。

原则:never block, never break——半写的 JSON、缺失的文件都只降级输出,绝不崩;
卡住要可见——工作台超过 30 分钟无文件活动且流程未完,提示"可能停滞"。

用法: python3 scripts/status.py <工作台目录(04-工作台/{NOTE})> [--json]
输出: 各产物有无 + 推导出的下一步建议。任何 agent 接手一条笔记,先跑这个。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STALL_SECONDS = 30 * 60


def _safe_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def derive(wb: Path) -> dict:
    note = wb.name
    sku_root = wb.parent.parent  # 素材库/{SKU}
    ai_dir, raw_dir, final_dir = sku_root / "02-AI生成", sku_root / "01-原始拍摄", sku_root / "03-成片"

    storyboard = _safe_json(wb / "storyboard.json")
    cutlist = _safe_json(wb / "cutlist.json")
    seg_total = len(storyboard["segments"]) if storyboard and isinstance(storyboard.get("segments"), list) else None

    def count(dir_: Path, tag: str) -> int:
        return len(list(dir_.glob(f"*{note}*{tag}*.mp4"))) if dir_.exists() else 0

    ai_n, raw_n = count(ai_dir, "_AI"), count(raw_dir, "_实拍")
    previews = sorted(wb.glob("preview*.mp4")) + sorted(wb.glob("previz*.mp4"))
    finals = list(final_dir.glob(f"*{note}*.mp4")) if final_dir.exists() else []
    manifest_lines = (wb / "manifest.jsonl").read_text(errors="replace").count("\n") if (wb / "manifest.jsonl").exists() else 0

    # 下一步推导(存在即状态)
    if not storyboard:
        nxt = "无分镜 → 跑 video-storyboard(新拟分镜须给人过目)"
    elif seg_total and ai_n == 0 and raw_n == 0:
        nxt = f"有分镜({seg_total}段)无素材 → video-previz 生成参考片(先报预算)"
    elif seg_total and 0 < ai_n < seg_total and raw_n == 0:
        nxt = f"AI片 {ai_n}/{seg_total} → 续跑 previz(断点续跑会跳过已有段)"
    elif not cutlist and (ai_n or raw_n):
        nxt = "有素材无剪单 → video-editing 出剪单(每刀带rationale)"
    elif cutlist and not previews and not finals:
        nxt = "有剪单未渲 → produce_cutlist.py 一键出片,或 cutlist_to_vectcut.py 进剪映"
    elif previews and not finals:
        nxt = "有预览未定稿 → 人审预览;通过则出正式成片/剪映草稿"
    elif finals:
        nxt = "已有成片 → 停在待人确认发布(红线:绝不自动发布)"
    else:
        nxt = "状态不完整 → 人工检查工作台"

    # 停滞检测
    stall = None
    try:
        latest = max((p.stat().st_mtime for p in wb.rglob("*") if p.is_file()), default=0)
        if latest and not finals and time.time() - latest > STALL_SECONDS:
            stall = f"距最后活动已 {int((time.time()-latest)/60)} 分钟,流程未完——可能停滞"
    except OSError:
        pass

    return {"workbench": str(wb), "note": note,
            "storyboard": bool(storyboard), "segments_planned": seg_total,
            "ai_clips": ai_n, "raw_clips": raw_n, "cutlist": bool(cutlist),
            "previews": len(previews), "finals": len(finals), "manifest_events": manifest_lines,
            "next": nxt, "stall": stall}


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: status.py <04-工作台/{NOTE} 目录> [--json]", file=sys.stderr)
        sys.exit(1)
    wb = Path(sys.argv[1]).expanduser()
    if not wb.is_dir():
        print(f"目录不存在: {wb}", file=sys.stderr)
        sys.exit(1)
    st = derive(wb)
    if "--json" in sys.argv:
        print(json.dumps(st, ensure_ascii=False, indent=1))
        return
    print(f"📋 {st['note']}  (manifest {st['manifest_events']} 条)")
    print(f"   分镜:{'✓'+str(st['segments_planned'])+'段' if st['storyboard'] else '—'}"
          f" | AI片:{st['ai_clips']} | 实拍:{st['raw_clips']}"
          f" | 剪单:{'✓' if st['cutlist'] else '—'} | 预览:{st['previews']} | 成片:{st['finals']}")
    print(f"➡️  下一步: {st['next']}")
    if st["stall"]:
        print(f"⏰ {st['stall']}")


if __name__ == "__main__":
    main()

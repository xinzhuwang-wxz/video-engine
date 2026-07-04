#!/usr/bin/env python3
"""交付承诺门:分镜(storyboard.json)=承诺,剪单(cutlist.json)=交付,渲染前逐条对账。

学自 OpenMontage 的 pre-compose validation gate(delivery promise + slideshow risk)思想,
按 video-engine 的契约体系原创实现:承诺没兑现的片子不该被渲染出来。

errors(不过门):
  - 段覆盖:分镜承诺的段在剪单缺失
  - 时长契约:某段交付时长与承诺偏差 >15%(重音对齐的微调在容差内),或总时长偏差 >10%
  - 字幕承诺:分镜写了 subtitle 的段,剪单丢了
warnings(过门但提示):
  - 静态幻灯片感:连续 ≥3 段(时长均 >3s)既无转场也无缓推
  - 同窗复用:两段用同一素材几乎相同的 in/out 窗口(疑似复制粘贴剪辑)
  - rationale 含 待定/TODO/占位

用法: python3 promise_check.py <storyboard.json> <cutlist.json> [--json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def check(sb: dict, cl: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    sb_segs = {int(s["seq"]): s for s in sb.get("segments", [])}
    cl_segs = {int(s["seq"]): s for s in cl.get("segments", [])}

    # 1. 段覆盖
    missing = sorted(set(sb_segs) - set(cl_segs))
    if missing:
        errs.append(f"分镜承诺的段在剪单缺失: {missing}")
    extra = sorted(set(cl_segs) - set(sb_segs))
    if extra:
        warns.append(f"剪单有分镜之外的段(确认是有意增补): {extra}")

    # 2. 时长契约
    total_promised = float(sb.get("total_duration") or 0)
    total_delivered = 0.0
    for seq in sorted(set(sb_segs) & set(cl_segs)):
        m = cl_segs[seq]["main"]
        dur = (float(m["out"]) - float(m["in"])) / float(m.get("speed", 1.0))
        total_delivered += dur
        promised = float(sb_segs[seq].get("duration") or 0)
        if promised > 0 and abs(dur - promised) / promised > 0.15:
            errs.append(f"S{seq:02d} 时长偏离承诺: 交付{dur:.2f}s vs 承诺{promised}s(>15%)")
    if total_promised > 0 and abs(total_delivered - total_promised) / total_promised > 0.10:
        errs.append(f"总时长偏离: 交付{total_delivered:.1f}s vs 承诺{total_promised}s(>10%)")

    # 3. 字幕承诺
    for seq, s in sb_segs.items():
        if (s.get("subtitle") or "").strip() and seq in cl_segs:
            if not (cl_segs[seq].get("subtitle") or "").strip():
                errs.append(f"S{seq:02d} 分镜承诺了字幕「{s['subtitle'][:12]}…」,剪单未交付")

    # 4. 静态幻灯片感(slideshow risk 的实拍语境版)
    run = 0
    for seq in sorted(cl_segs):
        m = cl_segs[seq]["main"]
        dur = (float(m["out"]) - float(m["in"])) / float(m.get("speed", 1.0))
        static = dur > 3.0 and not m.get("transition") and not cl_segs[seq].get("push_in")
        run = run + 1 if static else 0
        if run == 3:
            warns.append(f"连续3段(至S{seq:02d})时长>3s且无转场无缓推——成片可能有幻灯片感,考虑加缓推或调节奏")

    # 5. 同窗复用
    seen: dict[tuple, int] = {}
    for seq in sorted(cl_segs):
        m = cl_segs[seq]["main"]
        key = (Path(str(m["file"])).name, round(float(m["in"]), 1), round(float(m["out"]), 1))
        if key in seen:
            warns.append(f"S{seq:02d} 与 S{seen[key]:02d} 复用同素材同窗口({key[0]} {key[1]}-{key[2]}s)——确认是有意重复")
        else:
            seen[key] = seq

    # 6. rationale 占位
    for seq in sorted(cl_segs):
        r = cl_segs[seq].get("rationale") or ""
        if any(w in r for w in ("待定", "TODO", "占位", "tbd")):
            warns.append(f"S{seq:02d} rationale 含占位词——决策未完成就别过门")

    return errs, warns


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: promise_check.py <storyboard.json> <cutlist.json> [--json]", file=sys.stderr)
        sys.exit(2)
    sb = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    cl = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    errs, warns = check(sb, cl)
    if "--json" in sys.argv:
        print(json.dumps({"ok": not errs, "errors": errs, "warnings": warns}, ensure_ascii=False, indent=1))
    else:
        for w in warns:
            print(f"  ⚠ {w}", file=sys.stderr)
        if errs:
            print("✗ 承诺未兑现:", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
        else:
            print(f"✓ 交付对账通过: {len(cl.get('segments', []))} 段兑现分镜承诺" + (f" / {len(warns)} 条提示" if warns else ""))
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()

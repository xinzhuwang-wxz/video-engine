#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_engine.production import options_from_cli, run_cutlist_production


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full local cutlist production pipeline: validate, beat-align, render base, finish, and write reports."
    )
    parser.add_argument("cutlist", help="cutlist.json")
    parser.add_argument("--out", required=True, help="final output mp4")
    parser.add_argument("--bgm", default=None, help="optional BGM file; also enables beat align by default")
    parser.add_argument("--duration", type=float, default=None, help="override final duration in seconds")
    parser.add_argument("--profile", default="douyin_vertical", help="delivery profile")
    parser.add_argument("--work-dir", default=None, help="production working directory")
    parser.add_argument("--manifest", default=None, help="manifest.jsonl output path")
    parser.add_argument("--no-beat-align", action="store_true", help="skip beat alignment even when BGM is provided")
    parser.add_argument("--resume", action="store_true", help="断点续跑:base已存在且新于剪单则跳过基础渲染")
    parser.add_argument("--no-promise", action="store_true", help="跳过交付承诺门(分镜↔剪单对账)")
    parser.add_argument("--no-probe", action="store_true", help="跳过素材深校验门")
    parser.add_argument("--beat-tolerance", type=float, default=0.15, help="beat snap tolerance in seconds")
    parser.add_argument("--no-burn-subtitles", action="store_true", help="skip hard subtitle overlay")
    parser.add_argument("--no-soft-glow", action="store_true", help="skip soft glow finish pass")
    parser.add_argument("--no-beat-flash", action="store_true", help="skip beat flash finish pass")
    parser.add_argument("--no-review", action="store_true", help="skip review sheet generation")
    args = parser.parse_args()

    options = options_from_cli(
        cutlist=args.cutlist,
        out=args.out,
        bgm=args.bgm,
        duration=args.duration,
        profile=args.profile,
        work_dir=args.work_dir,
        manifest=args.manifest,
        beat_align=not args.no_beat_align,
        beat_tolerance=args.beat_tolerance,
        resume=args.resume,
        probe_assets=not args.no_probe,
        promise_gate=not args.no_promise,
        burn_subtitles=not args.no_burn_subtitles,
        soft_glow=not args.no_soft_glow,
        beat_flash=not args.no_beat_flash,
        write_review=not args.no_review,
    )
    report = run_cutlist_production(options)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(report["output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

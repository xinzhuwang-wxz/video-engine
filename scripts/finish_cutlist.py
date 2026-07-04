#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_engine.finisher import finish_cutlist, options_from_names


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finish a rendered cutlist video with hard subtitles, light beat effects, delivery normalization, and review artifacts."
    )
    parser.add_argument("cutlist", help="cutlist.json used to render the base video")
    parser.add_argument("--input", required=True, help="base mp4 from render_cutlist.py")
    parser.add_argument("--out", required=True, help="finished output mp4")
    parser.add_argument("--profile", default="douyin_vertical", help="delivery profile name")
    parser.add_argument("--duration", type=float, default=None, help="override final duration in seconds")
    parser.add_argument("--work-dir", default=None, help="directory for generated subtitle PNGs and stage render")
    parser.add_argument("--subtitle-y", type=int, default=None, help="字幕纵坐标(默认按 profile 高度 0.738)")
    parser.add_argument("--font", default=None, help="CJK-capable font path for hard subtitles")
    parser.add_argument("--no-burn-subtitles", action="store_true", help="skip hard subtitle overlay")
    parser.add_argument("--no-soft-glow", action="store_true", help="skip soft glow pass")
    parser.add_argument("--no-beat-flash", action="store_true", help="skip cut-point flash pass")
    parser.add_argument("--no-review", action="store_true", help="skip review sheet generation")
    args = parser.parse_args()

    options = options_from_names(
        input_path=args.input,
        cutlist_path=args.cutlist,
        output_path=args.out,
        profile_name=args.profile,
        target_duration=args.duration,
        work_dir=args.work_dir,
        font_path=args.font,
        subtitle_y=args.subtitle_y,
        burn_subtitles=not args.no_burn_subtitles,
        soft_glow=not args.no_soft_glow,
        beat_flash=not args.no_beat_flash,
        write_review=not args.no_review,
    )
    report = finish_cutlist(options)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(report["output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

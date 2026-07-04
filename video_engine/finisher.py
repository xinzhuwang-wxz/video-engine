from __future__ import annotations

import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .cutlist import TimelineSegment, load_cutlist, timeline_duration, timeline_from_cutlist
from .ffmpeg_tools import probe, run, volume_detect, write_review_sheet
from .media_profiles import MediaProfile, get_profile


FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]


@dataclass(frozen=True)
class FinishOptions:
    input_path: Path
    cutlist_path: Path
    output_path: Path
    profile: MediaProfile
    target_duration: float | None = None
    work_dir: Path | None = None
    subtitle_y: int | None = None
    font_path: Path | None = None
    burn_subtitles: bool = True
    soft_glow: bool = True
    beat_flash: bool = True
    write_review: bool = True


def find_font(explicit: Path | None = None) -> Path:
    if explicit and explicit.exists():
        return explicit
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    raise RuntimeError("No CJK-capable font found. Pass --font to finish_cutlist.py.")


def _fit_font(draw, text: str, font_path: Path, max_width: int):
    from PIL import ImageFont

    size = 78 if len(text) <= 5 else 66
    while size >= 42:
        font = ImageFont.truetype(str(font_path), size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=3)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(str(font_path), 42)


def write_subtitle_images(
    timeline: list[TimelineSegment],
    profile: MediaProfile,
    work_dir: Path,
    font_path: Path,
) -> list[Path]:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Hard subtitle rendering requires Pillow. Install Pillow or pass --no-burn-subtitles.") from exc

    subtitle_dir = work_dir / "subtitle-png"
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    sub_height = max(180, round(profile.height * 0.135))

    for index, item in enumerate(timeline, 1):
        if not item.subtitle:
            continue
        image = Image.new("RGBA", (profile.width, sub_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        shadow_start = round(sub_height * 0.31)
        shadow_span = max(1, sub_height - shadow_start)
        for y in range(shadow_start, sub_height):
            progress = max(0.0, min(1.0, (y - shadow_start) / shadow_span))
            alpha = int(64 * progress**1.8)
            draw.line([(0, y), (profile.width, y)], fill=(0, 0, 0, alpha))

        font = _fit_font(draw, item.subtitle, font_path, round(profile.width * 0.86))
        bbox = draw.textbbox((0, 0), item.subtitle, font=font, stroke_width=3)
        x = (profile.width - (bbox[2] - bbox[0])) // 2
        y = round(sub_height * (0.32 if len(item.subtitle) <= 6 else 0.28))
        draw.text((x + 3, y + 5), item.subtitle, font=font, fill=(38, 28, 20, 180), stroke_width=3, stroke_fill=(38, 28, 20, 95))
        draw.text((x, y), item.subtitle, font=font, fill=(255, 248, 232, 242), stroke_width=3, stroke_fill=(68, 43, 30, 180))
        line_width = round(profile.width * 0.28)
        line_x0 = (profile.width - line_width) // 2
        line_y = sub_height - round(sub_height * 0.21)
        draw.line([(line_x0, line_y), (line_x0 + line_width, line_y)], fill=(236, 205, 148, 150), width=2)

        output = subtitle_dir / f"subtitle_{index:02d}.png"
        image.save(output)
        outputs.append(output)
    return outputs


def _subtitle_inputs(subtitle_paths: list[Path], duration: float) -> list[str]:
    inputs: list[str] = []
    for path in subtitle_paths:
        inputs.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(path)])
    return inputs


def _build_filter(
    timeline: list[TimelineSegment],
    subtitle_paths: list[Path],
    profile: MediaProfile,
    duration: float,
    *,
    subtitle_y: int,
    soft_glow: bool,
    beat_flash: bool,
    has_audio: bool = True,
) -> str:
    filters: list[str] = []
    current = "vbase"

    filters.append(
        f"[0:v]scale={profile.width}:{profile.height}:force_original_aspect_ratio=increase,"
        f"crop={profile.width}:{profile.height},setsar=1,setpts=PTS-STARTPTS[{current}]"
    )
    if soft_glow:
        filters.extend(
            [
                f"[{current}]split=2[vmain][vsoft]",
                "[vsoft]gblur=sigma=18,eq=brightness=0.018:saturation=1.04[vglow]",
                "[vmain][vglow]blend=all_mode=screen:all_opacity=0.09[vglowed]",
            ]
        )
        current = "vglowed"

    if beat_flash and len(timeline) > 1:
        # 已知边界:每切点一个 between(),>20 段时表达式变长(ffmpeg 可承受;更长请改 sendcmd)
        windows = "+".join(f"between(t,{item.start:.3f},{item.start + 0.070:.3f})" for item in timeline[1:])
        filters.append(f"[{current}]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.15:t=fill:enable='{windows}'[vflash]")
        current = "vflash"

    subtitle_input_index = 1
    subtitle_by_seq = {int(path.stem.rsplit("_", 1)[1]): path for path in subtitle_paths}
    for index, item in enumerate(timeline, 1):
        if index not in subtitle_by_seq:
            continue
        next_label = f"vsub{index}"
        end = duration if index == len(timeline) else min(item.end, duration)
        filters.append(
            f"[{current}][{subtitle_input_index}:v]overlay=x=0:y={subtitle_y}:enable='between(t,{item.start:.3f},{end:.3f})'[{next_label}]"
        )
        current = next_label
        subtitle_input_index += 1

    filters.append(
        f"[{current}]tpad=stop_mode=clone:stop_duration=0.500,"
        f"fps=fps={profile.fps}:start_time=0,trim=duration={duration:.3f},setpts=PTS-STARTPTS[vout]"
    )
    if has_audio:
        filters.append(f"[0:a:0]apad=pad_dur=0.500,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[aout]")
    else:  # 输入无音频流:合成静音轨,输出契约恒有音轨(平台端要求)
        filters.append(f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[aout]")
    return ";".join(filters)


def _render_stage(options: FinishOptions, timeline: list[TimelineSegment], subtitle_paths: list[Path], duration: float, stage_path: Path) -> None:
    subtitle_y = options.subtitle_y if options.subtitle_y is not None else round(options.profile.height * 0.738)
    input_info = probe(options.input_path)
    has_audio = any(st.get("codec_type") == "audio" for st in input_info.get("streams", []))
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(options.input_path),
        *_subtitle_inputs(subtitle_paths, duration),
        "-filter_complex",
        _build_filter(
            timeline,
            subtitle_paths,
            options.profile,
            duration,
            subtitle_y=subtitle_y,
            soft_glow=options.soft_glow,
            beat_flash=options.beat_flash,
            has_audio=has_audio,
        ),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        options.profile.video_codec,
        "-crf",
        str(max(10, options.profile.crf - 4)),  # 中间道近无损,避免两次 CRF18 叠加损失;终道 normalize 用 profile.crf
        "-r",
        str(options.profile.fps),
        "-pix_fmt",
        options.profile.pixel_format,
        "-c:a",
        options.profile.audio_codec,
        "-b:a",
        options.profile.audio_bitrate,
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-dn",
        "-movflags",
        "+faststart",
        str(stage_path),
    ]
    run(cmd)


def _normalize_stage(stage_path: Path, output_path: Path, profile: MediaProfile, duration: float) -> None:
    pad_frames = max(2, math.ceil(profile.fps * 0.2))
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(stage_path),
            "-vf",
            f"tpad=stop_mode=clone:stop={pad_frames},fps={profile.fps},setpts=PTS-STARTPTS",
            "-af",
            f"apad=pad_dur=0.200,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            profile.video_codec,
            "-crf",
            str(profile.crf),
            "-pix_fmt",
            profile.pixel_format,
            "-c:a",
            profile.audio_codec,
            "-b:a",
            profile.audio_bitrate,
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def finish_cutlist(options: FinishOptions) -> dict:
    cutlist = load_cutlist(options.cutlist_path)
    timeline = timeline_from_cutlist(cutlist)
    duration = options.target_duration if options.target_duration is not None else timeline_duration(timeline)
    if duration <= 0:
        raise ValueError("target duration must be positive")

    created_tmp = options.work_dir is None
    work_dir = options.work_dir or Path(tempfile.mkdtemp(prefix="ve_finish_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    options.output_path.parent.mkdir(parents=True, exist_ok=True)

    subtitle_paths: list[Path] = []
    if options.burn_subtitles and any(item.subtitle for item in timeline):
        subtitle_paths = write_subtitle_images(timeline, options.profile, work_dir, find_font(options.font_path))

    stage_path = work_dir / f"{options.output_path.stem}.stage.mp4"
    _render_stage(options, timeline, subtitle_paths, duration, stage_path)
    _normalize_stage(stage_path, options.output_path, options.profile, duration)

    technical_probe = probe(options.output_path, count_frames=True)
    audio = volume_detect(options.output_path)
    review_sheet = None
    if options.write_review:
        timestamps = [min(max(item.midpoint, 0.0), max(duration - 0.05, 0.0)) for item in timeline[:10]]
        review_sheet = write_review_sheet(options.output_path, timestamps, options.output_path.with_name(f"{options.output_path.stem}-review.jpg"))

    report = {
        "output": str(options.output_path),
        "cutlist": str(options.cutlist_path),
        "input": str(options.input_path),
        "profile": options.profile.name,
        "target_duration": round(duration, 3),
        "hard_subtitles": bool(subtitle_paths),
        "soft_glow": options.soft_glow,
        "beat_flash": options.beat_flash,
        "probe": technical_probe,
        "audio": audio,
        "review_sheet": str(review_sheet) if review_sheet else None,
    }
    report_path = options.output_path.with_suffix(".finish-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path)
    if created_tmp:  # 自建的临时目录成功即清;失败路径留现场供排查
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
    return report


def options_from_names(
    *,
    input_path: str | Path,
    cutlist_path: str | Path,
    output_path: str | Path,
    profile_name: str = "douyin_vertical",
    target_duration: float | None = None,
    work_dir: str | Path | None = None,
    font_path: str | Path | None = None,
    burn_subtitles: bool = True,
    soft_glow: bool = True,
    beat_flash: bool = True,
    write_review: bool = True,
    subtitle_y: int | None = None,
) -> FinishOptions:
    return FinishOptions(
        input_path=Path(input_path),
        cutlist_path=Path(cutlist_path),
        output_path=Path(output_path),
        profile=get_profile(profile_name),
        target_duration=target_duration,
        work_dir=Path(work_dir) if work_dir else None,
        font_path=Path(font_path) if font_path else None,
        burn_subtitles=burn_subtitles,
        soft_glow=soft_glow,
        beat_flash=beat_flash,
        write_review=write_review,
        subtitle_y=subtitle_y,
    )

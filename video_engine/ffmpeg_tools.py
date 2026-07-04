from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class FfmpegError(RuntimeError):
    pass


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        stderr = result.stderr[-1600:] if result.stderr else ""
        raise FfmpegError(f"command failed: {' '.join(cmd[:10])}\n{stderr}")
    return result


def probe(path: str | Path, *, count_frames: bool = False) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,duration,nb_read_frames",
        "-of",
        "json",
    ]
    if count_frames:
        cmd.insert(1, "-count_frames")
    cmd.append(str(path))
    result = run(cmd, capture=True)
    return json.loads(result.stdout)


def volume_detect(path: str | Path) -> dict[str, float | None]:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    text = result.stderr
    values: dict[str, float | None] = {"mean_volume_db": None, "max_volume_db": None}
    for line in text.splitlines():
        if "mean_volume:" in line:
            values["mean_volume_db"] = float(line.rsplit("mean_volume:", 1)[1].strip().split()[0])
        if "max_volume:" in line:
            values["max_volume_db"] = float(line.rsplit("max_volume:", 1)[1].strip().split()[0])
    return values


def write_review_sheet(input_path: str | Path, timestamps: list[float], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = output.parent / f"{output.stem}-frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    for index, timestamp in enumerate(timestamps, 1):
        frame_path = frames_dir / f"frame_{index:02d}.jpg"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ]
        )
        frame_paths.append(frame_path)

    concat = frames_dir / "frames.txt"
    concat.write_text("".join(f"file '{path.resolve()}'\n" for path in frame_paths), encoding="utf-8")
    columns = min(5, max(1, len(frame_paths)))
    rows = (len(frame_paths) + columns - 1) // columns
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-vf",
            f"scale=270:480,tile={columns}x{rows}",
            "-frames:v",
            "1",
            str(output),
        ]
    )
    return output

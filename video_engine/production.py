from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .cutlist import load_cutlist, timeline_duration, timeline_from_cutlist
from .finisher import finish_cutlist, options_from_names
from .manifest import ManifestLog


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


@dataclass(frozen=True)
class CommandRecord:
    cmd: list[str]
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], Path], CommandRecord]


@dataclass(frozen=True)
class ProductionOptions:
    cutlist_path: Path
    output_path: Path
    bgm_path: Path | None = None
    target_duration: float | None = None
    profile_name: str = "douyin_vertical"
    work_dir: Path | None = None
    manifest_path: Path | None = None
    beat_align: bool = True
    beat_tolerance: float = 0.15
    resume: bool = False          # 断点续跑:base 已存在且新于剪单则跳过基础渲染
    probe_assets: bool = True     # 预渲染门:ffprobe 深校验素材
    promise_gate: bool = True     # 交付承诺门:同目录有 storyboard.json 则渲染前对账
    burn_subtitles: bool = True
    soft_glow: bool = True
    beat_flash: bool = True
    write_review: bool = True


def _run_command(cmd: list[str], cwd: Path = REPO_ROOT) -> CommandRecord:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"{result.stderr[-1600:]}"
        )
    return CommandRecord(cmd=cmd, stdout=result.stdout, stderr=result.stderr)


def _default_base_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.base{output_path.suffix}")


def _production_work_dir(options: ProductionOptions) -> Path:
    return options.work_dir or options.output_path.parent / f"{options.output_path.stem}.work"


def _manifest_path(options: ProductionOptions) -> Path:
    return options.manifest_path or _production_work_dir(options) / "manifest.jsonl"


def _python_cmd(script: str, *args: str) -> list[str]:
    return [sys.executable, str(SCRIPTS_DIR / script), *args]


def run_cutlist_production(
    options: ProductionOptions,
    *,
    command_runner: CommandRunner = _run_command,
) -> dict:
    """Run validate -> optional beat align -> base render -> finish -> report.

    This is video-engine's small pipeline runner: it keeps the cutlist as the
    decision artifact while hiding the repetitive command choreography from
    agents and users.
    """

    cutlist_path = options.cutlist_path.resolve()
    output_path = options.output_path.resolve()
    work_dir = _production_work_dir(options).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = ManifestLog(_manifest_path(options).resolve())
    base_path = _default_base_path(output_path)

    manifest.append(
        "production.start",
        cutlist=cutlist_path,
        output=output_path,
        bgm=options.bgm_path,
        profile=options.profile_name,
    )

    try:
        validate_cmd = _python_cmd("validate_cutlist.py", str(cutlist_path))
        if options.probe_assets:
            validate_cmd.append("--probe")
        manifest.append("stage.start", stage="validate", cmd=validate_cmd)
        validate_record = command_runner(validate_cmd, REPO_ROOT)
        manifest.append("stage.complete", stage="validate", stdout=validate_record.stdout, stderr=validate_record.stderr)

        if options.bgm_path and options.beat_align:
            bgm_path = options.bgm_path.resolve()
            beat_cmd = _python_cmd(
                "beat_align.py",
                str(cutlist_path),
                str(bgm_path),
                "--tolerance",
                str(options.beat_tolerance),
                "--write",
            )
            manifest.append("stage.start", stage="beat_align", cmd=beat_cmd)
            beat_record = command_runner(beat_cmd, REPO_ROOT)
            manifest.append("stage.complete", stage="beat_align", stdout=beat_record.stdout, stderr=beat_record.stderr)

            manifest.append("stage.start", stage="validate_after_beat_align", cmd=validate_cmd)
            validate_after_record = command_runner(validate_cmd, REPO_ROOT)
            manifest.append(
                "stage.complete",
                stage="validate_after_beat_align",
                stdout=validate_after_record.stdout,
                stderr=validate_after_record.stderr,
            )

        if options.resume and base_path.exists() and base_path.stat().st_mtime >= cutlist_path.stat().st_mtime:
            manifest.append("stage.skip", stage="render_base", reason="resume:base 新于剪单", output=base_path)
        else:
            render_cmd = _python_cmd("render_cutlist.py", str(cutlist_path), "--out", str(base_path))
            if options.bgm_path:
                render_cmd.extend(["--bgm", str(options.bgm_path.resolve())])
            manifest.append("stage.start", stage="render_base", cmd=render_cmd, output=base_path)
            render_record = command_runner(render_cmd, REPO_ROOT)
            manifest.append("stage.complete", stage="render_base", stdout=render_record.stdout, stderr=render_record.stderr, output=base_path)

        storyboard_path = cutlist_path.parent / "storyboard.json"
        if options.promise_gate and storyboard_path.exists():
            promise_cmd = _python_cmd("promise_check.py", str(storyboard_path), str(cutlist_path))
            manifest.append("stage.start", stage="promise_gate", cmd=promise_cmd)
            promise_record = command_runner(promise_cmd, REPO_ROOT)
            manifest.append("stage.complete", stage="promise_gate", stdout=promise_record.stdout, stderr=promise_record.stderr)

        cutlist = load_cutlist(cutlist_path)
        duration = options.target_duration if options.target_duration is not None else timeline_duration(timeline_from_cutlist(cutlist))
        finish_work_dir = work_dir / "finish"
        manifest.append("stage.start", stage="finish", input=base_path, output=output_path, duration=duration)
        finish_report = finish_cutlist(
            options_from_names(
                input_path=base_path,
                cutlist_path=cutlist_path,
                output_path=output_path,
                profile_name=options.profile_name,
                target_duration=duration,
                work_dir=finish_work_dir,
                burn_subtitles=options.burn_subtitles,
                soft_glow=options.soft_glow,
                beat_flash=options.beat_flash,
                write_review=options.write_review,
            )
        )
        manifest.append("stage.complete", stage="finish", report=finish_report)

        production_report = {
            "output": str(output_path),
            "base": str(base_path),
            "cutlist": str(cutlist_path),
            "bgm": str(options.bgm_path.resolve()) if options.bgm_path else None,
            "manifest": str(manifest.path),
            "finish_report": finish_report,
        }
        report_path = output_path.with_suffix(".production-report.json")
        report_path.write_text(json.dumps(production_report, ensure_ascii=False, indent=2), encoding="utf-8")
        production_report["report"] = str(report_path)
        manifest.append("production.complete", report=report_path, output=output_path)
        return production_report
    except Exception as exc:
        manifest.append("production.error", error=str(exc))
        raise


def options_from_cli(
    *,
    cutlist: str,
    out: str,
    bgm: str | None,
    duration: float | None,
    profile: str,
    work_dir: str | None,
    manifest: str | None,
    beat_align: bool,
    beat_tolerance: float,
    resume: bool = False,
    probe_assets: bool = True,
    burn_subtitles: bool,
    soft_glow: bool,
    beat_flash: bool,
    write_review: bool,
) -> ProductionOptions:
    return ProductionOptions(
        cutlist_path=Path(cutlist),
        output_path=Path(out),
        bgm_path=Path(bgm) if bgm else None,
        target_duration=duration,
        profile_name=profile,
        work_dir=Path(work_dir) if work_dir else None,
        manifest_path=Path(manifest) if manifest else None,
        beat_align=beat_align,
        beat_tolerance=beat_tolerance,
        resume=resume,
        probe_assets=probe_assets,
        burn_subtitles=burn_subtitles,
        soft_glow=soft_glow,
        beat_flash=beat_flash,
        write_review=write_review,
    )


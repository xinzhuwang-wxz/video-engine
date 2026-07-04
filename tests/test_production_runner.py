from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from video_engine.production import CommandRecord, ProductionOptions, run_cutlist_production


class ProductionRunnerTests(unittest.TestCase):
    def test_runner_orders_validate_render_finish_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mp4"
            source.write_bytes(b"fake")
            cutlist = root / "cutlist.json"
            cutlist.write_text(
                json.dumps(
                    {
                        "note_id": "unit",
                        "segments": [
                            {
                                "seq": 1,
                                "main": {"file": str(source), "in": 0, "out": 1.5},
                                "subtitle": "起",
                                "rationale": "unit test",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "out.mp4"
            manifest = root / "manifest.jsonl"
            calls: list[list[str]] = []

            def fake_runner(cmd: list[str], cwd: Path) -> CommandRecord:
                calls.append(cmd)
                if cmd[1].endswith("render_cutlist.py"):
                    Path(cmd[cmd.index("--out") + 1]).write_bytes(b"base")
                return CommandRecord(cmd=cmd, stdout="ok", stderr="")

            fake_finish_report = {
                "output": str(output),
                "probe": {"streams": []},
                "audio": {},
                "review_sheet": None,
                "report": str(output.with_suffix(".finish-report.json")),
            }

            with mock.patch("video_engine.production.finish_cutlist", return_value=fake_finish_report):
                report = run_cutlist_production(
                    ProductionOptions(
                        cutlist_path=cutlist,
                        output_path=output,
                        target_duration=1.5,
                        manifest_path=manifest,
                    ),
                    command_runner=fake_runner,
                )

            scripts = [Path(call[1]).name for call in calls]
            self.assertEqual(scripts, ["validate_cutlist.py", "render_cutlist.py"])
            self.assertEqual(report["output"], str(output.resolve()))
            self.assertTrue(manifest.exists())
            events = [json.loads(line)["event"] for line in manifest.read_text(encoding="utf-8").splitlines()]
            self.assertIn("production.start", events)
            self.assertIn("production.complete", events)

    def test_runner_includes_beat_align_when_bgm_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mp4"
            source.write_bytes(b"fake")
            bgm = root / "bgm.wav"
            bgm.write_bytes(b"fake")
            cutlist = root / "cutlist.json"
            cutlist.write_text(
                json.dumps(
                    {
                        "note_id": "unit",
                        "segments": [
                            {
                                "seq": 1,
                                "main": {"file": str(source), "in": 0, "out": 1.5},
                                "subtitle": "起",
                                "rationale": "unit test",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            calls: list[list[str]] = []

            def fake_runner(cmd: list[str], cwd: Path) -> CommandRecord:
                calls.append(cmd)
                if cmd[1].endswith("render_cutlist.py"):
                    Path(cmd[cmd.index("--out") + 1]).write_bytes(b"base")
                return CommandRecord(cmd=cmd, stdout="ok", stderr="")

            with mock.patch("video_engine.production.finish_cutlist", return_value={"output": str(root / "out.mp4")}):
                run_cutlist_production(
                    ProductionOptions(
                        cutlist_path=cutlist,
                        output_path=root / "out.mp4",
                        bgm_path=bgm,
                        target_duration=1.5,
                        manifest_path=root / "manifest.jsonl",
                    ),
                    command_runner=fake_runner,
                )

            scripts = [Path(call[1]).name for call in calls]
            self.assertEqual(
                scripts,
                ["validate_cutlist.py", "beat_align.py", "validate_cutlist.py", "render_cutlist.py"],
            )


if __name__ == "__main__":
    unittest.main()


class ResumeAndProbeTests(unittest.TestCase):
    def test_probe_flag_appends_to_validate_cmd(self) -> None:
        calls = []

        def runner(cmd, cwd):
            calls.append(cmd)
            return CommandRecord(cmd=cmd, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            cutlist = Path(tmp) / "cutlist.json"
            cutlist.write_text(json.dumps({"note_id": "t", "segments": [
                {"seq": 1, "main": {"file": "x.mp4", "in": 0, "out": 1}, "rationale": "r"}]}), encoding="utf-8")
            out = Path(tmp) / "out.mp4"
            try:
                run_cutlist_production(ProductionOptions(
                    cutlist_path=cutlist, output_path=out, probe_assets=True,
                    burn_subtitles=False, write_review=False), command_runner=runner)
            except Exception:
                pass  # finish 阶段真跑 ffmpeg 会失败,不影响本断言
        validate_calls = [c for c in calls if any("validate_cutlist" in str(x) for x in c)]
        self.assertTrue(validate_calls and "--probe" in validate_calls[0])

    def test_resume_skips_render_when_base_is_fresh(self) -> None:
        calls = []

        def runner(cmd, cwd):
            calls.append(cmd)
            return CommandRecord(cmd=cmd, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            cutlist = Path(tmp) / "cutlist.json"
            cutlist.write_text(json.dumps({"note_id": "t", "segments": [
                {"seq": 1, "main": {"file": "x.mp4", "in": 0, "out": 1}, "rationale": "r"}]}), encoding="utf-8")
            out = Path(tmp) / "out.mp4"
            base = Path(tmp) / "out.base.mp4"
            base.write_bytes(b"stub")  # base 比剪单新
            try:
                run_cutlist_production(ProductionOptions(
                    cutlist_path=cutlist, output_path=out, resume=True,
                    burn_subtitles=False, write_review=False), command_runner=runner)
            except Exception:
                pass
        self.assertFalse([c for c in calls if any("render_cutlist" in str(x) for x in c)],
                         "resume 下不应调用 render_cutlist")


class CliWiringTests(unittest.TestCase):
    def test_options_from_cli_accepts_all_flags(self) -> None:
        from video_engine.production import options_from_cli
        opts = options_from_cli(
            cutlist="c.json", out="o.mp4", bgm=None, duration=None, profile="douyin_vertical",
            work_dir=None, manifest=None, beat_align=True, beat_tolerance=0.15,
            burn_subtitles=True, soft_glow=True, beat_flash=True, write_review=True,
            resume=True, probe_assets=False, promise_gate=False)
        self.assertTrue(opts.resume); self.assertFalse(opts.probe_assets); self.assertFalse(opts.promise_gate)

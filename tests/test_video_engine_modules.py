from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from video_engine.cutlist import load_cutlist, timeline_duration, timeline_from_cutlist
from video_engine.finisher import options_from_names
from video_engine.media_profiles import get_profile


class CutlistTimelineTests(unittest.TestCase):
    def test_timeline_accounts_for_speed_and_subtitles(self) -> None:
        cutlist = {
            "note_id": "unit",
            "segments": [
                {
                    "seq": 1,
                    "main": {"file": "a.mp4", "in": 1.0, "out": 3.0, "speed": 1.0},
                    "subtitle": "起",
                    "rationale": "first",
                },
                {
                    "seq": 2,
                    "main": {"file": "b.mp4", "in": 0.0, "out": 4.0, "speed": 2.0},
                    "subtitle": "承",
                },
            ],
        }

        timeline = timeline_from_cutlist(cutlist)

        self.assertEqual([item.seq for item in timeline], [1, 2])
        self.assertEqual([item.subtitle for item in timeline], ["起", "承"])
        self.assertAlmostEqual(timeline[0].start, 0.0)
        self.assertAlmostEqual(timeline[0].end, 2.0)
        self.assertAlmostEqual(timeline[1].start, 2.0)
        self.assertAlmostEqual(timeline[1].end, 4.0)
        self.assertAlmostEqual(timeline_duration(timeline), 4.0)

    def test_load_cutlist_rejects_missing_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"note_id": "bad"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_cutlist(path)


class ProfileAndOptionsTests(unittest.TestCase):
    def test_profile_registry_has_douyin_vertical(self) -> None:
        profile = get_profile("douyin_vertical")

        self.assertEqual(profile.width, 1080)
        self.assertEqual(profile.height, 1920)
        self.assertEqual(profile.fps, 30)

    def test_options_from_names_resolves_paths_and_flags(self) -> None:
        options = options_from_names(
            input_path="base.mp4",
            cutlist_path="cutlist.json",
            output_path="out.mp4",
            target_duration=15.0,
            burn_subtitles=False,
            soft_glow=False,
        )

        self.assertEqual(options.profile.name, "douyin_vertical")
        self.assertEqual(options.target_duration, 15.0)
        self.assertFalse(options.burn_subtitles)
        self.assertFalse(options.soft_glow)


if __name__ == "__main__":
    unittest.main()


class BuildFilterTests(unittest.TestCase):
    def _timeline(self, subtitles=("你好", "")):
        from video_engine.cutlist import TimelineSegment
        segs, cursor = [], 0.0
        for i, sub in enumerate(subtitles, 1):
            segs.append(TimelineSegment(seq=i, start=cursor, end=cursor + 2.0, subtitle=sub, source_file=f"s{i}.mp4"))
            cursor += 2.0
        return segs

    def test_filter_graph_shapes(self) -> None:
        from video_engine.finisher import _build_filter
        from video_engine.media_profiles import get_profile
        prof = get_profile("douyin_vertical")
        tl = self._timeline()
        full = _build_filter(tl, [], prof, 4.0, subtitle_y=1400, soft_glow=True, beat_flash=True, has_audio=True)
        self.assertIn("[vout]", full); self.assertIn("[aout]", full)
        self.assertIn("gblur", full); self.assertIn("drawbox", full); self.assertIn("[0:a:0]", full)
        bare = _build_filter(tl, [], prof, 4.0, subtitle_y=1400, soft_glow=False, beat_flash=False, has_audio=False)
        self.assertNotIn("gblur", bare); self.assertNotIn("drawbox", bare)
        self.assertIn("anullsrc", bare); self.assertNotIn("[0:a:0]", bare)  # 无音频输入→静音轨,绝不引用 a:0

    def test_single_segment_has_no_flash_window(self) -> None:
        from video_engine.finisher import _build_filter
        from video_engine.media_profiles import get_profile
        one = self._timeline(subtitles=("",))
        out = _build_filter(one, [], get_profile("douyin_vertical"), 2.0, subtitle_y=1400,
                            soft_glow=False, beat_flash=True, has_audio=True)
        self.assertNotIn("drawbox", out)  # 单段无切点,不应有闪白


class PromiseCheckTests(unittest.TestCase):
    def test_promise_catches_missing_segment_and_subtitle(self) -> None:
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "promise_check", pathlib.Path(__file__).resolve().parents[1] / "scripts/promise_check.py")
        pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
        sb = {"total_duration": 4, "segments": [
            {"seq": 1, "duration": 2, "subtitle": "你好"}, {"seq": 2, "duration": 2}]}
        cl = {"segments": [{"seq": 1, "main": {"file": "a.mp4", "in": 0, "out": 2}, "subtitle": None}]}
        errs, _ = pc.check(sb, cl)
        self.assertTrue(any("缺失" in e for e in errs))
        self.assertTrue(any("字幕" in e for e in errs))
        good = {"segments": [
            {"seq": 1, "main": {"file": "a.mp4", "in": 0, "out": 2}, "subtitle": "你好"},
            {"seq": 2, "main": {"file": "b.mp4", "in": 1, "out": 3}}]}
        errs2, _ = pc.check(sb, good)
        self.assertEqual(errs2, [])

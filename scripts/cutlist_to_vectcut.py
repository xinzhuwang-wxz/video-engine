#!/usr/bin/env python3
"""剪单物化(正宗路线):cutlist JSON → VectCutAPI(官方 HTTP :9001) → 剪映草稿(带手艺)。

这是"成熟基座上的二次开发"胶水:决策(剪单)是我们的契约,执行全走官方引擎——
转场(362种)/滤镜(468种,经本地补丁透传)/关键帧缓推/BGM轨/字幕。
剪映=本地前端;draft_url=云预览入口(需开上传,默认关)。

剪单手艺字段(v2 扩展):
  cutlist.grade = {"filter":"清透","intensity":70}      # 全片滤镜
  seg.main.transition = "叠化" / seg.main.transition_duration
  seg.push_in = {"from":1.0,"to":1.06}                  # 该段缓推(uniform_scale 关键帧)
  cutlist.bgm = {"file":"...","volume":0.8}

用法: python3 cutlist_to_vectcut.py <cutlist.json> [--server http://localhost:9001] [--draft-root <剪映草稿目录>]
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ORIG_CWD = Path.cwd()
DEFAULT_DRAFT_ROOT = str(Path.home() / "Movies/JianyingPro/User Data/Projects/com.lveditor.draft")


def call(server: str, ep: str, payload: dict) -> dict:
    req = urllib.request.Request(f"{server}/{ep}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode())
    if not out.get("success"):
        raise RuntimeError(f"{ep} 失败: {out.get('error')}")
    return out.get("output") or {}


def _abs(f: str) -> str:
    p = Path(f)
    return str(p if p.is_absolute() else ORIG_CWD / p)


def materialize(cutlist: dict, server: str, draft_root: str) -> dict:
    canvas = cutlist.get("canvas") or {}
    W, H = canvas.get("width", 1080), canvas.get("height", 1920)
    grade = cutlist.get("grade") or {}
    d = call(server, "create_draft", {"width": W, "height": H})
    draft_id = d["draft_id"]

    cursor, pushes, texts = 0.0, [], []
    for seg in cutlist["segments"]:
        m = seg["main"]
        speed = m.get("speed", 1.0)
        dur = (m["out"] - m["in"]) / speed
        if (seg.get("subtitle") or "").strip():
            texts.append((seg["subtitle"].strip(), cursor, cursor + dur))
        payload = {"draft_id": draft_id, "video_url": _abs(m["file"]), "draft_folder": draft_root,
                   "width": W, "height": H, "start": m["in"], "end": m["out"],
                   "target_start": cursor, "speed": speed, "volume": m.get("volume", 1.0),
                   "track_name": "实拍"}
        if m.get("transition"):
            payload["transition"] = m["transition"]
            payload["transition_duration"] = m.get("transition_duration", 0.4)
        if grade.get("filter"):
            payload["filter_type"] = grade["filter"]
            payload["filter_intensity"] = grade.get("intensity", 100.0)
        call(server, "add_video", payload)
        if seg.get("push_in"):
            pushes.append((cursor, cursor + dur, seg["push_in"]))
        cursor += dur

    for t0, t1, p in pushes:  # 缓推:段首尾两个 uniform_scale 关键帧
        call(server, "add_video_keyframe", {"draft_id": draft_id, "track_name": "实拍",
             "property_types": ["uniform_scale", "uniform_scale"],
             "times": [t0 + 0.01, t1 - 0.01],
             "values": [str(p.get("from", 1.0)), str(p.get("to", 1.06))]})

    for txt, t0, t1 in texts:  # 旁白/字幕 → 官方 /add_text(底部居中)
        call(server, "add_text", {"draft_id": draft_id, "text": txt, "start": round(t0, 3),
             "end": round(t1, 3), "font_size": 8.0, "transform_y": -0.75,
             "track_name": "字幕", "font_color": "#FFFFFF"})

    bgm = cutlist.get("bgm")
    if bgm:
        call(server, "add_audio", {"draft_id": draft_id, "audio_url": _abs(bgm["file"]),
             "draft_folder": draft_root, "start": 0, "end": round(cursor, 3),
             "target_start": 0, "volume": bgm.get("volume", 0.8), "track_name": "BGM"})

    call(server, "save_draft", {"draft_id": draft_id, "draft_folder": draft_root})
    return {"draft_id": draft_id, "draft_dir": str(Path(draft_root) / draft_id),
            "preview_url": d.get("draft_url", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cutlist")
    ap.add_argument("--server", default="http://localhost:9001")
    ap.add_argument("--draft-root", default=DEFAULT_DRAFT_ROOT)
    args = ap.parse_args()
    p = Path(args.cutlist)
    if not p.is_absolute():
        p = ORIG_CWD / p
    result = materialize(json.loads(p.read_text()), args.server, args.draft_root)
    print(json.dumps(result, ensure_ascii=False))
    ok = (Path(result["draft_dir"]) / "draft_content.json").exists() or \
         (Path(result["draft_dir"]) / "draft_info.json").exists()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

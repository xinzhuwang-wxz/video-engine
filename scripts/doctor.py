#!/usr/bin/env python3
"""环境体检(preflight):一眼看清哪条能力可用、缺什么、怎么补。

学自 OpenMontage 的 preflight/doctor 思想(自实现,无代码借用):失败要发生在开工前,
而不是渲染到一半。零依赖(stdlib),任何 agent/人都能跑。

用法: python3 scripts/doctor.py [--json]
退出码: 0=核心能力齐(可剪辑) 1=核心缺失
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

VE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VE))


def _check(name: str, ok: bool, detail: str, fix: str = "", level: str = "core") -> dict:
    return {"name": name, "ok": ok, "detail": detail, "fix": fix, "level": level}


def _has_filter(name: str) -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, timeout=15)
        return any(f" {name} " in line for line in r.stdout.splitlines())
    except Exception:
        return False


def run_checks() -> list[dict]:
    checks: list[dict] = []

    # 1. ffmpeg / ffprobe(剪辑硬前提)
    ff = shutil.which("ffmpeg")
    checks.append(_check("ffmpeg", bool(ff), ff or "未找到", "brew install ffmpeg"))
    checks.append(_check("ffprobe", bool(shutil.which("ffprobe")), shutil.which("ffprobe") or "未找到", "随 ffmpeg 安装"))

    # 2. 字幕能力(libass 硬烧 / Pillow PNG 兜底)
    libass = _has_filter("subtitles")
    try:
        import PIL  # noqa: F401
        pillow = True
    except ImportError:
        pillow = False
    checks.append(_check("字幕·libass 硬烧", libass, "有 subtitles 滤镜" if libass else "ffmpeg 精简版无 libass",
                         "brew reinstall ffmpeg(完整版)", level="optional"))
    checks.append(_check("字幕·Pillow PNG 兜底", pillow, "Pillow 可用" if pillow else "未安装",
                         "pip install Pillow", level="optional" if libass else "core"))

    # 3. CJK 字体(PNG 字幕需要)
    from video_engine.finisher import FONT_CANDIDATES  # noqa: PLC0415
    font = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
    checks.append(_check("CJK 字体", bool(font), font or "候选路径均不存在", "安装 Noto Sans CJK 或 --font 指定", level="optional"))

    # 4. 基座(vendor + 补丁 + 服务)
    vendor = VE / "vendor/CapCutAPI"
    checks.append(_check("基座 vendor", (vendor / "capcut_server.py").exists(), str(vendor), "bash setup.sh"))
    patched = (vendor / "add_video_track.py").exists() and "filter_type" in (vendor / "add_video_track.py").read_text(errors="ignore")
    checks.append(_check("基座补丁(滤镜透传)", patched, "已应用" if patched else "未应用", "bash setup.sh 或见 patches/README.md", level="optional"))
    try:
        req = urllib.request.Request("http://localhost:9001/create_draft", data=b'{"width":720,"height":1280}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as r:
            server_ok = b"success" in r.read()
    except Exception:
        server_ok = False
    checks.append(_check("引擎服务 :9001", server_ok, "在线" if server_ok else "未启动",
                         "cd vendor/CapCutAPI && .venv/bin/python capcut_server.py &", level="optional"))

    # 5. 生成能力(可选:没有也能剪)
    env_file = (VE / ".env").read_text() if (VE / ".env").exists() else ""
    key = bool(os.environ.get("ARK_API_KEY")) or any(
        l.startswith("ARK_API_KEY=") and len(l.split("=", 1)[1].strip()) > 8 for l in env_file.splitlines())
    checks.append(_check("生成·ARK_API_KEY", bool(key), "已配置" if key else "未配置(纯剪辑不需要)",
                         "火山方舟控制台创建,填入 .env", level="optional"))

    # 6. 剪映草稿根(质量出口)
    draft_root = Path.home() / "Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
    checks.append(_check("剪映草稿目录", draft_root.exists(), str(draft_root) if draft_root.exists() else "未见(未装剪映?)",
                         "安装剪映专业版;或只用 ffmpeg 出口", level="optional"))

    return checks


def main() -> None:
    as_json = "--json" in sys.argv
    checks = run_checks()
    core_ok = all(c["ok"] for c in checks if c["level"] == "core")
    if as_json:
        print(json.dumps({"core_ok": core_ok, "checks": checks}, ensure_ascii=False, indent=1))
    else:
        for c in checks:
            mark = "✅" if c["ok"] else ("❌" if c["level"] == "core" else "⚠️ ")
            line = f" {mark} {c['name']}: {c['detail']}"
            if not c["ok"] and c["fix"]:
                line += f"  → {c['fix']}"
            print(line)
        print(f"\n{'✅ 核心能力齐,可以开工' if core_ok else '❌ 核心能力缺失,先按提示补齐'}(⚠️ 为可选能力,缺了走降级路径)")
    sys.exit(0 if core_ok else 1)


if __name__ == "__main__":
    main()

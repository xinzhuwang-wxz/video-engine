#!/usr/bin/env bash
# video-engine 一键安装:克隆基座 → 打补丁 → 建环境 → 冒烟验证
set -euo pipefail
cd "$(dirname "$0")"
echo "① 克隆基座 VectCutAPI(2039★)…"
[ -d vendor/CapCutAPI/.git ] || git clone --depth 1 https://github.com/sun-guannan/VectCutAPI.git vendor/CapCutAPI
echo "② 应用本地补丁(滤镜透传等)…"
(cd vendor/CapCutAPI && for p in ../../patches/*.patch; do git apply --check "$p" 2>/dev/null && git apply "$p" && echo "  ✓ $(basename $p)" || echo "  · $(basename $p) 已应用或需手工重放(见 patches/README.md)"; done)
echo "③ Python 环境…"
(cd vendor/CapCutAPI && { command -v uv >/dev/null && uv venv .venv -q && uv pip install -q -r requirements.txt --python .venv/bin/python; } || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; })
[ -f vendor/CapCutAPI/config.json ] || sed 's/"draft_profile": "capcut_legacy"/"draft_profile": "jianying_pro_10"/' vendor/CapCutAPI/config.json.example > vendor/CapCutAPI/config.json 2>/dev/null || true
[ -f .env ] || cp .env.example .env
echo "④ 冒烟…"; bash evals/video_smoke.sh
echo "完成。起引擎服务: cd vendor/CapCutAPI && .venv/bin/python capcut_server.py  (:9001)"

#!/usr/bin/env bash
# video-engine 离线冒烟:零 API、零网络、可重复。改动 video-engine/ 或升级 vendor 后必跑。
# 覆盖: 剪单校验(正例) → seedance dry-run → 剪单物化(临时草稿根) → draft_info.json 结构断言 → 清理
set -euo pipefail
cd "$(dirname "$0")/.."   # 插件根
VE=.
PY="$VE/vendor/CapCutAPI/.venv/bin/python"
[ -x "$PY" ] || { echo "SKIP: CapCutAPI venv 未装(cd $VE/vendor/CapCutAPI && uv venv .venv && uv pip install -r requirements.txt)"; exit 0; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 1. 测试片(ffmpeg 纯色,不依赖 drawtext)
ffmpeg -v error -y -f lavfi -i "color=c=0x2266aa:s=1080x1920:d=4" -c:v libx264 -pix_fmt yuv420p "$TMP/s01_shipai.mp4"
ffmpeg -v error -y -f lavfi -i "color=c=0xaa4422:s=1080x1920:d=4" -c:v libx264 -pix_fmt yuv420p "$TMP/s01_ai.mp4"

# 2. 剪单(两段:实拍裁切 + AI片直接当主轨混剪)
cat > "$TMP/cutlist.json" <<EOF
{"note_id":"_SMOKE","sku":"GY-SMOKE","canvas":{"width":1080,"height":1920},"segments":[
 {"seq":1,"main":{"file":"$TMP/s01_shipai.mp4","in":1.0,"out":3.0},"ai_ref":{"file":"$TMP/s01_ai.mp4","in":0.0,"out":2.0},"subtitle":"冒烟段1","rationale":"取1-3s"},
 {"seq":2,"main":{"file":"$TMP/s01_ai.mp4","in":0.5,"out":2.5},"ai_ref":null,"rationale":"AI片混剪"}]}
EOF
python3 "$VE/scripts/validate_cutlist.py" "$TMP/cutlist.json"

# 2.5 分镜校验器(video-storyboard 契约)
cat > "$TMP/sb.json" <<'EOF'
{"note_id":"_SMOKE","total_duration":10,"segments":[
 {"seq":1,"scene":"冒烟画面","line":"冒烟台词","duration":3,"first_frame_hint":"上身图","previz_prompt":"冒烟提示词"},
 {"seq":2,"scene":"冒烟画面2","subtitle":"冒烟字幕","duration":7,"first_frame_hint":"细节图","previz_prompt":"冒烟提示词2"}]}
EOF
python3 "$VE/skills/video-storyboard/scripts/validate_storyboard.py" "$TMP/sb.json"

# 2.7 交付承诺门(正:兑现 / 反:删段被拦)
cat > "$TMP/sb_promise.json" <<'EOF2'
{"total_duration":4,"segments":[{"seq":1,"duration":2,"subtitle":"冒烟字幕"},{"seq":2,"duration":2}]}
EOF2
python3 "$VE/scripts/promise_check.py" "$TMP/sb_promise.json" "$TMP/cutlist.json" >/dev/null 2>&1 && echo "✓ 承诺门正例通过"
python3 - "$TMP" <<'EOF2'
import json,sys,pathlib
t=pathlib.Path(sys.argv[1]); cl=json.loads((t/"cutlist.json").read_text()); del cl["segments"][1]
(t/"cutlist_broken.json").write_text(json.dumps(cl))
EOF2
if python3 "$VE/scripts/promise_check.py" "$TMP/sb_promise.json" "$TMP/cutlist_broken.json" >/dev/null 2>&1; then
  echo "✗ 承诺门反例未拦截"; exit 1
else echo "✓ 承诺门反例被拦"; fi

# 3. seedance dry-run(离线构造请求体)
cat > "$TMP/segs.json" <<'EOF'
[{"seq":1,"prompt":"冒烟测试提示词","duration":5}]
EOF
python3 "$VE/scripts/seedance_gen.py" --segments "$TMP/segs.json" --sku GY-SMOKE --note SMOKE --out-root "$TMP/lib" --dry-run > /dev/null

# 3.5 ffmpeg 直出成片(agent 主剪链路)+ 时长断言
OUT=$(python3 "$VE/scripts/render_cutlist.py" "$TMP/cutlist.json" --preview --out "$TMP/preview.mp4" 2>/dev/null | tail -1)
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
python3 -c "assert abs($DUR-4.0)<0.5, '成片时长应≈4s,实际 $DUR'; print('✓ 渲染时长断言通过')"

# 4. 物化(基座 VectCutAPI 官方服务;server 不在则 SKIP 本步)
if curl -s -m 2 -X POST http://localhost:9001/create_draft -H 'Content-Type: application/json' -d '{"width":720,"height":1280}' | grep -q success; then
  OUT=$(python3 "$VE/scripts/cutlist_to_vectcut.py" "$TMP/cutlist.json" --draft-root "$TMP/drafts")
  DRAFT=$(python3 -c "import json,sys;print(json.loads('$OUT'.replace(chr(10),''))['draft_dir'])" 2>/dev/null || echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)['draft_dir'])")
  python3 - "$DRAFT" <<'PYEOF'
import json, sys, pathlib
f = pathlib.Path(sys.argv[1]) / "draft_content.json"
d = json.loads(f.read_text())
vt = [t for t in d["tracks"] if t.get("type")=="video" and t.get("segments")]
assert vt and len(vt[0]["segments"]) == 2, "实拍轨应2段"
print("✓ vectcut 物化断言通过")
PYEOF
else
  echo "· SKIP vectcut 物化(9001 未启动;起服务后重跑覆盖)"
fi

echo "✓ video_smoke 全部断言通过"

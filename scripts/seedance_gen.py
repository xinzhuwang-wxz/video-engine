#!/usr/bin/env python3
"""previz 生成:分镜段 JSON → 火山方舟视频生成任务(Seedance 系) → 按命名规约落盘。

与剪辑层解耦:本脚本只负责"产出守命名规约的 mp4",换模型(Seedance/即梦/Sora/可灵…)
只需换 adapter 或 SEEDANCE_MODEL,下游 video-editing 技能不感知。

输入 segments JSON: [{"seq":1, "prompt":"…", "first_frame":"<本地图路径或http url>", "duration":5}]
输出: {out_root}/{SKU}/02-AI生成/{SKU}-{NOTE}-S{nn}_AI.mp4 + 结果 JSON(stdout)

用法:
  python3 seedance_gen.py --segments segs.json --sku GY-003 --note PQ-012 [--out-root ~/素材库] [--dry-run]
环境: ARK_API_KEY(必须,dry-run 除外) SEEDANCE_MODEL(默认 doubao-seedance-1-0-lite-i2v-250428)
      ARK_BASE(默认 https://ark.cn-beijing.volces.com/api/v3)
依赖: 仅标准库(urllib)。
"""
import argparse
import base64
import json
import math
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _load_dotenv():
    """轻量 .env 加载(仓库根),不覆盖已有环境变量。"""
    for parent in Path(__file__).resolve().parents:
        env = parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return


_load_dotenv()
ARK_BASE = os.environ.get("ARK_BASE", "https://ark.cn-beijing.volces.com/api/v3")
MODEL = os.environ.get("SEEDANCE_MODEL", "doubao-seedance-1-0-lite-i2v-250428")
IS_V2 = "seedance-2" in MODEL  # 2.0 系:参数走 JSON 字段;1.0 系:参数走提示词后缀
POLL_SEC, TIMEOUT_SEC = 5, 900


# 方舟是国内直连服务:绕过本机代理(host 挂着 127.0.0.1:10820,高并发下 503 Too many open connections)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _req(method: str, url: str, payload: dict | None = None, retries: int = 3) -> dict:
    key = os.environ.get("ARK_API_KEY")
    if not key:
        raise RuntimeError("缺 ARK_API_KEY(.env 或环境变量;火山方舟控制台获取)")
    data = json.dumps(payload).encode() if payload is not None else None
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with _OPENER.open(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Ark API {e.code}: {body}") from None  # 4xx/5xx带体,不重试
        except (urllib.error.URLError, OSError, TimeoutError) as e:  # 网络瞬时错误:退避重试
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"网络重试{retries}次仍失败: {last_err}")


def _image_url(path_or_url: str) -> str:
    """本地图转 data URL;http(s) 原样传。"""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    p = Path(path_or_url)
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def build_request(seg: dict, resolution: str = "720p", ratio: str = "9:16",
                  audio: bool = False) -> dict:
    """一段分镜 → 一个任务请求体。
    Seedance 1.0 系:参数跟在 prompt 后(--resolution 等文本命令);
    Seedance 2.0 系(含 mini):ratio/duration/generate_audio/watermark 走 JSON 顶层字段,
    图片参考 role=reference_image(最多9图),支持 reference_video/audio。
    生成时长 = ceil(分镜时长),多出的零头由剪单 in/out 裁掉(生成留余量,剪辑取精确)。"""
    # mini 实测:duration 下限 4s(400 InvalidParameter);生成留余量,剪单裁精确
    dur = max(4, min(15, math.ceil(float(seg.get("duration", 5)))))
    if IS_V2:
        content: list[dict] = [{"type": "text", "text": seg["prompt"]}]
        for img in (seg.get("ref_images") or ([seg["first_frame"]] if seg.get("first_frame") else [])):
            content.append({"type": "image_url", "role": "reference_image",
                            "image_url": {"url": _image_url(img)}})
        return {"model": MODEL, "content": content, "ratio": ratio, "duration": dur,
                "generate_audio": audio, "watermark": False}
    text = f"{seg['prompt']} --resolution {resolution} --duration {dur} --watermark false"
    content = [{"type": "text", "text": text}]
    if seg.get("first_frame"):
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": _image_url(seg["first_frame"])}})
    return {"model": MODEL, "content": content}


def run_segment(seg: dict, out_path: Path, resolution: str = "720p", ratio: str = "9:16", audio: bool = False) -> dict:
    body = build_request(seg, resolution, ratio, audio)
    task = _req("POST", f"{ARK_BASE}/contents/generations/tasks", body)
    task_id = task.get("id") or task.get("task_id")
    if not task_id:
        return {"seq": seg["seq"], "ok": False, "error": f"建任务失败: {task}"}
    t0 = time.time()
    while time.time() - t0 < TIMEOUT_SEC:
        time.sleep(POLL_SEC)
        st = _req("GET", f"{ARK_BASE}/contents/generations/tasks/{task_id}")
        status = st.get("status")
        if status == "succeeded":
            video_url = (st.get("content") or {}).get("video_url")
            if not video_url:
                return {"seq": seg["seq"], "ok": False, "error": f"无 video_url: {st}"}
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with _OPENER.open(video_url, timeout=300) as resp:  # 下载也绕代理,链接有时效立即下载
                out_path.write_bytes(resp.read())
            usage = st.get("usage") or {}
            return {"seq": seg["seq"], "ok": True, "file": str(out_path),
                    "task_id": task_id, "tokens": usage.get("total_tokens")}
        if status in ("failed", "cancelled"):
            return {"seq": seg["seq"], "ok": False, "error": str(st.get("error") or status)}
    return {"seq": seg["seq"], "ok": False, "error": "轮询超时"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--sku", required=True)
    ap.add_argument("--note", required=True)
    ap.add_argument("--out-root", default=os.environ.get("ASSET_ROOT", str(Path.home() / "素材库")))
    ap.add_argument("--resolution", default="720p", choices=["480p", "720p", "1080p"],
                    help="720p=参考级previz;1080p=成片级AI段(混剪直接进片,生成后须审帧)")
    ap.add_argument("--ratio", default="9:16", help="2.0系画幅(9:16竖屏/16:9/adaptive)")
    ap.add_argument("--audio", action="store_true", help="2.0系:生成音频(默认关,BGM归后期)")
    ap.add_argument("--dry-run", action="store_true", help="只打印请求体与目标路径,不调 API")
    args = ap.parse_args()

    segs = json.loads(Path(args.segments).read_text())
    results = []
    for seg in segs:
        out = Path(args.out_root) / args.sku / "02-AI生成" / f"{args.sku}-{args.note}-S{seg['seq']:02d}_AI.mp4"
        if out.exists() and not args.dry_run:  # 断点续跑:已生成的段跳过(重生成请先删文件或改名)
            results.append({"seq": seg["seq"], "ok": True, "file": str(out), "skipped": "已存在"})
            print(f"  段{seg['seq']}: ⏭ 已存在,跳过", file=sys.stderr)
            continue
        if args.dry_run:
            body = build_request(seg, args.resolution, args.ratio, args.audio)
            # 摘要打印,避免 base64 刷屏
            for c in body["content"]:
                if c["type"] == "image_url" and c["image_url"]["url"].startswith("data:"):
                    c["image_url"]["url"] = c["image_url"]["url"][:48] + f"...(base64,{len(c['image_url']['url'])}b)"
            results.append({"seq": seg["seq"], "dry_run": True, "would_write": str(out),
                            "model": MODEL, "request": body})
            continue
        try:  # 单段失败不拖死整批(断点续跑会补)
            results.append(run_segment(seg, out, args.resolution, args.ratio, args.audio))
        except Exception as e:
            results.append({"seq": seg["seq"], "ok": False, "error": str(e)[:300]})
        print(f"  段{seg['seq']}: {'✓ ' + results[-1].get('file', '') if results[-1]['ok'] else '✗ ' + results[-1]['error']}",
              file=sys.stderr)

    print(json.dumps({"sku": args.sku, "note": args.note, "results": results}, ensure_ascii=False, indent=2))
    sys.exit(0 if all(r.get("ok") or r.get("dry_run") for r in results) else 1)


if __name__ == "__main__":
    main()

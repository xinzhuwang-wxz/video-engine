# vendor 补丁纪律

vendor/CapCutAPI = github.com/sun-guannan/VectCutAPI(原名 CapCutAPI,2039★)的克隆,**本地补丁不提交进其 .git**。

## 现有补丁
- `0001-filter-passthrough.patch`:视频滤镜透传(add_video_track 暴露 filter_type/filter_intensity + capcut_server /add_video 路由透传)。上游 HTTP 层只有语音滤镜,无视频滤镜。PR 上游待用户批准(对外动作)。

## 升级 upstream 流程
```bash
cd video-engine/vendor/CapCutAPI
git stash && git pull && git stash pop   # 或: git checkout . && git pull && git apply ../../patches/*.patch
bash ../../../evals/video_smoke.sh       # 升级后必跑回归
```
补丁冲突时以 patch 文件为准手工重放,重放后重新 `git diff > 补丁文件` 刷新。

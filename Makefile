# video-engine · 常用入口(学自 OpenMontage 的 DX,自实现)
.PHONY: setup doctor test smoke server produce help

help:
	@echo "make setup    一键安装(克隆基座+补丁+环境+冒烟)"
	@echo "make doctor   环境体检(开工前跑,失败早暴露)"
	@echo "make test     单元测试"
	@echo "make smoke    离线冒烟回归(改动后必跑)"
	@echo "make server   起剪辑引擎 :9001"
	@echo "make produce CUTLIST=... OUT=... [BGM=...]   一键出片"
	@echo "make demo     零key演示(testdata,~20秒)"

setup:
	bash setup.sh

doctor:
	@python3 scripts/doctor.py

test:
	@python3 -m pytest tests/ -q 2>/dev/null || python3 -m unittest discover -s tests -q

smoke:
	@bash evals/video_smoke.sh

server:
	cd vendor/CapCutAPI && .venv/bin/python capcut_server.py

produce:
	@python3 scripts/produce_cutlist.py $(CUTLIST) --out $(OUT) $(if $(BGM),--bgm $(BGM))

demo:
	@echo "🎬 零key演示:testdata 两段测试片 → 校验→渲染→收尾(硬字幕/柔光/闪白)→体检报告"
	@python3 scripts/produce_cutlist.py testdata/cutlist_demo.json --out /tmp/ve_demo/demo.mp4
	@echo "── 产物 ──"; ls /tmp/ve_demo/ | sed 's/^/   /'
	@python3 -c "import json;r=json.load(open('/tmp/ve_demo/demo.finish-report.json'));print('   ✓',r['target_duration'],'s |',r['profile'],'| 硬字幕:',r['hard_subtitles'],'| review:',bool(r['review_sheet']))"

status:
	@python3 scripts/status.py $(WB)

# video-engine · 常用入口(学自 OpenMontage 的 DX,自实现)
.PHONY: setup doctor test smoke server produce help

help:
	@echo "make setup    一键安装(克隆基座+补丁+环境+冒烟)"
	@echo "make doctor   环境体检(开工前跑,失败早暴露)"
	@echo "make test     单元测试"
	@echo "make smoke    离线冒烟回归(改动后必跑)"
	@echo "make server   起剪辑引擎 :9001"
	@echo "make produce CUTLIST=... OUT=... [BGM=...]   一键出片"

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

status:
	@python3 scripts/status.py $(WB)

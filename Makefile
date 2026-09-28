PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
PY := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(PYTHON))

LOG_DIR := .logs
PID_DIR := $(LOG_DIR)/pids
POLL_INTERVAL_SECONDS ?= 15
export POLL_INTERVAL_SECONDS

STAGES := simulator preprocess train infer dashboard
STREAMLIT := $(PY) -m streamlit run pipeline/dashboard.py --server.port 8501 --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false

.PHONY: help install test config simulator preprocess train infer dashboard \
	run run-simulator run-preprocess run-train run-infer run-dashboard stop clean-data \
	docker-up docker-down docker-test

help:
	@echo "Foreground: make simulator | preprocess | train | infer | dashboard"
	@echo "Background stack: make run    Stop: make stop"
	@echo "Containers: make docker-up | docker-down | docker-test"
	@echo "Logs: $(LOG_DIR)/    PIDs: $(PID_DIR)/"
	@echo "Also: make install | test | config | clean-data"

install:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

config:
	$(PY) -c "from pipeline.config import load_config; from pipeline.paths import ensure_data_dirs; print(load_config()); print(ensure_data_dirs())"

simulator:
	$(PY) -m pipeline.simulator

preprocess:
	$(PY) -m pipeline.preprocess

train:
	$(PY) -m pipeline.train

infer:
	$(PY) -m pipeline.infer

dashboard:
	$(STREAMLIT)

start_bg = mkdir -p $(LOG_DIR) $(PID_DIR); pidfile=$(PID_DIR)/$(1).pid; if [ -f $$pidfile ] && kill -0 `cat $$pidfile` 2>/dev/null; then echo "$(1) already running (pid `cat $$pidfile`)"; else $(PY) -c 'import shlex,subprocess,sys; log=open(sys.argv[1],"a",buffering=1); p=subprocess.Popen(shlex.split(sys.argv[3]),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True); open(sys.argv[2],"w").write(str(p.pid)+"\n")' $(LOG_DIR)/$(1).log $$pidfile "$(2)"; echo "started $(1) pid `cat $$pidfile` — log $(LOG_DIR)/$(1).log"; fi

run-simulator:
	@$(call start_bg,simulator,$(PY) -m pipeline.simulator)

run-preprocess:
	@$(call start_bg,preprocess,$(PY) -m pipeline.preprocess)

run-train:
	@$(call start_bg,train,$(PY) -m pipeline.train)

run-infer:
	@$(call start_bg,infer,$(PY) -m pipeline.infer)

run-dashboard:
	@$(call start_bg,dashboard,$(STREAMLIT))

run: run-simulator run-preprocess run-train run-infer run-dashboard
	@echo "DashBite is up. Model Pulse: http://localhost:8501"
	@echo "Logs: $(LOG_DIR)/    PIDs: $(PID_DIR)/"
	@echo "Stop with: make stop"

stop:
	@mkdir -p $(PID_DIR)
	@for name in $(STAGES); do \
		pidfile=$(PID_DIR)/$$name.pid; \
		if [ ! -f $$pidfile ]; then \
			continue; \
		fi; \
		pid=$$(cat $$pidfile); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -TERM -$$pid 2>/dev/null || kill -TERM $$pid 2>/dev/null || true; \
			i=0; \
			while kill -0 $$pid 2>/dev/null && [ $$i -lt 10 ]; do \
				sleep 0.3; \
				i=$$((i + 1)); \
			done; \
			if kill -0 $$pid 2>/dev/null; then \
				kill -KILL -$$pid 2>/dev/null || kill -KILL $$pid 2>/dev/null || true; \
			fi; \
			echo "stopped $$name (pid $$pid)"; \
		else \
			echo "$$name was not running"; \
		fi; \
		rm -f $$pidfile; \
	done
	@if command -v lsof >/dev/null 2>&1; then \
		pids=$$(lsof -ti tcp:8501 2>/dev/null || true); \
		if [ -n "$$pids" ]; then \
			kill -TERM $$pids 2>/dev/null || true; \
			sleep 0.5; \
			kill -KILL $$pids 2>/dev/null || true; \
			echo "stopped leftover process on :8501"; \
		fi; \
	fi

clean-data:
	@alive=0; \
	for name in $(STAGES); do \
		pidfile=$(PID_DIR)/$$name.pid; \
		if [ -f $$pidfile ] && kill -0 $$(cat $$pidfile) 2>/dev/null; then \
			alive=1; \
		fi; \
	done; \
	if [ $$alive -eq 1 ]; then \
		echo "Run make stop before make clean-data"; \
		exit 1; \
	fi
	rm -rf data/raw data/features data/models data/predictions data/quality
	@echo "removed data directories"

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-test:
	docker compose run --rm --no-deps test

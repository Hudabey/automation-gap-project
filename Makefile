PY ?= .venv/bin/python

all:
	cd 1-motors-drives && ../$(PY) motors_drives.py
	cd 2-sensors-filtering && ../$(PY) sensors_filtering.py
	cd 3-state-machine && ../$(PY) tank_fsm.py
	cd 4-modbus-tcp && ../$(PY) modbus_tcp.py > results.txt && cat results.txt

venv:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

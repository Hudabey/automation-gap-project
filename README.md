# Automation Gap Project

Hudeifa Hassan · Constructor University Matriculation No. 30010819

Four short exercises covering the CO-543 Automation topics that SRH BST-BCS-09
(Siemens Mechatronic Systems Certification, PLC programming in TIA Portal) covered only
partly or not at all.

| CO-543 topic | Part | What it shows |
| --- | --- | --- |
| Actuators: electric motors and drives | [1-motors-drives](1-motors-drives/) | DC motor speed control; induction motor equivalent circuit and torque–speed curve; inverter V/f control with voltage boost; sizing the conveyor drive of the PLC exercise |
| Sensors: calibration, accuracy vs. precision | [2-sensors-filtering](2-sensors-filtering/) | Bias vs. noise of a 0–10 bar transmitter on an S7 analog input; two-point vs. least-squares calibration |
| Filtering, estimation and data fusion, with stability | [2-sensors-filtering](2-sensors-filtering/) | Moving average vs. exponential filter (pole, stability limit); 1-D Kalman filter; inverse-variance fusion of two sensors |
| State machines; specification → automation design; automation pyramid | [3-state-machine](3-state-machine/) | The tank process of the PLC exercise as a tested state machine (Python model + IEC 61131-3 Structured Text), placed in the automation pyramid |
| One industrial communication protocol in detail | [4-modbus-tcp](4-modbus-tcp/) | Modbus TCP server and client written from the specification; frames decoded byte by byte, exceptions included |

PLC organisation and programming, digital and analog I/O, and sequence design were covered in
BST-BCS-09 itself.

## Run

```bash
make venv     # once: Python venv with numpy and matplotlib
make all      # runs every part, rewrites each results.txt and the plots
```

## Results

Each part's README holds its results and explanation.

# 4 · Modbus TCP in detail

A Modbus TCP server and client written from the specification (Modbus Application
Protocol v1.1b3; Modbus Messaging on TCP/IP v1.0b) with plain sockets, no Modbus library.
The server plays the tank PLC of exercise 3 (pyramid level 1); the client plays the HMI
(level 2). Full session: [results.txt](results.txt).

## Frame

```
MBAP header (7 bytes)                                      PDU
transaction id | protocol id | length | unit id | function code | data
   2 bytes     |   2 (= 0)   |   2    |    1    |      1        |  n
```

`length` counts the unit id plus the PDU; all 16-bit fields are big-endian. The transaction
id lets a client match responses to requests; the unit id addresses a device behind a
gateway (for example a Modbus RTU device on RS-485).

## Data map of the tank PLC

| Table | Address | Meaning |
| --- | --- | --- |
| Coils | 0, 1, 2 | M1 fill pump, M2 drain pump, E1 heater |
| Holding registers | 0 | Level (mm) |
| | 1 | Completed cycles |
| | 2 | State (0 IDLE … 4 MAINTENANCE) |
| | 3 | Heat hold time (s) |
| | 4 | Maintenance time (s) |

## Session, decoded

| Request | Bytes (request → response) | Meaning |
| --- | --- | --- |
| FC01 Read Coils 0–2 | `01 00 00 00 03` → `01 01 05` | 1 byte of data, 0x05 = 0b101: M1 on, M2 off, E1 on |
| FC03 Read 5 registers | `03 00 00 00 05` → `03 0A 02 64 00 02 00 01 00 14 00 5A` | 10 bytes: 612 mm, cycle 2, state 1, 20 s, 90 s |
| FC06 Write register 3 = 25 | `06 00 03 00 19` → same bytes echoed | Success is an echo of the request |
| FC16 Write registers 3–4 = 30, 120 | `10 00 03 00 02 04 00 1E 00 78` → `10 00 03 00 02` | 2 registers written |
| FC03 registers 4–6 | `03 00 04 00 03` → `83 02` | Exception: 0x80 set on the function code, code 02 illegal data address |
| FC01 quantity 0 | `01 00 00 00 00` → `81 03` | Exception 03 illegal data value |
| FC43 (not implemented) | `2B 0E 01 00` → `AB 01` | Exception 01 illegal function |

All seven checks pass.

## Compared with PROFIBUS (from BST-BCS-09)

| | PROFIBUS DP | Modbus TCP |
| --- | --- | --- |
| Physical layer | RS-485 twisted pair, up to 12 Mbit/s, 32 stations per segment, repeaters to extend | Ethernet |
| Access | Token passing between masters, cyclic master–slave polling | Client–server request/response over TCP port 502 |
| Data | Cyclic process image exchanged every bus cycle | Data read or written on request |
| Determinism | Fixed bus cycle | Depends on the network and the client's polling |

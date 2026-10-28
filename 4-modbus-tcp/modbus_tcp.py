"""Exercise 4: Modbus TCP, implemented from the protocol specification with plain sockets.

Modbus Application Protocol v1.1b3 and Modbus Messaging on TCP/IP v1.0b. A Modbus TCP frame (ADU) is

    MBAP header (7 bytes)                             PDU
    transaction id | protocol id | length | unit id | function code | data
        2 bytes    |  2 (= 0)    |   2    |   1     |     1         |  n

`length` counts the unit id plus the PDU. All 16-bit fields are big-endian.

The server plays the tank PLC of exercise 3 (level 1 of the automation pyramid): coils are its
outputs, holding registers its process values and set-points. The client plays the HMI / SCADA
(level 2). Implemented function codes:
    0x01 Read Coils, 0x03 Read Holding Registers, 0x06 Write Single Register,
    0x10 Write Multiple Registers; exceptions 0x01 illegal function, 0x02 illegal data address,
    0x03 illegal data value.

Run:  python modbus_tcp.py   -> starts the server on localhost, runs the client session,
                                prints every request/response in hex with a decoded line, runs checks.
"""
import socket
import struct
import threading

HOST, PORT = "127.0.0.1", 15020          # 502 is the standard port; a high port avoids needing root


# ---------------------------------------------------------------- server
class TankPLC:
    """Data model of the tank PLC."""

    def __init__(self):
        # coils 0..2: M1, M2, E1
        self.coils = [True, False, True]
        # holding registers: 0 level (mm), 1 cycle count, 2 state, 3 heat time (s), 4 maintenance time (s)
        self.hr = [612, 2, 1, 20, 90]
        self.lock = threading.Lock()


def exception(fc, code):
    return struct.pack(">BB", fc | 0x80, code)


def handle_pdu(plc, pdu):
    fc = pdu[0]
    with plc.lock:
        if fc == 0x01:                                   # Read Coils
            start, qty = struct.unpack(">HH", pdu[1:5])
            if not 1 <= qty <= 2000:
                return exception(fc, 0x03)
            if start + qty > len(plc.coils):
                return exception(fc, 0x02)
            bits = plc.coils[start:start + qty]
            nbytes = (qty + 7) // 8
            data = bytearray(nbytes)
            for i, b in enumerate(bits):                 # LSB of the first byte = first coil
                if b:
                    data[i // 8] |= 1 << (i % 8)
            return struct.pack(">BB", fc, nbytes) + bytes(data)
        if fc == 0x03:                                   # Read Holding Registers
            start, qty = struct.unpack(">HH", pdu[1:5])
            if not 1 <= qty <= 125:
                return exception(fc, 0x03)
            if start + qty > len(plc.hr):
                return exception(fc, 0x02)
            regs = plc.hr[start:start + qty]
            return struct.pack(f">BB{qty}H", fc, 2 * qty, *regs)
        if fc == 0x06:                                   # Write Single Register (echo request)
            addr, value = struct.unpack(">HH", pdu[1:5])
            if addr >= len(plc.hr):
                return exception(fc, 0x02)
            plc.hr[addr] = value
            return pdu[:5]
        if fc == 0x10:                                   # Write Multiple Registers
            start, qty, nbytes = struct.unpack(">HHB", pdu[1:6])
            if not 1 <= qty <= 123 or nbytes != 2 * qty:
                return exception(fc, 0x03)
            if start + qty > len(plc.hr):
                return exception(fc, 0x02)
            plc.hr[start:start + qty] = struct.unpack(f">{qty}H", pdu[6:6 + nbytes])
            return struct.pack(">BHH", fc, start, qty)
    return exception(fc, 0x01)


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def serve(plc, ready):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    ready.set()
    conn, _ = srv.accept()
    with conn, srv:
        while True:
            try:
                header = recv_exact(conn, 7)
            except ConnectionError:
                return
            tid, proto, length, unit = struct.unpack(">HHHB", header)
            pdu = recv_exact(conn, length - 1)
            resp = handle_pdu(plc, pdu)
            conn.sendall(struct.pack(">HHHB", tid, proto, len(resp) + 1, unit) + resp)


# ---------------------------------------------------------------- client
class Client:
    def __init__(self, unit=1):
        self.sock = socket.create_connection((HOST, PORT))
        self.tid = 0
        self.unit = unit

    def request(self, pdu, label):
        self.tid += 1
        adu = struct.pack(">HHHB", self.tid, 0, len(pdu) + 1, self.unit) + pdu
        self.sock.sendall(adu)
        header = recv_exact(self.sock, 7)
        tid, proto, length, unit = struct.unpack(">HHHB", header)
        resp = recv_exact(self.sock, length - 1)
        assert tid == self.tid and proto == 0, "transaction id / protocol id mismatch"
        print(f"\n{label}")
        print(f"  request  {fmt(adu)}")
        print(f"  response {fmt(header + resp)}")
        return resp

    def read_coils(self, start, qty):
        r = self.request(struct.pack(">BHH", 0x01, start, qty), f"FC01 Read Coils start={start} qty={qty}")
        if r[0] & 0x80:
            return decode_exc(r)
        bits = [(r[2 + i // 8] >> (i % 8)) & 1 for i in range(qty)]
        print(f"  decoded  coils = {bits}")
        return bits

    def read_hr(self, start, qty):
        r = self.request(struct.pack(">BHH", 0x03, start, qty), f"FC03 Read Holding Registers start={start} qty={qty}")
        if r[0] & 0x80:
            return decode_exc(r)
        regs = list(struct.unpack(f">{qty}H", r[2:2 + 2 * qty]))
        print(f"  decoded  registers = {regs}")
        return regs

    def write_reg(self, addr, value):
        r = self.request(struct.pack(">BHH", 0x06, addr, value), f"FC06 Write Single Register addr={addr} value={value}")
        if r[0] & 0x80:
            return decode_exc(r)
        print("  decoded  echo of the request = success")
        return True

    def write_regs(self, start, values):
        pdu = struct.pack(f">BHHB{len(values)}H", 0x10, start, len(values), 2 * len(values), *values)
        r = self.request(pdu, f"FC16 Write Multiple Registers start={start} values={values}")
        if r[0] & 0x80:
            return decode_exc(r)
        print(f"  decoded  wrote {struct.unpack('>HH', r[1:5])[1]} registers")
        return True

    def raw(self, pdu, label):
        r = self.request(pdu, label)
        return decode_exc(r) if r[0] & 0x80 else r

    def close(self):
        self.sock.close()


EXC = {1: "illegal function", 2: "illegal data address", 3: "illegal data value"}


def decode_exc(r):
    print(f"  decoded  exception: function 0x{r[0]:02X} = 0x{r[0] & 0x7F:02X} | 0x80, code {r[1]} ({EXC.get(r[1], '?')})")
    return ("EXC", r[1])


def fmt(b):
    h = b.hex(" ").upper().split()
    return f"[MBAP {' '.join(h[:7])}] [PDU {' '.join(h[7:])}]"


if __name__ == "__main__":
    plc = TankPLC()
    ready = threading.Event()
    th = threading.Thread(target=serve, args=(plc, ready), daemon=True)
    th.start()
    ready.wait()

    c = Client()
    checks = []
    checks.append(("read coils M1,M2,E1", c.read_coils(0, 3) == [1, 0, 1]))
    checks.append(("read 5 holding registers", c.read_hr(0, 5) == [612, 2, 1, 20, 90]))
    checks.append(("write heat time 25 s", c.write_reg(3, 25) is True and plc.hr[3] == 25))
    checks.append(("write heat + maintenance times", c.write_regs(3, [30, 120]) is True and plc.hr[3:5] == [30, 120]))
    checks.append(("exception 02, address past the map", c.read_hr(4, 3) == ("EXC", 2)))
    checks.append(("exception 03, quantity 0", c.read_coils(0, 0) == ("EXC", 3)))
    checks.append(("exception 01, unsupported FC 0x2B", c.raw(bytes([0x2B, 0x0E, 0x01, 0x00]), "FC43 (not implemented)") == ("EXC", 1)))
    c.close()

    print("\nChecks")
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    raise SystemExit(0 if all(ok for _, ok in checks) else 1)

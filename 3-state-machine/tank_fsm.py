"""Exercise 3: the tank-heating process of PLC exercise Task 2, modelled as a state machine.

Specification (Siemens SPE assignment, Task 2):
  1) Level below B1 and Start pressed -> pump motor M1 (pump G1) fills until level reaches B3.
  2) From B2 on, heater E1 is on while the tank fills.
  3) At B3 the heater stays on for 20 s, then turns off.
  4) Then pump motor M2 (pump G2) empties the tank until the level drops below B1.
  5) The cycle repeats 5 times; then the system stays idle 90 s (maintenance) before a new Start.

The controller below is written the way a PLC runs it: one scan every 10 ms, read inputs ->
evaluate the state machine -> write outputs, with TON-style timers. A simple tank model closes the loop.
tank.st holds the same machine in IEC 61131-3 Structured Text.

Run:  python tank_fsm.py   -> transition log, checks of every spec point, timing diagram PNG.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = 0.01                       # s
B1, B2, B3 = 0.10, 0.50, 0.90     # m, sensor heights
FILL_RATE, DRAIN_RATE = 0.02, 0.025   # m/s with pump running
HEAT_TIME, MAINT_TIME, CYCLES = 20.0, 90.0, 5


class TON:
    """IEC 61131-3 on-delay timer: Q goes TRUE once IN has been TRUE for PT seconds."""

    def __init__(self, pt):
        self.pt, self.et, self.q = pt, 0.0, False

    def __call__(self, inp, dt):
        self.et = min(self.et + dt, self.pt) if inp else 0.0
        self.q = inp and self.et >= self.pt
        return self.q


class TankController:
    STATES = ("IDLE", "FILL", "HEAT_HOLD", "DRAIN", "MAINTENANCE")

    def __init__(self):
        self.state = "IDLE"
        self.cycle = 0
        self.t_heat = TON(HEAT_TIME)
        self.t_maint = TON(MAINT_TIME)
        self.M1 = self.M2 = self.E1 = False

    def scan(self, start, b1, b2, b3, dt=SCAN):
        s = self.state
        heat_done = self.t_heat(s == "HEAT_HOLD", dt)
        maint_done = self.t_maint(s == "MAINTENANCE", dt)

        if s == "IDLE" and start and not b1:
            s = "FILL"
        elif s == "FILL" and b3:
            s = "HEAT_HOLD"
        elif s == "HEAT_HOLD" and heat_done:
            s = "DRAIN"
        elif s == "DRAIN" and not b1:
            self.cycle += 1
            s = "FILL" if self.cycle < CYCLES else "MAINTENANCE"
        elif s == "MAINTENANCE" and maint_done:
            self.cycle = 0
            s = "IDLE"
        self.state = s

        # outputs are a function of the state (Moore machine) plus the B2 interlock for the heater
        self.M1 = s == "FILL"
        self.M2 = s == "DRAIN"
        self.E1 = (s == "FILL" and b2) or s == "HEAT_HOLD"
        return self.M1, self.M2, self.E1


def simulate(t_end=900.0, start_at=1.0):
    ctl = TankController()
    level = 0.0
    log, trace = [], []
    prev = ctl.state
    t = 0.0
    while t < t_end:
        start = abs(t - start_at) < SCAN / 2                     # one-scan pulse on the Start button
        b1, b2, b3 = level >= B1, level >= B2, level >= B3
        m1, m2, e1 = ctl.scan(start, b1, b2, b3)
        level += (FILL_RATE * m1 - DRAIN_RATE * m2) * SCAN
        level = max(level, 0.0)
        if ctl.state != prev:
            log.append((round(t, 2), prev, ctl.state, ctl.cycle, round(level, 3)))
            prev = ctl.state
        trace.append((t, level, m1, m2, e1, ctl.state))
        t += SCAN
    return log, trace


def check(trace, log):
    """Check each spec point against the simulated run."""
    results = []
    # 1) M1 runs only between Start/below-B1 and B3
    results.append(("1 M1 stops at B3", all(not (m1 and lvl > B3 + 0.01) for _, lvl, m1, *_ in trace)))
    # 2) heater never on below B2 while filling
    results.append(("2 heater only from B2", all(not (e1 and lvl < B2 - 0.001 and st == "FILL") for _, lvl, _, _, e1, st in trace)))
    # 3) heater hold lasts 20 s
    holds = [(a, b) for (a, s0, s1, *_), (b, *_rest) in zip(log, log[1:]) if s1 == "HEAT_HOLD"]
    results.append(("3 hold = 20 s", all(abs((b - a) - HEAT_TIME) < 2 * SCAN for a, b in holds) and len(holds) == CYCLES))
    # 4) M2 and M1 never on together; drain ends below B1
    results.append(("4 M1/M2 interlocked", all(not (m1 and m2) for _, _, m1, m2, *_ in trace)))
    # 5) exactly 5 cycles, then 90 s maintenance, then IDLE
    maint = [(a, b) for (a, s0, s1, *_), (b, *_rest) in zip(log, log[1:]) if s1 == "MAINTENANCE"]
    results.append(("5 five cycles then 90 s idle", len(maint) == 1 and abs(maint[0][1] - maint[0][0] - MAINT_TIME) < 2 * SCAN
                    and log[-1][2] == "IDLE"))
    return results


def plot(trace):
    t = [r[0] for r in trace]
    fig, axes = plt.subplots(4, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(t, [r[1] for r in trace])
    for h, name in ((B1, "B1"), (B2, "B2"), (B3, "B3")):
        axes[0].axhline(h, color="grey", ls=":", lw=0.8)
        axes[0].text(t[-1], h, f" {name}", va="center", fontsize=8)
    axes[0].set_ylabel("Level (m)")
    for ax, idx, name in ((axes[1], 2, "M1 fill"), (axes[2], 3, "M2 drain"), (axes[3], 4, "E1 heater")):
        ax.step(t, [int(r[idx]) for r in trace], where="post")
        ax.set_ylabel(name)
        ax.set_yticks([0, 1])
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("Tank process: 5 cycles then 90 s maintenance")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "3_timing_diagram.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    log, trace = simulate()
    lines = ["Transitions  (time s, from -> to, completed cycles, level m)"]
    lines += [f"  {t:7.2f}  {a:<11} -> {b:<11} cycle {c}  level {lvl:.3f}" for t, a, b, c, lvl in log]
    lines.append("")
    lines.append("Spec checks")
    res = check(trace, log)
    lines += [f"  {'PASS' if ok else 'FAIL'}  {name}" for name, ok in res]
    print("\n".join(lines))
    with open(os.path.join(HERE, "results.txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    plot(trace)
    raise SystemExit(0 if all(ok for _, ok in res) else 1)

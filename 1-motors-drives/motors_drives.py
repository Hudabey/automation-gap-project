"""Exercise 1: electric motors and drives (after Hughes & Drury, Electric Motors and Drives, 5th ed.).

1a  Separately excited DC motor: torque-speed line and armature-voltage speed control.
1b  Induction motor: per-phase equivalent circuit, torque-slip curve, starting / pull-out / rated torque.
1c  Inverter-fed induction motor: constant V/f control, with and without low-frequency voltage boost.
1d  Drive sizing for the conveyor of the PLC exercise (Task 3): load torque, gear ratio, motor choice.

Run:  python motors_drives.py   -> prints results.txt content and writes the PNG plots next to this file.
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
out_lines = []


def out(s=""):
    print(s)
    out_lines.append(s)


# ---------------------------------------------------------------- 1a DC motor
# Hughes ch. 3: V = E + I*Ra, E = k*w, T = k*I  (k in V·s/rad = N·m/A)
V_rated, Ra, k = 220.0, 0.5, 1.4
I_rated = 30.0

w0 = V_rated / k                       # no-load speed (rad/s)
T_stall = k * V_rated / Ra             # stall torque, I = V/Ra
T_rated = k * I_rated
w_rated = (V_rated - I_rated * Ra) / k

out("1a  Separately excited DC motor  (V = 220 V, Ra = 0.5 ohm, k = 1.4 N·m/A)")
out(f"    no-load speed      w0 = V/k            = {w0:7.1f} rad/s = {w0*60/(2*math.pi):6.0f} rpm")
out(f"    rated torque       T  = k*I (I = 30 A) = {T_rated:7.1f} N·m")
out(f"    rated speed        w  = (V - I*Ra)/k   = {w_rated:7.1f} rad/s = {w_rated*60/(2*math.pi):6.0f} rpm")
out(f"    speed drop at rated load               = {100*(w0-w_rated)/w0:5.1f} %")
out(f"    stall torque       T  = k*V/Ra         = {T_stall:7.0f} N·m  ({T_stall/T_rated:.0f}x rated -> needs current limiting)")
out(f"    efficiency at rated point (copper loss only) = {100*(1 - I_rated**2*Ra/(V_rated*I_rated)):4.1f} %")

fig, ax = plt.subplots(figsize=(6, 4))
T = np.linspace(0, 1.5 * T_rated, 100)
for V in (220, 165, 110, 55):
    w = (V - T / k * Ra) / k
    ax.plot(T, w * 60 / (2 * math.pi), label=f"V = {V} V")
ax.axvline(T_rated, color="grey", ls=":", lw=1)
ax.set_xlabel("Torque (N·m)")
ax.set_ylabel("Speed (rpm)")
ax.set_title("DC motor: speed control by armature voltage")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "1a_dc_torque_speed.png"), dpi=120)
plt.close(fig)

# ------------------------------------------------------- 1b induction motor
# Hughes ch. 5-7. 4-pole, 400 V (star, 231 V/phase), 50 Hz, about 5.5 kW.
p, f_rated, V_line = 4, 50.0, 400.0
V_ph = V_line / math.sqrt(3)
R1, X1, R2, X2, Xm = 0.9, 2.4, 0.95, 2.4, 50.0     # ohm per phase at 50 Hz


def torque(s, V=V_ph, f=f_rated):
    """Electromagnetic torque from the per-phase circuit (Thevenin form), reactances scaled with f."""
    a = f / f_rated
    x1, x2, xm = X1 * a, X2 * a, Xm * a
    Zth = complex(0, xm) * complex(R1, x1) / complex(R1, x1 + xm)
    Vth = V * xm / abs(complex(R1, x1 + xm))
    ws = 2 * math.pi * f / (p / 2)
    I2 = Vth / abs(complex(Zth.real + R2 / s, Zth.imag + x2))
    return 3 * I2**2 * R2 / s / ws


ns = 120 * f_rated / p
s_grid = np.linspace(1e-4, 1, 2000)
T_curve = np.array([torque(s) for s in s_grid])
i_max = int(np.argmax(T_curve))
T_start = torque(1.0)

# rated point: slip at which shaft power (ignoring mechanical losses) = 5.5 kW
P_target = 5500.0
s_rated = min(s_grid[:i_max], key=lambda s: abs(torque(s) * (1 - s) * 2 * math.pi * ns / 60 - P_target))
T_r = torque(s_rated)

out()
out("1b  Induction motor  (4-pole, 400 V star, 50 Hz, R1 0.9, X1 2.4, R2' 0.95, X2' 2.4, Xm 50 ohm/phase)")
out(f"    synchronous speed  ns = 120 f / p       = {ns:6.0f} rpm")
out(f"    rated point (5.5 kW): slip = {100*s_rated:4.1f} %, speed = {ns*(1-s_rated):5.0f} rpm, torque = {T_r:5.1f} N·m")
out(f"    starting torque  (s = 1)                = {T_start:5.1f} N·m  ({T_start/T_r:.1f}x rated)")
out(f"    pull-out torque  (s = {s_grid[i_max]:.3f})           = {T_curve[i_max]:5.1f} N·m  ({T_curve[i_max]/T_r:.1f}x rated)")
s_check = R2 / abs(complex(0, Xm) * complex(R1, X1) / complex(R1, X1 + Xm) + complex(0, X2))
out(f"    check: s_max = R2'/|Zth + jX2'|         = {s_check:.3f}")
out(f"    starting current (s = 1) = {V_ph/abs(complex(R1+R2, X1+X2)):4.0f} A per phase  -> why star-delta or soft starters are used")

fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(ns * (1 - s_grid), T_curve)
ax.plot([ns * (1 - s_rated)], [T_r], "o", label=f"rated {T_r:.0f} N·m")
ax.plot([ns * (1 - s_grid[i_max])], [T_curve[i_max]], "s", label=f"pull-out {T_curve[i_max]:.0f} N·m")
ax.set_xlabel("Speed (rpm)")
ax.set_ylabel("Torque (N·m)")
ax.set_title("Induction motor torque-speed curve, 50 Hz")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "1b_induction_torque_speed.png"), dpi=120)
plt.close(fig)

# ---------------------------------------------------- 1c V/f inverter drive
out()
out("1c  Inverter drive, constant V/f (V/f = 231/50 = 4.62 V/Hz per phase)")
out("      f (Hz)   V (V)   ns (rpm)   pull-out, plain V/f   pull-out, with boost")
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for f in (50, 35, 20, 10, 5):
    V = V_ph * f / f_rated
    V_boost = V + 0.05 * V_ph * (1 - f / f_rated)          # linear boost, 5 % of rated at 0 Hz -> 0 at 50 Hz
    ns_f = 120 * f / p
    Tf = np.array([torque(s, V, f) for s in s_grid])
    Tb = np.array([torque(s, V_boost, f) for s in s_grid])
    out(f"      {f:5.0f}   {V:6.1f}   {ns_f:7.0f}    {Tf.max():6.1f} N·m            {Tb.max():6.1f} N·m")
    axes[0].plot(ns_f * (1 - s_grid), Tf, label=f"{f} Hz")
    axes[1].plot(ns_f * (1 - s_grid), Tb, label=f"{f} Hz")
axes[0].set_title("Constant V/f: pull-out torque falls at low f (R1 drop)")
axes[1].set_title("V/f with low-frequency voltage boost")
for a in axes:
    a.set_xlabel("Speed (rpm)")
    a.grid(alpha=0.3)
    a.legend(fontsize=8)
axes[0].set_ylabel("Torque (N·m)")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "1c_vf_control.png"), dpi=120)
plt.close(fig)
out("    Constant V/f keeps the flux, and so the torque curve shape, nearly constant while ns scales with f.")
out("    At low f the stator resistance drop takes a larger share of V, flux falls, and pull-out torque drops;")
out("    the boost adds voltage at low f to restore it.")

# ------------------------------------------------ 1d conveyor drive sizing
# PLC exercise Task 3: PCB heat-test conveyor.  Assumed mechanical data (stated, not given in the sheet).
m_load = 60.0        # kg: belt, carriers and one board
mu = 0.3             # rolling/sliding friction coefficient of the belt
v_belt = 0.25        # m/s
d_drum = 0.10        # m drum diameter
t_acc = 0.5          # s to reach belt speed
eta_gear = 0.9
g = 9.81

F_fric = mu * m_load * g
F_acc = m_load * v_belt / t_acc
T_drum = (F_fric + F_acc) * d_drum / 2
n_drum = v_belt / (math.pi * d_drum) * 60
gear = (ns * (1 - 0.05)) / n_drum      # small 4-pole motor, about 5 % slip
T_motor = T_drum / gear / eta_gear
P_motor = (F_fric * v_belt) / eta_gear

out()
out("1d  Conveyor drive for PLC Task 3 (assumed: 60 kg moving mass, mu 0.3, 0.25 m/s belt, 0.10 m drum, 0.5 s ramp)")
out(f"    friction force        = mu*m*g            = {F_fric:6.1f} N")
out(f"    acceleration force    = m*v/t             = {F_acc:6.1f} N")
out(f"    drum torque           = F*d/2             = {T_drum:6.2f} N·m at {n_drum:4.0f} rpm")
out(f"    gear ratio (motor about 1425 rpm)          = {gear:5.1f} : 1")
out(f"    motor torque          = T_drum/(i*eta)    = {T_motor:6.3f} N·m")
out(f"    steady shaft power    = F_fric*v/eta      = {P_motor:6.1f} W  -> a 0.12 kW 4-pole motor with a ~30:1 gearbox")
out("    Drive choice: the cycle needs start/stop and two speeds at most, so a direct-on-line contactor")
out("    (as in the PLC exercise, output M1) is enough. A small inverter would add soft ramps (protects the")
out("    boards on the belt) and positioning at sensor B2, and is the better choice if parts slip at start.")

with open(os.path.join(HERE, "results.txt"), "w") as fh:
    fh.write("\n".join(out_lines) + "\n")

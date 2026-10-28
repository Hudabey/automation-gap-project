"""Exercise 2: industrial sensors, calibration, filtering and estimation.

Setting: the pressure transmitter of the PLC course (0-10 bar -> 0-10 V on an S7 analog input,
nominal range 0..27648 counts), here with realistic errors.

2a  Accuracy vs precision: bias and spread of a raw transmitter at fixed pressures.
2b  Calibration: two-point and least-squares linear calibration against a reference gauge.
2c  Filtering: moving average and first-order IIR (exponential) filter; step response and noise; stability.
2d  Estimation: 1-D Kalman filter tracking a slowly filling tank; gain convergence.
2e  Data fusion: two level sensors with different noise combined by inverse-variance weighting.

Run:  python sensors_filtering.py   (fixed random seed, so results are repeatable)
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(7)
out_lines = []


def out(s=""):
    print(s)
    out_lines.append(s)


# ---------------------------------------------------- the simulated sensor
P_FS = 10.0          # bar full scale
GAIN_ERR = 1.03      # +3 % span error
OFFSET = 0.15        # V zero offset
NONLIN = -0.004      # V/bar^2, slight quadratic non-linearity
NOISE = 0.04         # V rms electrical noise
COUNTS_FS = 27648    # S7 nominal range for 0..10 V


def transmitter_volts(p):
    p = np.asarray(p, dtype=float)
    return GAIN_ERR * p + OFFSET + NONLIN * p * (p - P_FS) + rng.normal(0, NOISE, p.shape)


def to_counts(v):
    return np.clip(np.round(v / 10.0 * COUNTS_FS), -32768, 32767)


def counts_to_bar_nominal(c):
    return c / COUNTS_FS * P_FS        # what an uncalibrated PLC program would compute


# --------------------------------------------- 2a accuracy vs precision
out("2a  Accuracy vs precision (200 readings per point, uncalibrated scaling counts/27648*10 bar)")
out("      true (bar)   mean read (bar)   bias (bar)   std (bar)")
test_p = [0.0, 2.5, 5.0, 7.5, 10.0]
for p in test_p:
    r = counts_to_bar_nominal(to_counts(transmitter_volts(np.full(200, p))))
    out(f"      {p:7.2f}      {r.mean():8.3f}        {r.mean()-p:+7.3f}     {r.std(ddof=1):6.3f}")
out("    Bias (accuracy error) is systematic: up to ~0.45 bar, so calibration is needed.")
out("    Spread (precision) is random: ~0.04 bar, set by noise; calibration cannot remove it, filtering can reduce it.")
out(f"    ADC resolution: 10 bar / 27648 counts = {10/27648*1000:.2f} mbar per count, far below the noise.")

# --------------------------------------------------------- 2b calibration
ref_p = np.linspace(0, 10, 11)
reading = np.array([counts_to_bar_nominal(to_counts(transmitter_volts(np.full(50, p)))).mean() for p in ref_p])

# two-point: zero and span
a2 = (ref_p[-1] - ref_p[0]) / (reading[-1] - reading[0])
b2 = ref_p[0] - a2 * reading[0]
# least squares over all points
A = np.vstack([reading, np.ones_like(reading)]).T
a_ls, b_ls = np.linalg.lstsq(A, ref_p, rcond=None)[0]

val_p = np.linspace(0.5, 9.5, 10)
val_r = np.array([counts_to_bar_nominal(to_counts(transmitter_volts(np.full(50, p)))).mean() for p in val_p])
err_raw = np.abs(val_r - val_p).max()
err_2pt = np.abs(a2 * val_r + b2 - val_p).max()
err_ls = np.abs(a_ls * val_r + b_ls - val_p).max()

out()
out("2b  Calibration against a reference gauge (11 points 0..10 bar, validated on 10 other points)")
out(f"    two-point (zero/span):  p = {a2:.4f} * r {b2:+.4f}   max error {err_2pt:.3f} bar")
out(f"    least squares (11 pts): p = {a_ls:.4f} * r {b_ls:+.4f}   max error {err_ls:.3f} bar")
out(f"    uncalibrated:                                       max error {err_raw:.3f} bar")
out("    Two-point removes offset and span error exactly at the ends but leaves the bow of the non-linearity")
out("    in mid-range; least squares spreads that residual over the range and lowers the worst case.")
out("    In the PLC this is one line after NORM_X/SCALE_X:  p_cal := a * p_raw + b;")

fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(val_p, val_r - val_p, "o-", label="uncalibrated")
ax.plot(val_p, a2 * val_r + b2 - val_p, "s-", label="two-point")
ax.plot(val_p, a_ls * val_r + b_ls - val_p, "^-", label="least squares")
ax.axhline(0, color="grey", lw=0.8)
ax.set_xlabel("True pressure (bar)")
ax.set_ylabel("Error (bar)")
ax.set_title("Calibration error on validation points")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "2b_calibration.png"), dpi=120)
plt.close(fig)

# ------------------------------------------------------------ 2c filtering
dt = 0.01                                    # 10 ms PLC cycle / sample time
t = np.arange(0, 6, dt)
p_true = np.where(t < 2, 2.0, 6.0)           # step from 2 to 6 bar at t = 2 s
meas = a_ls * counts_to_bar_nominal(to_counts(transmitter_volts(p_true))) + b_ls

N = 20
ma = np.convolve(meas, np.ones(N) / N, mode="full")[: len(meas)]
ma[: N - 1] = np.cumsum(meas[: N - 1]) / np.arange(1, N)

alpha = 0.1                                  # y[k] = y[k-1] + alpha*(x[k] - y[k-1])
ema = np.empty_like(meas)
ema[0] = meas[0]
for i in range(1, len(meas)):
    ema[i] = ema[i - 1] + alpha * (meas[i] - ema[i - 1])

flat = t < 1.9


def settle_time(y):
    """Time after the step to stay within 2 % of the 4 bar step."""
    after = y[t >= 2]
    idx = np.where(np.abs(after - 6.0) > 0.08)[0]
    if len(idx) and idx[-1] >= len(after) - 50:
        return "never (noise > band)"
    return f"{(idx[-1] + 1) * dt:.2f} s" if len(idx) else "0.00 s"


tau = dt * (1 - alpha) / alpha
out()
out("2c  Filtering a 2 -> 6 bar step, 10 ms sampling")
out("      filter               noise std (bar)   2 % settling time")
out(f"      raw                  {meas[flat].std():.4f}            {settle_time(meas)}")
out(f"      moving average N=20  {ma[flat].std():.4f}            {settle_time(ma)}")
out(f"      exponential a=0.1    {ema[flat].std():.4f}            {settle_time(ema)}")
out(f"    Moving average: noise / sqrt(N) = {meas[flat].std()/np.sqrt(N):.4f} expected; delay N*dt = {N*dt:.2f} s, always stable (FIR).")
out(f"    Exponential: pole at z = 1 - a = {1-alpha:.1f}; stable for 0 < a < 2 (|1 - a| < 1);")
out(f"    time constant tau = dt(1-a)/a = {tau:.2f} s; noise gain sqrt(a/(2-a)) = {np.sqrt(alpha/(2-alpha)):.3f}.")
for a_test in (0.5, 1.0, 1.9, 2.1):
    y = 0.0
    for _ in range(200):
        y = y + a_test * (1.0 - y)
    out(f"      a = {a_test:3.1f}: output after 200 steps of a unit input = {y: .3g}")

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(t, meas, color="lightgrey", lw=0.8, label="measured")
ax.plot(t, ma, label=f"moving average N={N}")
ax.plot(t, ema, label=f"exponential a={alpha}")
ax.plot(t, p_true, "k--", lw=1, label="true")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Pressure (bar)")
ax.set_title("Noise vs response time")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "2c_filters.png"), dpi=120)
plt.close(fig)

# ---------------------------------------------------- 2d 1-D Kalman filter
# Tank level h (m) rising at a roughly constant rate; state x = [h, h_dot].
dt_k = 0.1
n = 600
q = 1e-9                                    # process noise (rate drift, m/s per step)^2
r_var = 0.02**2                             # level sensor noise 2 cm
true_h = np.zeros(n)
rate = 0.004
for i in range(1, n):
    rate += rng.normal(0, np.sqrt(q))
    true_h[i] = true_h[i - 1] + rate * dt_k
z = true_h + rng.normal(0, np.sqrt(r_var), n)

F = np.array([[1, dt_k], [0, 1]])
H = np.array([[1.0, 0.0]])
Q = np.array([[0, 0], [0, q]])
x = np.array([0.0, 0.0])
P = np.eye(2)
est = np.zeros(n)
gains = np.zeros(n)
for i in range(n):
    x = F @ x
    P = F @ P @ F.T + Q
    S = H @ P @ H.T + r_var
    K = (P @ H.T) / S
    x = x + (K * (z[i] - H @ x)).ravel()
    P = (np.eye(2) - K @ H) @ P
    est[i] = x[0]
    gains[i] = K[0, 0]

rms_raw = np.sqrt(np.mean((z[100:] - true_h[100:]) ** 2))
rms_kf = np.sqrt(np.mean((est[100:] - true_h[100:]) ** 2))
out()
out("2d  Kalman filter: tank level with a constant-rate model, 2 cm sensor noise, 0.1 s steps")
out(f"    RMS error raw sensor = {100*rms_raw:.2f} cm, Kalman estimate = {100*rms_kf:.2f} cm")
out(f"    level gain K: first step {gains[0]:.3f}, after 10 steps {gains[10]:.3f}, steady state {gains[-1]:.3f}")
out("    The gain starts near 1 (trust the sensor while the model is unknown) and converges to a constant")
out("    as P converges; with (F, H) observable and Q > 0 the steady-state filter is stable.")
out(f"    It also estimates the fill rate: {1000*x[1]:.2f} mm/s (true {1000*rate:.2f} mm/s), which a plain filter cannot.")

fig, axes = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
tt = np.arange(n) * dt_k
axes[0].plot(tt, z, color="lightgrey", lw=0.8, label="sensor")
axes[0].plot(tt, est, label="Kalman")
axes[0].plot(tt, true_h, "k--", lw=1, label="true")
axes[0].set_ylabel("Level (m)")
axes[0].legend()
axes[0].grid(alpha=0.3)
axes[1].plot(tt, gains)
axes[1].set_ylabel("Kalman gain K")
axes[1].set_xlabel("Time (s)")
axes[1].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "2d_kalman.png"), dpi=120)
plt.close(fig)

# ---------------------------------------------------------- 2e data fusion
s1, s2 = 0.02, 0.05                          # ultrasonic 2 cm, float sensor 5 cm
h_const = 1.20
z1 = h_const + rng.normal(0, s1, 5000)
z2 = h_const + rng.normal(0, s2, 5000)
w1 = (1 / s1**2) / (1 / s1**2 + 1 / s2**2)
fused = w1 * z1 + (1 - w1) * z2
naive = 0.5 * (z1 + z2)
out()
out("2e  Fusion of two level sensors (2 cm and 5 cm noise), 5000 samples")
out(f"    weights 1/sigma^2: w1 = {w1:.3f}, w2 = {1-w1:.3f}")
out(f"    std: sensor 1 {z1.std():.4f}, sensor 2 {z2.std():.4f}, plain average {naive.std():.4f}, weighted {fused.std():.4f} m")
out(f"    theory: 1/sqrt(1/s1^2 + 1/s2^2) = {1/np.sqrt(1/s1**2 + 1/s2**2):.4f} m; the weighted fusion beats the best single sensor,")
out("    the plain average does not. This is the static case of the Kalman update in 2d.")

with open(os.path.join(HERE, "results.txt"), "w") as fh:
    fh.write("\n".join(out_lines) + "\n")

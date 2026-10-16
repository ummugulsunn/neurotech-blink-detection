"""Causal pre-processing, so the same code could run sample-by-sample in real time."""
from __future__ import annotations

import numpy as np
from scipy import signal


def remove_baseline(x: np.ndarray, fs: float, calib_s: float) -> np.ndarray:
    """Subtract the median of the first `calib_s` seconds (the amplifier's DC offset)."""
    n = max(1, int(round(calib_s * fs)))
    return x - np.median(x[:n])


def bandpass(x: np.ndarray, fs: float, low_hz: float = 0.1, high_hz: float = 10.0) -> np.ndarray:
    """Causal band-pass: 1st-order high-pass (removes drift with little ringing after a blink)
    followed by a 4th-order Butterworth low-pass (removes EMG and 50/60 Hz mains)."""
    hp = signal.butter(1, low_hz, btype="highpass", fs=fs, output="sos")
    lp = signal.butter(4, high_hz, btype="lowpass", fs=fs, output="sos")
    sos = np.vstack([hp, lp])
    zi = signal.sosfilt_zi(sos) * x[0]
    y, _ = signal.sosfilt(sos, x, zi=zi)
    return y

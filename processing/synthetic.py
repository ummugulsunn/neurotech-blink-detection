"""Synthetic test signal. NOT a measurement: used only by tests and `demo.py --synthetic`
so the pipeline can be exercised before any real recording exists."""
from __future__ import annotations

import numpy as np

from processing.recording import Recording


def synthetic_recording(
    duration_s: float = 60.0,
    fs: float = 250.0,
    blink_times_s: np.ndarray | None = None,
    blink_amplitude: float = 120.0,
    noise_sd: float = 4.0,
    mains_hz: float = 50.0,
    seed: int = 0,
) -> Recording:
    rng = np.random.default_rng(seed)
    t = np.arange(int(duration_s * fs)) / fs
    if blink_times_s is None:
        blink_times_s = np.arange(12.0, duration_s - 2.0, 5.0)

    x = 512.0                                         # mid-scale ADC offset
    x = x + 20.0 * np.sin(2 * np.pi * 0.05 * t)       # slow electrode drift
    x = x + 6.0 * np.sin(2 * np.pi * mains_hz * t)    # mains interference
    x = x + rng.normal(0, noise_sd, t.size)
    for onset in blink_times_s:                       # skewed bump, ~300 ms wide
        u = np.clip(t - onset, 0, None)
        bump = (u / 0.1) ** 2 * np.exp(-u / 0.05)
        x = x + blink_amplitude * bump / bump.max()

    cue = np.zeros(t.size, dtype=bool)
    cue[np.clip(np.round(np.asarray(blink_times_s) * fs).astype(int), 0, t.size - 1)] = True
    return Recording(t=t, value=np.clip(np.round(x), 0, 1023), cue=cue, fs=fs, name="synthetic")

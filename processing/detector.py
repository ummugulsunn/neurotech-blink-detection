"""Threshold blink detector.

The signal is band-passed, then a blink is reported at the first sample where it
crosses `k` robust standard deviations (MAD-based) above its calibration level.
After a detection the detector ignores the signal for `refractory_s` seconds.
Everything is causal: a detection at sample i only uses samples <= i.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from processing.filters import bandpass, remove_baseline


@dataclass
class DetectorConfig:
    low_hz: float = 0.1
    high_hz: float = 10.0
    k: float = 5.0               # threshold in robust SDs; tune on training recordings only
    refractory_s: float = 0.4
    calib_s: float = 10.0        # leading window used for baseline and noise estimate
    polarity: str = "pos"        # "pos", "neg" or "both"; check against your electrode placement


@dataclass
class DetectionResult:
    filtered: np.ndarray
    threshold: float
    indices: np.ndarray          # sample index of each detection


def robust_sd(x: np.ndarray) -> float:
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))


def detect_blinks(x: np.ndarray, fs: float, cfg: DetectorConfig = DetectorConfig()) -> DetectionResult:
    y = bandpass(remove_baseline(x, fs, cfg.calib_s), fs, cfg.low_hz, cfg.high_hz)

    if cfg.polarity == "pos":
        s = y
    elif cfg.polarity == "neg":
        s = -y
    elif cfg.polarity == "both":
        s = np.abs(y)
    else:
        raise ValueError(f"unknown polarity {cfg.polarity!r}")

    n_cal = max(2, int(round(cfg.calib_s * fs)))
    cal = s[:n_cal]
    threshold = float(np.median(cal) + cfg.k * robust_sd(cal))

    above = s > threshold
    crossings = np.flatnonzero(above[1:] & ~above[:-1]) + 1
    refractory = int(round(cfg.refractory_s * fs))
    kept: list[int] = []
    for i in crossings:
        if i >= n_cal and (not kept or i - kept[-1] >= refractory):
            kept.append(int(i))
    return DetectionResult(filtered=y, threshold=threshold, indices=np.asarray(kept, dtype=int))

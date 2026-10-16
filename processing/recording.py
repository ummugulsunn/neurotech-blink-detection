"""Load recordings written by acquisition/logger.py."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Recording:
    t: np.ndarray          # seconds from the first sample (board clock)
    value: np.ndarray      # raw ADC counts (0-1023 on an Uno)
    cue: np.ndarray        # bool, True on the sample where a BLINK cue was shown
    fs: float              # sampling rate estimated from the board timestamps
    name: str = ""

    @property
    def duration_s(self) -> float:
        return float(self.t[-1] - self.t[0]) if len(self.t) > 1 else 0.0

    @property
    def cue_times(self) -> np.ndarray:
        return self.t[self.cue]


def board_time_to_seconds(board_time_us: np.ndarray) -> np.ndarray:
    """Convert Arduino micros() to seconds from the first sample, undoing the 32-bit rollover."""
    d = np.diff(board_time_us.astype(np.int64))
    d[d < 0] += 2**32
    return np.concatenate([[0], np.cumsum(d)]) / 1e6


def load_recording(path: str | Path) -> Recording:
    path = Path(path)
    data = np.genfromtxt(path, delimiter=",", comments="#", names=True, dtype=None, encoding="ascii")
    t = board_time_to_seconds(np.asarray(data["board_time_us"]))
    fs = 1.0 / float(np.median(np.diff(t)))
    return Recording(
        t=t,
        value=np.asarray(data["value"], dtype=float),
        cue=np.asarray(data["cue"]).astype(bool),
        fs=fs,
        name=path.stem,
    )

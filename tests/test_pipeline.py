"""Tests on synthetic signals only."""
import numpy as np
import pytest

from acquisition.logger import parse_line
from evaluation.evaluate import Score, match
from processing.detector import DetectorConfig, detect_blinks
from processing.filters import bandpass, remove_baseline
from processing.recording import board_time_to_seconds
from processing.synthetic import synthetic_recording

FS = 250.0


def amplitude_gain(freq_hz: float) -> float:
    t = np.arange(int(20 * FS)) / FS
    y = bandpass(np.sin(2 * np.pi * freq_hz * t), FS)
    return np.std(y[int(10 * FS):]) / np.std(np.sin(2 * np.pi * freq_hz * t))


def test_bandpass_keeps_blink_band_and_removes_mains():
    assert amplitude_gain(2.0) > 0.9
    assert amplitude_gain(50.0) < 0.01
    assert amplitude_gain(0.01) < 0.15


def test_remove_baseline_centres_calibration_window():
    x = np.full(1000, 512.0)
    assert np.allclose(remove_baseline(x, FS, calib_s=2.0), 0.0)


def test_detects_every_synthetic_blink_without_false_positives():
    rec = synthetic_recording(seed=1)
    det = detect_blinks(rec.value, rec.fs)
    score, latencies = match(rec.cue_times, rec.t[det.indices], max_lag_s=0.5)
    assert (score.tp, score.fp, score.fn) == (len(rec.cue_times), 0, 0)
    assert max(latencies) < 0.2  # onset to threshold crossing on a 100 ms rise


def test_no_detections_on_noise_only():
    rec = synthetic_recording(blink_times_s=np.array([]), seed=2)
    assert detect_blinks(rec.value, rec.fs).indices.size == 0


def test_refractory_merges_close_crossings():
    rec = synthetic_recording(seed=3)
    det = detect_blinks(rec.value, rec.fs, DetectorConfig(refractory_s=0.4))
    assert np.all(np.diff(det.indices) >= int(0.4 * rec.fs))


def test_negative_polarity_finds_inverted_blinks():
    rec = synthetic_recording(seed=4)
    inverted = 1024 - rec.value
    assert detect_blinks(inverted, rec.fs, DetectorConfig(polarity="pos")).indices.size == 0
    assert detect_blinks(inverted, rec.fs, DetectorConfig(polarity="neg")).indices.size == rec.cue.sum()


def test_match_counts_tp_fp_fn():
    score, lat = match(np.array([1.0, 5.0, 9.0]), np.array([1.2, 3.0, 5.1]), max_lag_s=0.5)
    assert (score.tp, score.fp, score.fn) == (2, 1, 1)
    assert lat == pytest.approx([0.2, 0.1])
    assert Score(2, 1, 1).f1 == pytest.approx(2 / 3)


def test_board_time_rollover():
    us = np.array([2**32 - 4000, 2**32 - 0, 4000], dtype=np.int64) % 2**32
    assert np.allclose(board_time_to_seconds(us), [0, 0.004, 0.008])


@pytest.mark.parametrize("raw,expected", [
    (b"123456,511\r\n", (123456, 511)),
    (b"# fs_hz=250 pin=A0 baud=115200\r\n", None),
    (b"12,\r\n", None),
    (b"\xff\xfe\r\n", None),
])
def test_parse_line(raw, expected):
    assert parse_line(raw) == expected

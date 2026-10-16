"""Evaluate the blink detector against BLINK cues recorded by acquisition/logger.py.

A detection counts as a true positive if it falls within [cue, cue + max_lag_s]
and no earlier detection was already matched to that cue. Latency is
detection time minus cue time, so on real recordings it includes the
participant's reaction time to the cue.

Held-out evaluation: pass --tune files to pick the threshold k on those
recordings only, then report metrics on --test files.

Example:
    python -m evaluation.evaluate --tune data/recordings/train/*.csv \
        --test data/recordings/test/*.csv --out results/
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from processing.detector import DetectorConfig, detect_blinks
from processing.recording import Recording, load_recording


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: "Score") -> "Score":
        return Score(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else float("nan")

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else float("nan")


def match(cue_times: np.ndarray, det_times: np.ndarray, max_lag_s: float) -> tuple[Score, list[float]]:
    """Greedy one-to-one matching of detections to cues in time order."""
    used = np.zeros(len(det_times), dtype=bool)
    latencies: list[float] = []
    for c in np.sort(cue_times):
        candidates = np.flatnonzero(~used & (det_times >= c) & (det_times <= c + max_lag_s))
        if candidates.size:
            j = candidates[0]
            used[j] = True
            latencies.append(float(det_times[j] - c))
    tp = len(latencies)
    return Score(tp=tp, fp=int((~used).sum()), fn=len(cue_times) - tp), latencies


def evaluate(recordings: list[Recording], cfg: DetectorConfig, max_lag_s: float):
    total, latencies, per_file = Score(), [], []
    for rec in recordings:
        det = detect_blinks(rec.value, rec.fs, cfg)
        score, lat = match(rec.cue_times, rec.t[det.indices], max_lag_s)
        total, latencies = total + score, latencies + lat
        per_file.append({"file": rec.name, "duration_s": round(rec.duration_s, 1),
                         "cues": int(rec.cue.sum()), **asdict(score)})
    return total, latencies, per_file


def tune_k(recordings: list[Recording], cfg: DetectorConfig, max_lag_s: float,
           grid=np.arange(2.0, 15.01, 0.5)) -> float:
    best_k, best_f1 = cfg.k, -1.0
    for k in grid:
        f1 = evaluate(recordings, replace(cfg, k=float(k)), max_lag_s)[0].f1
        if not np.isnan(f1) and f1 >= best_f1:  # ties go to the larger, more conservative k
            best_k, best_f1 = float(k), f1
    return best_k


def plot_recording(rec: Recording, cfg: DetectorConfig, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    det = detect_blinks(rec.value, rec.fs, cfg)
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(11, 5.5))
    ax1.plot(rec.t, rec.value, lw=0.6, color="0.35")
    ax1.set_ylabel("raw (ADC counts)")
    ax1.set_title(f"{rec.name}: raw vs. filtered ({cfg.low_hz}-{cfg.high_hz} Hz), k={cfg.k}")
    ax2.plot(rec.t, det.filtered, lw=0.8, color="tab:blue", label="filtered")
    ax2.axhline(det.threshold * (-1 if cfg.polarity == "neg" else 1), color="tab:orange", ls="--", lw=1, label="threshold")
    for i, c in enumerate(rec.cue_times):
        for ax in (ax1, ax2):
            ax.axvline(c, color="tab:green", alpha=0.35, lw=1, label="cue" if (i == 0 and ax is ax2) else None)
    ax2.plot(rec.t[det.indices], det.filtered[det.indices], "rv", ms=7, label="detected")
    ax2.axvspan(rec.t[0], rec.t[0] + cfg.calib_s, color="0.9", label="calibration")
    ax2.set_xlabel("time (s)")
    ax2.set_ylabel("filtered")
    ax2.legend(loc="upper right", fontsize=8, ncol=5)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def summarize(recordings: list[Recording], cfg: DetectorConfig, max_lag_s: float) -> dict:
    total, lat, per_file = evaluate(recordings, cfg, max_lag_s)
    lat_ms = np.asarray(lat) * 1000
    return {
        "dataset": {"recordings": len(recordings),
                    "total_duration_s": round(sum(r.duration_s for r in recordings), 1),
                    "cues": int(sum(r.cue.sum() for r in recordings))},
        "config": asdict(cfg), "max_lag_s": max_lag_s,
        **asdict(total),
        "precision": total.precision, "recall": total.recall, "f1": total.f1,
        "latency_ms_median": float(np.median(lat_ms)) if lat else None,
        "latency_ms_iqr": [float(np.percentile(lat_ms, 25)), float(np.percentile(lat_ms, 75))] if lat else None,
        "per_file": per_file,
    }


def print_summary(title: str, s: dict) -> None:
    d = s["dataset"]
    print(f"\n== {title} ==")
    print(f"dataset: {d['recordings']} recording(s), {d['total_duration_s']} s, {d['cues']} cues")
    for f in s["per_file"]:
        print(f"  {f['file']}: {f['duration_s']} s, cues={f['cues']} tp={f['tp']} fp={f['fp']} fn={f['fn']}")
    print(f"TP={s['tp']} FP={s['fp']} FN={s['fn']}  "
          f"precision={s['precision']:.3f} recall={s['recall']:.3f} F1={s['f1']:.3f}")
    if s["latency_ms_median"] is not None:
        q1, q3 = s["latency_ms_iqr"]
        print(f"latency (detection - cue): median {s['latency_ms_median']:.0f} ms, IQR {q1:.0f}-{q3:.0f} ms")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test", nargs="+", type=Path, required=True, help="held-out recordings to score")
    p.add_argument("--tune", nargs="*", type=Path, default=[], help="recordings used only to choose k")
    p.add_argument("--k", type=float, default=DetectorConfig.k)
    p.add_argument("--polarity", choices=["pos", "neg", "both"], default=DetectorConfig.polarity)
    p.add_argument("--max-lag", type=float, default=1.5, help="seconds after a cue a detection may count")
    p.add_argument("--out", type=Path, default=Path("results"))
    args = p.parse_args(argv)

    overlap = {f.resolve() for f in args.tune} & {f.resolve() for f in args.test}
    if overlap:
        p.error(f"files used for both tuning and testing: {sorted(map(str, overlap))}")

    cfg = DetectorConfig(k=args.k, polarity=args.polarity)
    if args.tune:
        tune_recs = [load_recording(f) for f in args.tune]
        cfg = replace(cfg, k=tune_k(tune_recs, cfg, args.max_lag))
        print_summary(f"tuning set (chose k={cfg.k})", summarize(tune_recs, cfg, args.max_lag))

    test_recs = [load_recording(f) for f in args.test]
    summary = summarize(test_recs, cfg, args.max_lag)
    summary["tuned_on"] = [str(f) for f in args.tune]
    print_summary("test set", summary)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(summary, indent=2))
    plot_recording(test_recs[0], cfg, args.out / "signal.png")
    print(f"\nwrote {args.out / 'metrics.json'} and {args.out / 'signal.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

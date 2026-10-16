"""Serial logger: reads "board_time_us,adc_value" lines from the Arduino and
writes them to CSV with a host timestamp.

With --cue, the terminal prints BLINK at random intervals and the row that is
being written at that moment gets cue=1. Those cues are the ground-truth labels
used by evaluation/evaluate.py.

Example:
    python -m acquisition.logger --port /dev/cu.usbmodem1101 --seconds 120 --cue \
        --out data/recordings/s01_r01.csv
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = ["host_time_s", "board_time_us", "value", "cue"]


def parse_line(raw: bytes) -> tuple[int, int] | None:
    """Return (board_time_us, value) or None for header/garbled lines."""
    text = raw.decode("ascii", errors="ignore").strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def next_cue_time(now: float, min_gap: float, max_gap: float) -> float:
    return now + random.uniform(min_gap, max_gap)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", required=True, help="serial port, e.g. /dev/cu.usbmodem1101 or COM3")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--seconds", type=float, default=60.0, help="recording length")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cue", action="store_true", help="show BLINK cues and label them")
    p.add_argument("--settle", type=float, default=10.0,
                   help="seconds at the start with no cues (used as the detector's calibration window)")
    p.add_argument("--min-gap", type=float, default=4.0, help="min seconds between cues")
    p.add_argument("--max-gap", type=float, default=7.0, help="max seconds between cues")
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args(argv)

    import serial  # imported here so the rest of the repo works without pyserial

    random.seed(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with serial.Serial(args.port, args.baud, timeout=1) as ser, args.out.open("w", newline="") as f:
        time.sleep(2.0)  # Uno resets when the port opens
        ser.reset_input_buffer()

        f.write(f"# recorded_utc={datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        f.write(f"# baud={args.baud} cue={args.cue} settle_s={args.settle} "
                f"cue_gap_s={args.min_gap}-{args.max_gap}\n")
        writer = csv.writer(f)
        writer.writerow(COLUMNS)

        start = time.monotonic()
        cue_at = start + args.settle if args.cue else float("inf")
        pending_cue = False
        n_rows = n_cues = n_bad = 0
        print(f"Recording {args.seconds:.0f} s to {args.out}. Relax; "
              + (f"blink only when you see BLINK (first cue after {args.settle:.0f} s)." if args.cue else "no cues."))

        while (now := time.monotonic()) - start < args.seconds:
            if now >= cue_at:
                print("\a  BLINK", flush=True)
                pending_cue = True
                n_cues += 1
                cue_at = next_cue_time(now, args.min_gap, args.max_gap)
            sample = parse_line(ser.readline())
            if sample is None:
                n_bad += 1
                continue
            writer.writerow([f"{time.monotonic() - start:.6f}", sample[0], sample[1], int(pending_cue)])
            pending_cue = False
            n_rows += 1

    print(f"Done: {n_rows} samples, {n_cues} cues, {n_bad} skipped lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

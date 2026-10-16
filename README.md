# Blink detection from a single EOG/EEG channel

An Arduino Uno samples one forehead biopotential channel and streams it to a laptop. Python filters the signal and detects eye blinks with a threshold detector, as a building block for touchless interaction.

> **Status:** the code is complete and tested on synthetic signals. Measured results will be added once the recordings described below exist. Until then this README reports no accuracy numbers.

## Hardware and wiring

| Part | Notes |
|---|---|
| Arduino Uno R3 | 10-bit ADC, USB serial |
| Biopotential amplifier | **TODO: sensor model** (single channel, analog output centred on mid-supply) |
| 3 electrodes | measuring, reference, ground |

```
Amplifier OUT  -> Arduino A0
Amplifier VCC  -> 5V
Amplifier GND  -> GND
Electrodes: measuring above one eyebrow (Fp1/Fp2 area), reference and ground per the amplifier's docs
```

Run the laptop on battery while recording, and don't wear electrodes while a device is plugged into mains power.

Firmware settings are named constants at the top of [`firmware/blink_acquisition/blink_acquisition.ino`](firmware/blink_acquisition/blink_acquisition.ino): `SIGNAL_PIN = A0`, `SAMPLE_RATE_HZ = 250`, `BAUD_RATE = 115200`.

## Run it on sample data (no hardware)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python demo.py              # recording in data/sample/ (not added yet)
python demo.py --synthetic  # generated signal; shows the pipeline runs, not a result
pytest -q
```

Each demo writes `results/metrics.json` and `results/signal.png`, a plot of the raw and filtered signal with cues and detections marked.

## Record and evaluate your own data

```bash
# 1. Upload the sketch with the Arduino IDE, then record (blink only when BLINK appears):
python -m acquisition.logger --port /dev/cu.usbmodem1101 --seconds 120 --cue \
    --out data/recordings/train/s01_r01.csv

# 2. Choose the threshold on training recordings, then score held-out ones:
python -m evaluation.evaluate --tune data/recordings/train/*.csv \
    --test data/recordings/test/*.csv --out results/
```

The evaluator refuses to run if a file appears in both sets.

## How it works

```
electrodes -> amplifier -> Arduino A0 (250 Hz, 10-bit)
           -> USB serial "board_time_us,value"
           -> acquisition/logger.py  (CSV + BLINK cue labels)
           -> processing/filters.py  baseline removal (median of first 10 s)
                                     1st-order high-pass 0.1 Hz + 4th-order low-pass 10 Hz (causal)
           -> processing/detector.py threshold = median + k * robust SD of the calibration window
                                     detection = upward crossing, 0.4 s refractory
           -> evaluation/evaluate.py match to cues within 1.5 s: precision, recall, F1, latency
```

All filtering is causal (`scipy.signal.sosfilt`), so a detection at time *t* uses only samples up to *t*. The same code could therefore run live.

Latency is measured as detection time minus cue time. On real recordings it includes the participant's reaction time to the cue, so it is an upper bound on the algorithm's own delay.

## Measured results

None yet. When recordings exist, this section will list the exact dataset (participants, recordings, minutes, number of cued blinks, train/test split) next to the output of `evaluation/evaluate.py`.

## Limitations

- One channel, one detector (threshold). There is no machine-learning model.
- Spontaneous blinks during a cued recording have no label, so they count as false positives. This lowers measured precision.
- Polarity (`--polarity pos|neg|both`) depends on where the electrodes sit. Check it on the plot before evaluating.
- The 0.1 Hz high-pass leaves slow drift in the signal. Large electrode movement can still cross the threshold.
- Labels come from cue times, not from annotated blink onsets.

## Next steps

- Record a labelled dataset and publish the results here.
- Add a manual annotation step so spontaneous blinks get labels too.
- With enough labelled data, compare the threshold baseline against a windowed-feature classifier (logistic regression or random forest).
- Add a real-time mode that runs the detector on the live serial stream.

## Repository layout

```
firmware/     Arduino sketch
acquisition/  serial logger -> CSV
processing/   filters, detector, recording loader, synthetic test signal
evaluation/   metrics and plot
tests/        pytest on synthetic signals
data/sample/  small anonymised recording for the demo (to be added)
demo.py       end-to-end demo
```

# Audio QA (v0.2)

A small command‑line tool for batch‑checking audio files for loudness and basic technical quality.

It reads WAV / AIFF / FLAC / M4A / MP3, measures **LUFS (approximate BS.1770)**, **SNR** and **Crest Factor**, and uses a simple rules file (`thresholds.yaml`) to label each file as **PASS / WARN / FAIL**.  
Results can be written to **Markdown** (for humans) and **JSON** (for scripts/CI). A few lightweight tests help check that the metrics move in the expected direction.

---

## Quick Start (conda)

```bash
conda create -n audioqa python=3.12 -y && conda activate audioqa
conda install -c conda-forge numpy pyloudnorm pysoundfile pydub pyyaml tqdm pytest ffmpeg -y

# make some demo audio
python examples/make_calibrations.py

# run a batch
python main.py batch examples/audio \
  --thresholds thresholds.yaml \
  --out reports/report.md \
  --out-json reports/results.json

# run tests
pytest -q
```

---

## How to Use

### Analyse a single file

```bash
python main.py analyze examples/audio/sine_1k.wav --thresholds thresholds.yaml
```

This prints:

- a JSON blob with all the metrics, and  
- a line of `JUDGEMENT: {...}` based on `thresholds.yaml`.

### Batch process with timestamped reports

```bash
ts=$(date '+%Y%m%d-%H%M%S')
python main.py batch examples/audio \
  --thresholds thresholds.yaml \
  --out "reports/report-$ts.md" \
  --out-json "reports/results-$ts.json" \
  --jobs 4

open "reports/report-$ts.md"
```

In CI or regression testing, you can treat the generated JSON as a **baseline**: keep a known‑good `results-*.json` file under version control, and compare new batch runs against it to spot changes in metrics or verdicts.

---

## Threshold Keys Reference

`thresholds.yaml` describes what “good enough” means for your use case.  
Each key below controls one metric. You can set:

- `min`, `max` → PASS band  
- optional `warn_min`, `warn_max` → softer edges around the PASS band

| Threshold Key           | Description                                                    | Typical Values / Units         | Purpose                                                |
|------------------------|----------------------------------------------------------------|--------------------------------|--------------------------------------------------------|
| `lufs`                 | Integrated loudness (LUFS, per ITU-R BS.1770)                  | min: -24.0, max: -16.0         | Overall programme loudness                             |
| `snr_db`               | Signal-to-noise ratio (dB, hybrid estimation)                  | min: 20.0                      | How far the signal sits above the noise floor          |
| `crest_db`             | Crest factor (dB)                                              | max: 18.0                      | Peak vs average; very low can mean heavy limiting      |
| `true_peak_dbfs`       | True peak level (dBFS, 4× oversample approx)                   | max: -1.0                      | Headroom to digital full scale                         |
| `lra`                  | Loudness range (LRA, dB)                                       | max: 12.0                      | Loudness dynamics over time                            |
| `channel_imbalance_db` | Channel imbalance (dB)                                         | max: 1.0                       | Level difference between L/R                           |
| `lr_corr`              | L/R correlation coefficient                                    | min: 0.85                      | Stereo correlation; very low may indicate phase issues |
| `rms_dbfs`             | Root mean square level (dBFS)                                  | min: -80.0                     | Used for the “silence gate”                            |
| `peak_dbfs`            | Sample peak level (dBFS)                                       | min: -60.0                     | Also used for the “silence gate”                       |

> You don’t need to set every key. Only configure the ones you care about.

---

## Decision Rules

The checker is intentionally simple and predictable.

### Threshold logic

For a given metric:

- `min ≤ value ≤ max` → **PASS**  
- `warn_min ≤ value < min` or `max < value ≤ warn_max` → **WARN** (if `warn_*` exists)  
- everything outside that → **FAIL**

If the tool can’t sensibly compute a metric (e.g. the clip is too short or not suitable), that metric is marked as **NA** and does **not** affect PASS/FAIL for that file.

### SNR (hybrid) logic

- If the audio clearly has quiet sections, SNR is estimated from time‑domain frame statistics (low‑energy frames as noise, high‑energy frames as signal).  
- If the signal behaves more like a single tone, the code falls back to a narrow‑band spectral estimate.  
- If neither looks reliable, SNR is reported as **NA**.

### Silence gate

To avoid silently accepting “empty” content:

- If `RMS < -80 dBFS` **or** `Peak < -60 dBFS`, the file is automatically marked **FAIL** as “near‑silence / missing content”, regardless of other metrics.

### Example thresholds (same as the demo)

```yaml
lufs:
  min: -24.0
  max: -16.0
  warn_min: -26.0
  warn_max: -14.0

snr_db:
  min: 20.0
  warn_min: 18.0

crest_db:
  max: 18.0
  warn_max: 20.0
```

---

## What This Tool Can Catch

Typical issues it helps flag:

1. **Inconsistent loudness** — LUFS outside the target window means material doesn’t sit at a consistent level.  
2. **Raised noise floor** — Low SNR suggests line, room, or codec noise.  
3. **Over‑compression / potential clipping** — Very small crest factor hints at hard or brick‑wall limiting.  
4. **Missing or almost‑silent content** — The silence gate forces obviously “dead” material to FAIL.  
5. **Encoding / format differences** — M4A/MP3 are decoded through ffmpeg so metrics stay comparable.  
6. **Channel / stereo issues** — Channel imbalance and low L/R correlation help catch wiring or polarity mistakes.

---

## Notes

- dBFS is normalised so that 1.0 is full scale. Multi‑channel files are downmixed for the main table; per‑channel metrics are written in a separate section when available.  
- LUFS is computed via `pyloudnorm`, which follows the ITU‑R BS.1770 / EBU R128 loudness model.  
- In batch mode, if **any** file FAILs, the process exits with a non‑zero code so CI pipelines can fail on QA problems.  
- You can always check the version with:
  ```bash
  python main.py --version
  ```

---

## Testing & CI

- Run the unit tests (including simple monotonicity checks for RMS/LUFS/SNR) with:
  ```bash
  pytest -q
  ```
- In CI, call the batch command and rely on the non‑zero exit code whenever any file FAILs, for example:
  ```bash
  python main.py batch examples/audio \
    --thresholds thresholds.yaml \
    --out reports/report-ci.md \
    --out-json reports/results-ci.json
  ```
- For stricter regression testing, keep a known‑good JSON report under version control and compare new `results-*.json` files against it to detect unexpected changes in metrics or verdicts.
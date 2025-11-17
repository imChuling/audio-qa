import sys
from pathlib import Path

import numpy as np

# Add the project root (where metrics.py lives) to sys.path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metrics import (
    rms_dbfs,
    r128_loudness_and_lra,
    snr_db,
)


def _make_tone(freq=1000.0, level=0.1, sr=48000, dur_s=2.0):
    """Generate a simple sine tone for monotonicity tests."""
    n = int(sr * dur_s)
    t = np.linspace(0.0, dur_s, n, endpoint=False, dtype=np.float32)
    y = np.sin(2.0 * np.pi * freq * t).astype(np.float32)
    return (y * level).astype(np.float32), sr


def _make_noise(level=0.1, sr=48000, dur_s=2.0):
    """Generate white noise at a given level."""
    n = int(sr * dur_s)
    rng = np.random.default_rng(42)
    y = rng.standard_normal(n).astype(np.float32)
    y = y / np.max(np.abs(y) + 1e-12)
    return (y * level).astype(np.float32), sr


def test_rms_monotonic_with_gain():
    """Louder signals should have higher (less negative) RMS dBFS."""
    y1, sr = _make_tone(level=0.1)
    y2, _ = _make_tone(level=0.5, sr=sr)

    rms1 = rms_dbfs(y1)
    rms2 = rms_dbfs(y2)

    # y2 is about +14 dB relative to y1; we only check that the direction is correct
    assert rms2 > rms1 + 3.0


def test_lufs_monotonic_with_gain():
    """Louder signals should report higher (less negative) LUFS."""
    y1, sr = _make_tone(level=0.1)
    y2, _ = _make_tone(level=0.5, sr=sr)

    L1, _, _, _ = r128_loudness_and_lra(y1, sr)
    L2, _, _, _ = r128_loudness_and_lra(y2, sr)

    # Louder signals should produce LUFS values closer to 0
    assert L2 > L1 + 3.0


def test_snr_tone_vs_noise():
    """
    SNR for tone + noise should be higher than for noise alone,
    when both estimates are available.
    """
    # Base noise floor
    noise, sr = _make_noise(level=0.05)
    # Add a 1 kHz tone on top of the same noise
    tone, _ = _make_tone(level=0.3, sr=sr)
    mix = noise + tone
    mix = np.clip(mix, -1.0, 1.0)

    snr_noise = snr_db(noise, sr)
    snr_mix = snr_db(mix, sr)

    # In some cases snr_db may return None (e.g. if conditions are not met).
    # Here we assert: if both are defined, the mixed signal should have higher SNR.
    if snr_noise is not None and snr_mix is not None:
        assert snr_mix > snr_noise
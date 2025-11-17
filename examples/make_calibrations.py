# examples/make_calibrations.py
"""
Generate a few simple WAV files used as calibration / demo signals:

- silence.wav         : 2 s of digital silence
- sine_1k.wav         : 1 kHz sine at about -14 dBFS peak / -17 dBFS RMS
- sine_1k_noise.wav   : same sine with a small amount of added white noise
"""

import os

import numpy as np
import soundfile as sf

# Create the output directory for demo audio
os.makedirs("examples/audio", exist_ok=True)

sr = 48000
t = np.arange(sr * 2) / sr  # 2 seconds at 48 kHz

# 1 kHz sine tone at peak 0.2 (~ -14 dBFS peak, ~ -17 dBFS RMS)
sine = 0.2 * np.sin(2 * np.pi * 1000 * t)

# Low-level white noise to make a simple SNR example
noise = 0.02 * np.random.randn(len(t))

# Write three WAV files: silence, pure sine, and sine + noise
sf.write("examples/audio/silence.wav", np.zeros_like(t, dtype=np.float32), sr)
sf.write("examples/audio/sine_1k.wav", sine.astype("float32"), sr)
sf.write("examples/audio/sine_1k_noise.wav", (sine + noise).astype("float32"), sr)

print("Wrote examples/audio/*.wav")

# audio_io.py - audio loading helpers (mono & multi-channel)

import os
import shutil

import numpy as np
import soundfile as sf

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except Exception:
    HAS_PYDUB = False

FFMPEG_BIN = shutil.which("ffmpeg")
if HAS_PYDUB and FFMPEG_BIN:
    # Ensure pydub knows where ffmpeg/ffprobe are
    AudioSegment.converter = FFMPEG_BIN
    AudioSegment.ffmpeg = FFMPEG_BIN
    AudioSegment.ffprobe = shutil.which("ffprobe") or FFMPEG_BIN


def read_audio(path):
    """
    Read an audio file, downmix to mono and return (y_mono, sr).

    - Prefer soundfile for uncompressed formats (WAV/AIFF/FLAC, etc.)
    - Fall back to pydub + ffmpeg for common compressed formats (M4A/MP3/AAC/MP4)

    The returned array is float32 in roughly the [-1, 1] range.
    """
    ext = os.path.splitext(path)[1].lower()
    try:
        y, sr = sf.read(path, always_2d=False)
        if getattr(y, "ndim", 1) > 1:
            y = y.mean(axis=1)
        return np.asarray(y, np.float32), sr
    except Exception:
        if ext in (".m4a", ".mp3", ".aac", ".mp4"):
            if not HAS_PYDUB:
                raise RuntimeError(
                    f"Cannot read {path}: pydub not installed. "
                    "In your env run: `conda install -c conda-forge pydub ffmpeg -y`"
                )
            if FFMPEG_BIN is None:
                raise RuntimeError(
                    f"Cannot read {path}: ffmpeg not found on PATH. "
                    "In your env run: `conda install -c conda-forge ffmpeg -y`"
                )
            aud = AudioSegment.from_file(path)
            sr = aud.frame_rate
            ch = aud.channels
            arr = np.array(aud.get_array_of_samples())
            scale = float(1 << (8 * aud.sample_width - 1))
            y = (arr.astype(np.float32) / scale)
            if ch > 1:
                y = y.reshape(-1, ch).mean(axis=1)
            return y, sr
        raise


def read_audio_multi(path):
    """
    Read an audio file as multi-channel and return (y_multi, sr), where y_multi has shape (N, C).

    - Prefer soundfile for uncompressed formats (WAV/AIFF/FLAC, etc.)
    - Fall back to pydub + ffmpeg for common compressed formats (M4A/MP3/AAC/MP4)

    The returned array is float32 with channels along the last axis.
    """

    ext = os.path.splitext(path)[1].lower()
    try:
        y, sr = sf.read(path, always_2d=True)  # (N, C)
        return np.asarray(y, np.float32), sr
    except Exception:
        if ext in (".m4a", ".mp3", ".aac", ".mp4"):
            if not HAS_PYDUB or FFMPEG_BIN is None:
                raise
            aud = AudioSegment.from_file(path)
            sr = aud.frame_rate
            ch = aud.channels
            arr = np.array(aud.get_array_of_samples(), dtype=np.float32)
            scale = float(1 << (8 * aud.sample_width - 1))
            y = (arr / scale).reshape(-1, ch)  # (N, C)
            return y, sr
        raise
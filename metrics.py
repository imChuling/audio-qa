# metrics.py - audio metrics: dBFS, LUFS, SNR, True Peak, per-channel, ...

import math
import numpy as np
import pyloudnorm as pyln

from typing import Tuple, Optional, List, Dict, Any


def rms_dbfs(y: np.ndarray) -> float:
    rms = np.sqrt(np.mean(np.square(y))) + 1e-12
    return 20 * math.log10(rms)


def peak_dbfs(y: np.ndarray) -> float:
    peak = np.max(np.abs(y)) + 1e-12
    return 20 * math.log10(peak)


def crest_db(peak_db: float, rms_db: float) -> float:
    return peak_db - rms_db


def lufs_integrated(y: np.ndarray, sr: int) -> float:
    meter = pyln.Meter(sr)
    return meter.integrated_loudness(y)


def snr_db(y: np.ndarray, sr: int) -> Optional[float]:
    """
    Hybrid SNR estimator.

    - If the signal has clear low-energy / silent segments, use a time-domain percentile method
      (works well for speech and ambience).
    - Otherwise, fall back to a narrow-band spectral estimate that only returns a value for
      near single-tone material.
    - If no reliable estimate can be made, return None (reported as NA in the report).
    """
    n = len(y)
    if n < int(0.5 * sr):  # do not evaluate if shorter than 0.5 s
        return None

    # ---------- time-domain percentile method ----------
    frame = max(1, int(0.05 * sr))  # 50 ms frame
    frames = np.array([np.mean(y[i:i + frame] ** 2) for i in range(0, n, frame)], dtype=float)
    frames = frames[frames > 0]
    if len(frames) >= 10:
        p10 = np.percentile(frames, 10)
        p20 = np.percentile(frames, 20)
        p80 = np.percentile(frames, 80)
        p90 = np.percentile(frames, 90)
        dyn_db = 10.0 * np.log10((p90 + 1e-12) / (p10 + 1e-12))
        low_count = int(np.sum(frames <= p20))
        high_count = int(np.sum(frames >= p80))
        if dyn_db >= 6.0 and low_count >= 5 and high_count >= 5:
            noise_power = float(np.mean(frames[frames <= p20])) + 1e-12
            sig_power = float(np.mean(frames[frames >= p80])) + 1e-12
            return 10.0 * np.log10(sig_power / noise_power)

    # ---------- spectral method (only for tone-like material) ----------
    nfft = 1 << int(np.floor(np.log2(min(n, 262144))))
    if nfft < 4096:
        return None
    x = y[:nfft].astype(np.float64)
    w = np.hanning(nfft)
    X = np.fft.rfft(x * w)
    psd = (X.real ** 2 + X.imag ** 2) / (np.sum(w ** 2) + 1e-12)
    psd[0] = 0.0
    pk = int(np.argmax(psd))
    med = float(np.median(psd[1:]))

    # Require a very prominent line to treat as a tone, to avoid misclassifying music/speech
    if med <= 0 or psd[pk] < 20.0 * med:
        return None

    sig = psd[max(1, pk - 1): pk + 2].sum()
    noise = psd.sum() - sig + 1e-12
    return 10.0 * np.log10(sig / noise)


# --- R128: Integrated / Short-term / Momentary / LRA ---
def r128_loudness_and_lra(
    y: np.ndarray, sr: int
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    y = np.asarray(y, np.float64)
    meter = pyln.Meter(sr)  # BS.1770 + R128 gating

    # Integrated
    L_i = meter.integrated_loudness(y)

    # Short-term (3 s) / Momentary (400 ms): take P95 of finite values for robustness to spikes/NaNs
    def _p95(series):
        if series is None:
            return None
        series = np.asarray(series, dtype=float)
        series = series[np.isfinite(series)]
        if series.size == 0:
            return None
        return float(np.nanpercentile(series, 95))

    try:
        L_s = _p95(meter.loudness_shortterm(y))
    except Exception:
        L_s = None
    try:
        L_m = _p95(meter.loudness_momentary(y))
    except Exception:
        L_m = None

    # LRA: can be unstable on very short clips; treat invalid results as None
    try:
        LRA = float(meter.loudness_range(y))
        if not np.isfinite(LRA):
            LRA = None
    except Exception:
        LRA = None

    return L_i, L_s, L_m, LRA


# --- True Peak (4× oversampling approximation) ---
def true_peak_dbfs(y: np.ndarray, sr: int, os_factor: int = 4) -> Optional[float]:
    x = np.asarray(y, np.float64)
    if x.size == 0:
        return None

    peak = float(np.max(np.abs(x)))
    # Linear interpolation 4× oversampling (engineering approximation; can be replaced by a higher-order scheme)
    if os_factor > 1 and x.size > 1:
        t = np.arange(x.size, dtype=np.float64)
        t_up = np.linspace(0.0, x.size - 1.0, x.size * os_factor)
        x_up = np.interp(t_up, t, x)
        peak = max(peak, float(np.max(np.abs(x_up))))
    if not math.isfinite(peak) or peak <= 0:
        return None
    return 20.0 * math.log10(peak)


def per_channel_metrics(y_multi: np.ndarray, sr: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    N, C = y_multi.shape
    rows: List[Dict[str, Any]] = []

    for c in range(C):
        yc = y_multi[:, c]
        pk = peak_dbfs(yc)
        rms = rms_dbfs(yc)
        cr = crest_db(pk, rms)
        try:
            Li, Ls, Lm, LRA = r128_loudness_and_lra(yc, sr)
        except Exception:
            Li = Ls = Lm = LRA = None
        rows.append(
            {
                "ch": c,
                "peak_dbfs": pk,
                "rms_dbfs": rms,
                "crest_db": cr,
                "lufs": Li,
                "lufs_s": Ls,
                "lufs_m": Lm,
                "lra": LRA,
            }
        )

    # Stereo / multichannel consistency checks (light-weight)
    extra: Dict[str, Any] = {}
    if C >= 2:
        L, R = y_multi[:, 0], y_multi[:, 1]
        if np.std(L) > 1e-12 and np.std(R) > 1e-12:
            corr = float(np.corrcoef(L, R)[0, 1])
        else:
            corr = None

        Lrms, Rrms = rms_dbfs(L), rms_dbfs(R)
        imb = None
        if math.isfinite(Lrms) and math.isfinite(Rrms):
            imb = abs(Lrms - Rrms)

        extra.update({"lr_corr": corr, "channel_imbalance_db": imb})

    # Dead-channel detection
    silent_idx = []
    for i, r in enumerate(rows):
        if (r["rms_dbfs"] is not None and r["rms_dbfs"] < -80.0) or (
            r["peak_dbfs"] is not None and r["peak_dbfs"] < -60.0
        ):
            silent_idx.append(i)
    extra["silent_channels"] = silent_idx

    return rows, extra
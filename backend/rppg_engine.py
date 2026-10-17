"""
SatyaSpandan rPPG engine: remote photoplethysmography + spatial pulse coherence.

Pipeline (see implementation.md, section 6):
    1. Ingest       cv2.VideoCapture, true FPS, optional VFR resampling
    2. Landmarks    MediaPipe FaceLandmarker (478 pts) -> forehead / left / right
                    cheek ROIs + 2 background patches -> mean RGB per frame
    3. Pulse        GREEN | CHROM | POS per ROI
    4. Filter       detrend -> 5th-order Butterworth 0.7-3.0 Hz (sosfiltfilt)
    5. Spectrum     periodogram, BPM, SNR, background-subtracted PSD
    6. Coherence    Pearson r, magnitude-squared coherence, CPSD phase lag and
                    per-ROI BPM agreement between all ROI pairs, per window
    7. Decision     quality gate -> "Unable to assess", else coherence score
                    vs threshold -> "No strong signs" / "Possible manipulation"

Methods follow the original papers:
    GREEN  Verkruysse, Svaasand & Nelson, Optics Express 2008
    CHROM  de Haan & Jeanne, IEEE TBME 2013
    POS    Wang, den Brinker, Stuijk & de Haan, IEEE TBME 2017
    SNR    harmonic-power definition as used by rPPG-Toolbox (Liu et al. 2023)
    Filter, 10 s window and background subtraction: Seibold et al. 2025
    Spatial coherence features: Ciftci, Demir & Yin (FakeCatcher), TPAMI 2020

The verdict is a probabilistic warning sign, never proof.
"""

from __future__ import annotations

import base64
import math
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
from scipy import signal

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

VERDICTS = {
    "real": "No strong signs detected",
    "manip": "Possible manipulation detected",
    "unable": "Unable to assess",
}

ROI_NAMES = ("forehead", "left", "right")
ROI_PAIRS = (("left", "right"), ("left", "forehead"), ("right", "forehead"))
ROI_LABELS = {"forehead": "forehead", "left": "left cheek", "right": "right cheek"}

# MediaPipe 478-point face mesh indices. "left"/"right" = the subject's side.
# The convex hull of each set is used as the ROI polygon.
ROI_LANDMARKS = {
    "forehead": [10, 338, 297, 299, 296, 336, 9, 107, 66, 69, 67, 109],
    "left": [345, 346, 347, 348, 349, 329, 371, 266, 425, 411, 352],
    "right": [116, 117, 118, 119, 120, 100, 142, 36, 205, 187, 123],
}
EYE_OUTER = (33, 263)  # inter-ocular distance = face scale

# BGR colours for the overlay
ROI_COLORS = {
    "forehead": (0, 170, 255),   # amber
    "left": (255, 140, 30),      # blue
    "right": (200, 60, 220),     # magenta
    "background": (150, 150, 150),
}

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_landmarker.task")

ProgressFn = Optional[Callable[[float, str], None]]


# --------------------------------------------------------------------------
# Configuration and result containers
# --------------------------------------------------------------------------

@dataclass
class EngineConfig:
    method: str = "POS"                 # "GREEN" | "CHROM" | "POS"
    band_hz: tuple = (0.7, 3.0)         # 42-180 bpm (Seibold et al. 2025)
    filter_order: int = 5
    window_s: float = 10.0              # analysis window (Seibold: best HR stability at 10 s)
    step_s: float = 2.0
    min_duration_s: float = 6.0
    max_duration_s: float = 30.0
    max_width: int = 640
    model_path: str = DEFAULT_MODEL_PATH

    # quality gate
    min_face_ratio: float = 0.80
    min_face_px: float = 40.0           # inter-ocular distance in original pixels
    max_median_motion: float = 0.05     # landmark shift / inter-ocular distance per frame
    max_fast_motion_frac: float = 0.30  # share of frames with motion > 0.10
    min_snr_db: float = -1.0
    max_bg_ratio: float = 0.5
    max_bg_corr: float = 0.6

    # decision (tau is replaced by tools/calibrate.py output when available)
    threshold: float = 55.0
    min_frac_coherent: float = 0.6
    bpm_tol: float = 7.0                # ~ one spectral bin at 10 s, plus rounding
    max_lag_ms: float = 150.0
    hr_jump_bpm: float = 15.0
    hr_jump_penalty: float = 5.0


@dataclass
class AnalysisResult:
    verdict: str
    verdict_key: str                    # "real" | "manip" | "unable"
    risk_level: str                     # "Low" | "Medium" | "High" | "—"
    confidence: str                     # "High" | "Medium" | "Low" | "—"
    bpm: Optional[float]
    coherence_score: Optional[float]
    snr_db: Optional[float]
    reasons: list
    quality: dict
    fps: float
    method: str
    threshold: float
    t: np.ndarray = field(default_factory=lambda: np.zeros(0))
    signals: dict = field(default_factory=dict)
    psd: dict = field(default_factory=dict)
    windows: list = field(default_factory=list)
    pairs: dict = field(default_factory=dict)
    overlay_frame: Optional[np.ndarray] = None

    def to_dict(self, max_points: int = 600) -> dict:
        """JSON-ready dict: downsampled waves, PSD limited to 30-240 bpm, overlay as base64 JPEG."""
        n = len(self.t)
        idx = np.unique(np.linspace(0, n - 1, min(n, max_points)).astype(int)) if n else np.zeros(0, int)
        sig = {k: _round_list(np.asarray(v)[idx]) for k, v in self.signals.items()} if n else {k: [] for k in ROI_NAMES}
        overlay_b64 = None
        if self.overlay_frame is not None:
            import cv2
            ok, buf = cv2.imencode(".jpg", self.overlay_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                overlay_b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        psd = {}
        if self.psd:
            bpm_axis = np.asarray(self.psd["bpm_axis"])
            keep = (bpm_axis >= 30) & (bpm_axis <= 240)
            psd = {k: _round_list(np.asarray(v)[keep]) for k, v in self.psd.items()}
        return {
            "verdict": self.verdict,
            "verdict_key": self.verdict_key,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "bpm": _round(self.bpm, 1),
            "coherence_score": _round(self.coherence_score, 1),
            "snr_db": _round(self.snr_db, 2),
            "reasons": self.reasons,
            "quality": {k: _round(v, 4) for k, v in self.quality.items()},
            "fps": _round(self.fps, 3),
            "method": self.method,
            "threshold": self.threshold,
            "t": _round_list(self.t[idx]) if n else [],
            "signals": sig,
            "psd": psd,
            "windows": [{k: _round(v, 4) for k, v in w.items()} for w in self.windows],
            "pairs": {k: {kk: _round(vv, 4) for kk, vv in v.items()} for k, v in self.pairs.items()},
            "overlay_jpeg_b64": overlay_b64,
        }


def _round(x, nd=3):
    if x is None:
        return None
    x = float(x)
    return None if not math.isfinite(x) else round(x, nd)


def _round_list(a, nd=4):
    return [round(float(v), nd) if math.isfinite(v) else 0.0 for v in np.asarray(a, dtype=float)]


# --------------------------------------------------------------------------
# Stage 3: pulse extraction
# --------------------------------------------------------------------------

def pulse_green(rgb: np.ndarray, fs: float) -> np.ndarray:
    """GREEN (Verkruysse 2008): the green channel carries the strongest PPG."""
    return rgb[:, 1].astype(float)


def pulse_pos(rgb: np.ndarray, fs: float, win_s: float = 1.6) -> np.ndarray:
    """POS (Wang et al. 2017): project normalised RGB onto the plane orthogonal to skin tone."""
    rgb = np.asarray(rgb, dtype=float)
    n = len(rgb)
    l = int(math.ceil(win_s * fs))
    h_out = np.zeros(n)
    proj = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])
    for end in range(l, n + 1):
        start = end - l
        block = rgb[start:end]
        mean = block.mean(axis=0)
        if np.any(mean <= 0):
            continue
        cn = block / mean                      # temporal normalisation
        s = cn @ proj.T                        # (l, 2)
        s0, s1 = s[:, 0], s[:, 1]
        sd1 = s1.std()
        alpha = s0.std() / sd1 if sd1 > 1e-12 else 0.0
        h = s0 + alpha * s1
        h_out[start:end] += h - h.mean()       # overlap-add
    return h_out


def pulse_chrom(rgb: np.ndarray, fs: float, win_s: float = 1.6, band=(0.7, 3.0)) -> np.ndarray:
    """CHROM (de Haan & Jeanne 2013): chrominance signals X, Y with alpha tuning, Hann overlap-add."""
    rgb = np.asarray(rgb, dtype=float)
    n = len(rgb)
    wl = int(math.ceil(win_s * fs))
    wl += wl % 2
    half = wl // 2
    hi = min(band[1], 0.45 * fs)
    sos = signal.butter(3, [band[0], hi], btype="bandpass", fs=fs, output="sos")
    hann = signal.windows.hann(wl)
    out = np.zeros(n)
    start = 0
    while start + wl <= n:
        block = rgb[start:start + wl]
        mean = block.mean(axis=0)
        if np.all(mean > 0):
            cn = block / mean
            x = 3.0 * cn[:, 0] - 2.0 * cn[:, 1]
            y = 1.5 * cn[:, 0] + cn[:, 1] - 1.5 * cn[:, 2]
            padlen = min(3 * (2 * len(sos) + 1), wl - 1)
            xf = signal.sosfiltfilt(sos, x, padlen=padlen)
            yf = signal.sosfiltfilt(sos, y, padlen=padlen)
            sy = yf.std()
            alpha = xf.std() / sy if sy > 1e-12 else 0.0
            out[start:start + wl] += (xf - alpha * yf) * hann
        start += half
    return out


PULSE_METHODS = {"GREEN": pulse_green, "CHROM": pulse_chrom, "POS": pulse_pos}


def extract_pulse(rgb: np.ndarray, fs: float, method: str = "POS", band=(0.7, 3.0)) -> np.ndarray:
    method = method.upper()
    if method == "CHROM":
        return pulse_chrom(rgb, fs, band=band)
    if method not in PULSE_METHODS:
        raise ValueError(f"Unknown method {method!r}; use GREEN, CHROM or POS")
    return PULSE_METHODS[method](rgb, fs)


# --------------------------------------------------------------------------
# Stage 4: filtering
# --------------------------------------------------------------------------

def effective_band(fs: float, band=(0.7, 3.0)) -> tuple:
    """Keep the upper edge below Nyquist for low-FPS clips."""
    return (band[0], min(band[1], 0.45 * fs))


def bandpass(x: np.ndarray, fs: float, band=(0.7, 3.0), order: int = 5) -> np.ndarray:
    """detrend -> zero-phase Butterworth band-pass -> z-normalise."""
    x = np.asarray(x, dtype=float)
    if len(x) < 8 or not np.all(np.isfinite(x)):
        return np.zeros_like(x)
    x = signal.detrend(x, type="linear")
    lo, hi = effective_band(fs, band)
    sos = signal.butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")
    padlen = min(3 * (2 * len(sos) + 1), len(x) - 1)
    x = signal.sosfiltfilt(sos, x, padlen=padlen)
    sd = x.std()
    return (x - x.mean()) / sd if sd > 1e-12 else np.zeros_like(x)


# --------------------------------------------------------------------------
# Stage 5: spectrum, BPM, SNR
# --------------------------------------------------------------------------

def _next_pow2(n: int) -> int:
    return 1 if n <= 1 else 2 ** int(math.ceil(math.log2(n)))


def psd(x: np.ndarray, fs: float, nfft: Optional[int] = None):
    nfft = nfft or max(_next_pow2(len(x)) * 2, 256)
    f, p = signal.periodogram(x, fs=fs, nfft=nfft, detrend=False)
    return f, p


def band_mask(f: np.ndarray, band) -> np.ndarray:
    return (f >= band[0]) & (f <= band[1])


def normalise_in_band(f, p, band) -> np.ndarray:
    """Scale a PSD to unit area inside the band (so face and background are comparable)."""
    m = band_mask(f, band)
    area = p[m].sum()
    return p / area if area > 1e-20 else np.zeros_like(p)


def peak_freq(f, p, band) -> float:
    m = band_mask(f, band)
    if not np.any(m) or p[m].max() <= 0:
        return float("nan")
    return float(f[m][np.argmax(p[m])])


def snr_db(f, p, f_hr: float, band, dev_hz: float = 0.1) -> float:
    """Power within +/-6 bpm of the 1st and 2nd harmonics vs the rest of the band (dB)."""
    if not math.isfinite(f_hr):
        return float("nan")
    inb = band_mask(f, band)
    h1 = np.abs(f - f_hr) <= dev_hz
    h2 = np.abs(f - 2 * f_hr) <= dev_hz
    sig = p[inb & (h1 | h2)].sum()
    rest = p[inb & ~(h1 | h2)].sum()
    if rest <= 0 or sig <= 0:
        return float("nan")
    return float(10 * np.log10(sig / rest))


# --------------------------------------------------------------------------
# Stage 6: spatial coherence
# --------------------------------------------------------------------------

def pair_metrics(xa: np.ndarray, xb: np.ndarray, fs: float, f_hr: float, band) -> dict:
    """Pearson r, magnitude-squared coherence and CPSD phase lag at the heart-rate frequency."""
    r = float(np.corrcoef(xa, xb)[0, 1]) if xa.std() > 0 and xb.std() > 0 else 0.0
    nper = int(min(len(xa), max(16, round(4 * fs))))
    f, c = signal.coherence(xa, xb, fs=fs, nperseg=nper)
    near = np.abs(f - f_hr) <= 0.15
    if not np.any(near):
        near = np.array([np.argmin(np.abs(f - f_hr))])
    msc = float(np.mean(c[near]))
    f2, pxy = signal.csd(xa, xb, fs=fs, nperseg=nper)
    k = int(np.argmin(np.abs(f2 - f_hr)))
    phase = float(np.angle(pxy[k]))
    lag_ms = abs(phase) / (2 * math.pi * f_hr) * 1000.0 if f_hr > 0 else float("nan")
    cpsd_mag = np.abs(pxy[band_mask(f2, band)])
    return {
        "r": r,
        "msc": msc,
        "lag_ms": lag_ms,
        "cpsd_max": float(cpsd_mag.max()) if cpsd_mag.size else 0.0,
        "cpsd_mean": float(cpsd_mag.mean()) if cpsd_mag.size else 0.0,
    }


def window_bounds(n: int, fs: float, window_s: float, step_s: float) -> list:
    wl = int(round(window_s * fs))
    st = max(1, int(round(step_s * fs)))
    if n <= wl:
        return [(0, n)]
    starts = list(range(0, n - wl + 1, st))
    if starts[-1] + wl < n:
        starts.append(n - wl)
    return [(s, s + wl) for s in starts]


# --------------------------------------------------------------------------
# Stage 7: analysis on RGB traces (video-free entry point)
# --------------------------------------------------------------------------

def analyze_traces(
    rgb: dict,
    fps: float,
    cfg: EngineConfig = EngineConfig(),
    quality: Optional[dict] = None,
    overlay_frame: Optional[np.ndarray] = None,
) -> AnalysisResult:
    """
    rgb: {"forehead": (T,3), "left": (T,3), "right": (T,3), optional "background": (T,3)}
         mean R, G, B per frame for each region.
    """
    method = cfg.method.upper()
    n = min(len(rgb[k]) for k in ROI_NAMES)
    duration = n / fps if fps > 0 else 0.0
    q = {"face_ratio": 1.0, "face_px": 100.0, "motion": 0.0, "fast_motion_frac": 0.0}
    q.update(quality or {})
    q["duration_s"] = duration
    q["fps"] = fps
    band = effective_band(fps, cfg.band_hz) if fps > 0 else cfg.band_hz

    gate_reasons = []
    if fps < 4:
        gate_reasons.append(_reason("bad_fps", "block", "The video's frame rate is too low or unreadable to measure a heartbeat."))
    if duration < cfg.min_duration_s:
        gate_reasons.append(_reason("too_short", "block",
            f"The usable clip is only {duration:.1f} s. At least {cfg.min_duration_s:.0f} seconds of clearly visible face are needed to measure a heartbeat reliably."))
    if q["face_ratio"] < cfg.min_face_ratio:
        gate_reasons.append(_reason("face_missing", "block",
            f"A face was found in only {q['face_ratio'] * 100:.0f}% of frames, so the face was not visible clearly enough."))
    if q["face_px"] < cfg.min_face_px:
        gate_reasons.append(_reason("face_small", "block", "The face is too small or too far away for skin-colour analysis."))
    if q["motion"] > cfg.max_median_motion or q["fast_motion_frac"] > cfg.max_fast_motion_frac:
        gate_reasons.append(_reason("motion", "block", "There is too much head or camera movement for a stable skin-colour reading."))

    # Too little data to process at all
    if n < max(16, int(2 * fps)) or fps < 4:
        return _unable(gate_reasons or [_reason("too_short", "block", "The clip is too short to analyse.")],
                       q, fps, method, cfg, overlay_frame)

    t = np.arange(n) / fps

    # Stage 3 + 4: pulse per ROI, pooled skin and background
    raw = {k: np.asarray(rgb[k], dtype=float)[:n] for k in ROI_NAMES}
    sig = {k: bandpass(extract_pulse(raw[k], fps, method, band), fps, band, cfg.filter_order) for k in ROI_NAMES}
    pooled_rgb = np.mean([raw[k] for k in ROI_NAMES], axis=0)
    pooled = bandpass(extract_pulse(pooled_rgb, fps, method, band), fps, band, cfg.filter_order)
    has_bg = "background" in rgb and rgb["background"] is not None and len(rgb["background"]) >= n
    bg = bandpass(np.asarray(rgb["background"], dtype=float)[:n, 1], fps, band, cfg.filter_order) if has_bg else np.zeros(n)

    # Stage 5: spectra (whole clip)
    f, p_pooled = psd(pooled, fps)
    _, p_bg = psd(bg, fps)
    pn_face = normalise_in_band(f, p_pooled, band)
    pn_bg = normalise_in_band(f, p_bg, band)
    p_clean = np.clip(pn_face - pn_bg, 0, None)
    f_raw = peak_freq(f, pn_face, band)
    f_hr = peak_freq(f, p_clean, band)
    if not math.isfinite(f_hr):
        f_hr = f_raw
    bpm = f_hr * 60 if math.isfinite(f_hr) else None
    dev = max(0.1, 1.0 / duration)              # half the spectral main-lobe width for short clips
    snr_pooled = snr_db(f, p_pooled, f_hr, band, dev)
    # Gate on the best single region: "is there a readable pulse anywhere on this face?"
    # (pooling desynchronised regions would wrongly turn a manipulated face into "unable").
    roi_psd = {k: psd(sig[k], fps)[1] for k in ROI_NAMES}
    roi_snr = {k: snr_db(f, roi_psd[k], peak_freq(f, roi_psd[k], band), band, dev) for k in ROI_NAMES}
    finite = [v for v in roi_snr.values() if math.isfinite(v)]
    snr = max(finite) if finite else float("nan")
    q.update({f"snr_{k}": v for k, v in roi_snr.items()})
    q["snr_pooled"] = snr_pooled
    # Ambient check on the best region: is its dominant oscillation also present in the background?
    best = max(ROI_NAMES, key=lambda k: roi_snr[k] if math.isfinite(roi_snr[k]) else -1e9)
    pn_best = normalise_in_band(f, roi_psd[best], band)
    f_best = peak_freq(f, pn_best, band)
    k_best = int(np.argmin(np.abs(f - f_best))) if math.isfinite(f_best) else 0
    bg_ratio = float(pn_bg[k_best] / pn_best[k_best]) if has_bg and pn_best[k_best] > 0 else 0.0
    bg_corr = float(abs(np.corrcoef(sig[best], bg)[0, 1])) if has_bg and bg.std() > 0 and sig[best].std() > 0 else 0.0
    q["snr_db"] = snr
    q["bg_ratio"] = bg_ratio
    q["bg_corr"] = bg_corr

    if not math.isfinite(snr) or snr < cfg.min_snr_db:
        gate_reasons.append(_reason("low_snr", "block",
            "The pulse signal is too weak compared with the noise. This is typical of heavily compressed, forwarded, very dark or blurry videos."))
    if has_bg and (bg_ratio > cfg.max_bg_ratio or bg_corr > cfg.max_bg_corr):
        gate_reasons.append(_reason("ambient", "block",
            "Lighting flicker or compression noise in the background looks like a pulse, so the face signal cannot be separated reliably."))

    # Per-ROI spectra for display (same normalisation as the analysis)
    psd_out = {"bpm_axis": f * 60}
    peak_ref = 0.0
    for k in ROI_NAMES:
        psd_out[k] = normalise_in_band(f, roi_psd[k], band)
        peak_ref = max(peak_ref, psd_out[k][band_mask(f, band)].max(initial=0))
    psd_out["background"] = pn_bg
    psd_out["cleaned"] = p_clean
    if peak_ref > 0:
        for k in (*ROI_NAMES, "background", "cleaned"):
            psd_out[k] = psd_out[k] / peak_ref

    # Stage 6: coherence per window
    windows = []
    pair_acc = {f"{a}-{b}": [] for a, b in ROI_PAIRS}
    for s, e in window_bounds(n, fps, cfg.window_s, cfg.step_s):
        seg = {k: sig[k][s:e] for k in ROI_NAMES}
        fw, pw = psd(pooled[s:e], fps)
        f_w = peak_freq(fw, pw, band)
        if not math.isfinite(f_w):
            f_w = f_hr
        roi_bpm = {}
        for k in ROI_NAMES:
            fk, pk = psd(seg[k], fps)
            roi_bpm[k] = peak_freq(fk, pk, band) * 60
        rs, mscs, agrees = [], [], []
        for a, b in ROI_PAIRS:
            m = pair_metrics(seg[a], seg[b], fps, f_w, band)
            m["dbpm"] = abs(roi_bpm[a] - roi_bpm[b])
            pair_acc[f"{a}-{b}"].append(m)
            rs.append(m["r"])
            mscs.append(m["msc"])
            agrees.append(m["dbpm"] <= cfg.bpm_tol and m["lag_ms"] <= cfg.max_lag_ms)
        r_bar = float(np.clip(np.mean(rs), 0, 1))
        msc_bar = float(np.mean(mscs))
        agree = float(np.mean(agrees))
        scs_w = 100 * (0.4 * r_bar + 0.4 * msc_bar + 0.2 * agree)
        windows.append({
            "t_start": s / fps, "t_end": e / fps, "scs": scs_w, "bpm": f_w * 60,
            "r_lr": rs[0], "r_lm": rs[1], "r_rm": rs[2], "msc": msc_bar, "agree": agree,
            "bpm_forehead": roi_bpm["forehead"], "bpm_left": roi_bpm["left"], "bpm_right": roi_bpm["right"],
        })

    pairs = {}
    for key, ms in pair_acc.items():
        pairs[key] = {mk: float(np.median([m[mk] for m in ms])) for mk in ms[0]}

    scs_ws = np.array([w["scs"] for w in windows])
    scs = float(np.median(scs_ws))
    jumps = np.abs(np.diff([w["bpm"] for w in windows])) if len(windows) > 1 else np.zeros(0)
    max_jump = float(jumps.max()) if jumps.size else 0.0
    if max_jump > cfg.hr_jump_bpm:
        scs = max(0.0, scs - cfg.hr_jump_penalty)
    frac_coherent = float(np.mean(scs_ws >= cfg.threshold))
    q["frac_coherent"] = frac_coherent
    q["max_hr_jump_bpm"] = max_jump

    common = dict(quality=q, fps=fps, method=method, threshold=cfg.threshold, t=t,
                  signals=sig, psd=psd_out, windows=windows, pairs=pairs, overlay_frame=overlay_frame)

    if gate_reasons:
        return AnalysisResult(verdict=VERDICTS["unable"], verdict_key="unable", risk_level="—", confidence="—",
                              bpm=bpm, coherence_score=scs, snr_db=snr,
                              reasons=gate_reasons + [_caveat()], **common)

    # Stage 7: verdict
    is_real = scs >= cfg.threshold and frac_coherent >= cfg.min_frac_coherent
    key = "real" if is_real else "manip"
    margin = abs(scs - cfg.threshold)
    confidence = "High" if margin >= 20 else ("Medium" if margin >= 10 else "Low")
    if key == "real":
        risk = "Medium" if confidence == "Low" else "Low"
    else:
        risk = "High" if confidence == "High" else "Medium"
    reasons = explain(key, scs, bpm, pairs, windows, max_jump, frac_coherent, cfg, confidence)
    return AnalysisResult(verdict=VERDICTS[key], verdict_key=key, risk_level=risk, confidence=confidence,
                          bpm=bpm, coherence_score=scs, snr_db=snr, reasons=reasons, **common)


def _reason(code: str, severity: str, text: str) -> dict:
    return {"code": code, "severity": severity, "text": text}


def _caveat() -> dict:
    return _reason("caveat_global_hr", "info",
                   "A visible heartbeat does not prove a video is real. Modern face-swaps can copy the pulse of the "
                   "source video (Seibold et al., 2025), which is why SatyaSpandan compares regions instead.")


def _unable(reasons, q, fps, method, cfg, overlay) -> AnalysisResult:
    return AnalysisResult(verdict=VERDICTS["unable"], verdict_key="unable", risk_level="—", confidence="—",
                          bpm=None, coherence_score=None, snr_db=None, reasons=reasons + [_caveat()],
                          quality=q, fps=fps, method=method, threshold=cfg.threshold, overlay_frame=overlay)


def explain(key, scs, bpm, pairs, windows, max_jump, frac_coherent, cfg, confidence) -> list:
    """Plain-language reasons. Each rule fires independently."""
    out = []
    lr, lm, rm = pairs["left-right"], pairs["left-forehead"], pairs["right-forehead"]
    if key == "real":
        out.append(_reason("coherent", "info",
            f"All three skin regions rise and fall together at about {bpm:.0f} bpm (spatial coherence {scs:.0f}%)."))
        if confidence == "Low":
            out.append(_reason("borderline", "warn",
                "The score is close to the decision threshold. Please treat this result with extra caution."))
    else:
        if lr["r"] < 0.3:
            out.append(_reason("cheek_desync", "warn",
                f"The left and right cheeks do not pulse together (correlation {lr['r']:.2f}). In a real face both "
                "cheeks are fed by the same heartbeat."))
        for (name, m) in (("left-forehead", lm), ("right-forehead", rm)):
            a = name.split("-")[0]
            if m["r"] < 0.3:
                out.append(_reason(f"{a}_forehead_desync", "warn",
                    f"The {ROI_LABELS[a]} and the forehead pulse out of step (correlation {m['r']:.2f})."))
        w_bad = [w for w in windows if w["scs"] < cfg.threshold]
        if w_bad:
            diffs = [(abs(w["bpm_forehead"] - w["bpm_left"]), "left", w) for w in w_bad] + \
                    [(abs(w["bpm_forehead"] - w["bpm_right"]), "right", w) for w in w_bad]
            d, side, w = max(diffs, key=lambda x: x[0])
            if d > 10:
                out.append(_reason("bpm_mismatch", "warn",
                    f"Around {w['t_start']:.0f}-{w['t_end']:.0f} s the forehead shows {w['bpm_forehead']:.0f} bpm but "
                    f"the {ROI_LABELS[side]} shows {w[f'bpm_{side}']:.0f} bpm. A single heart cannot produce two different rates."))
        worst_lag = max(((m["lag_ms"], name) for name, m in pairs.items()), key=lambda x: x[0])
        if worst_lag[0] > cfg.max_lag_ms:
            a, b = worst_lag[1].split("-")
            out.append(_reason("phase_lag", "warn",
                f"The {ROI_LABELS[a]} and the {ROI_LABELS[b]} are offset by about {worst_lag[0]:.0f} ms, far more than "
                "natural blood-flow delays across a face."))
        out.append(_reason("low_coherence", "warn",
            f"Overall spatial coherence is {scs:.0f}%, below the {cfg.threshold:.0f}% threshold; only "
            f"{frac_coherent * 100:.0f}% of time windows looked coherent."))
    if max_jump > cfg.hr_jump_bpm:
        out.append(_reason("hr_jump", "warn",
            f"The estimated heart rate jumps by {max_jump:.0f} bpm between neighbouring 2-second steps, which is physiologically unlikely."))
    out.append(_caveat())
    return out


# --------------------------------------------------------------------------
# Stages 1 + 2: video ingestion and ROI traces (OpenCV + MediaPipe)
# --------------------------------------------------------------------------

def _roi_hull(pts: np.ndarray, ids: list) -> np.ndarray:
    import cv2
    return cv2.convexHull(pts[ids].astype(np.int32))


def _skin_mean(rgb_frame: np.ndarray, ycrcb: np.ndarray, hull: np.ndarray) -> np.ndarray:
    """Mean RGB of skin pixels inside the polygon. Broad YCrCb range (all skin tones) + luminance trimming."""
    import cv2
    h, w = rgb_frame.shape[:2]
    x, y, bw, bh = cv2.boundingRect(hull)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + bw, w), min(y + bh, h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return np.full(3, np.nan)
    mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(mask, [hull - np.array([x0, y0])], 1)
    poly = mask.astype(bool)
    if poly.sum() < 50:
        return np.full(3, np.nan)
    crop = rgb_frame[y0:y1, x0:x1]
    yc = ycrcb[y0:y1, x0:x1]
    lum = yc[..., 0]
    lo, hi = np.percentile(lum[poly], [5, 95])
    skin = poly & (yc[..., 1] >= 128) & (yc[..., 1] <= 180) & (yc[..., 2] >= 70) & (yc[..., 2] <= 135) \
        & (lum >= lo) & (lum <= hi)
    use = skin if skin.sum() >= max(50, 0.5 * poly.sum()) else poly
    return crop[use].mean(axis=0)


def _background_boxes(face_box, w, h) -> list:
    """Two square background patches away from the face (Seibold et al. 2025)."""
    s = int(0.12 * w)
    m = int(0.03 * w)
    fx0, fy0, fx1, fy1 = face_box
    pad_x, pad_y = 0.15 * (fx1 - fx0), 0.15 * (fy1 - fy0)
    fx0, fy0, fx1, fy1 = fx0 - pad_x, fy0 - pad_y, fx1 + pad_x, fy1 + pad_y
    candidates = [(m, m), (w - m - s, m), (m, h - m - s), (w - m - s, h - m - s),
                  (m, (h - s) // 2), (w - m - s, (h - s) // 2)]
    boxes = []
    for x, y in candidates:
        overlaps = not (x + s < fx0 or x > fx1 or y + s < fy0 or y > fy1)
        if not overlaps:
            boxes.append((x, y, x + s, y + s))
        if len(boxes) == 2:
            break
    return boxes


def extract_traces(path: str, cfg: EngineConfig = EngineConfig(), progress: ProgressFn = None) -> dict:
    """Read a video and return per-frame mean RGB traces for each ROI plus quality data."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    def report(frac, stage):
        if progress:
            progress(float(frac), stage)

    report(0.0, "Reading video")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("We couldn't read this video file. Try an MP4 (H.264) file.")
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps_ok = bool(fps) and math.isfinite(fps) and 10 <= fps <= 120
    max_frames = int(cfg.max_duration_s * (fps if fps_ok else 30))
    n_expected = min(n_total, max_frames) if n_total > 0 else max_frames

    with open(cfg.model_path, "rb") as fh:
        model_buf = fh.read()
    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_buffer=model_buf),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    traces = {k: [] for k in (*ROI_NAMES, "background")}
    stamps, found, iod, motion = [], [], [], []
    prev_pts = None
    bg_boxes = None
    overlay_candidates = []
    scale = 1.0
    last_ts = -1
    i = 0
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        while i < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            stamps.append(cap.get(cv2.CAP_PROP_POS_MSEC))
            h0, w0 = frame.shape[:2]
            if w0 > cfg.max_width:
                scale = cfg.max_width / w0
                frame = cv2.resize(frame, (cfg.max_width, int(round(h0 * scale))), interpolation=cv2.INTER_AREA)
            h, w = frame.shape[:2]
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ts = int(round(i * 1000.0 / (fps if fps_ok else 30)))
            ts = max(ts, last_ts + 1)
            last_ts = ts
            res = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame), ts)
            if res.face_landmarks:
                lms = res.face_landmarks[0]
                pts = np.array([[p.x * w, p.y * h] for p in lms])
                d_eye = float(np.linalg.norm(pts[EYE_OUTER[0]] - pts[EYE_OUTER[1]]))
                ycrcb = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2YCrCb)
                hulls = {k: _roi_hull(pts, ROI_LANDMARKS[k]) for k in ROI_NAMES}
                for k in ROI_NAMES:
                    traces[k].append(_skin_mean(rgb_frame, ycrcb, hulls[k]))
                if bg_boxes is None:
                    x0, y0 = pts.min(axis=0)
                    x1, y1 = pts.max(axis=0)
                    bg_boxes = _background_boxes((x0, y0, x1, y1), w, h)
                found.append(True)
                iod.append(d_eye / scale)
                motion.append(np.median(np.linalg.norm(pts - prev_pts, axis=1)) / d_eye
                              if prev_pts is not None and d_eye > 0 else np.nan)
                prev_pts = pts
                if len(overlay_candidates) < 1 and i >= n_expected // 2:
                    overlay_candidates.append((frame.copy(), hulls))
            else:
                for k in ROI_NAMES:
                    traces[k].append(np.full(3, np.nan))
                found.append(False)
                prev_pts = None
            if bg_boxes:
                vals = [rgb_frame[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0) for x0, y0, x1, y1 in bg_boxes]
                traces["background"].append(np.mean(vals, axis=0))
            else:
                traces["background"].append(np.full(3, np.nan))
            i += 1
            if i % 10 == 0:
                report(0.85 * i / max(n_expected, 1), "Tracking face")
    cap.release()

    n = len(found)
    if n == 0:
        raise ValueError("The video contains no readable frames.")

    stamps = np.asarray(stamps, dtype=float)
    if not fps_ok:
        span = (stamps[-1] - stamps[0]) / 1000.0 if n > 1 else 0
        fps = (n - 1) / span if span > 0 else 0.0

    arr = {k: np.asarray(v, dtype=float) for k, v in traces.items()}
    found = np.asarray(found)

    # Variable-frame-rate clips: resample to a uniform grid
    d = np.diff(stamps)
    if n > 2 and fps > 0 and np.all(d > 0) and np.median(d) > 0 and np.std(d) / np.median(d) > 0.10:
        t_src = (stamps - stamps[0]) / 1000.0
        t_uni = np.arange(0, t_src[-1], 1.0 / fps)
        for k in arr:
            arr[k] = np.stack([np.interp(t_uni, t_src, arr[k][:, c]) for c in range(3)], axis=1)
        found = np.interp(t_uni, t_src, found.astype(float)) > 0.5

    # Fill short gaps (< 0.5 s), then keep the longest valid run
    valid = np.all(np.isfinite(np.stack([arr[k][:, 1] for k in ROI_NAMES], axis=1)), axis=1)
    max_gap = int(0.5 * fps) if fps > 0 else 0
    valid_filled = _fill_short_gaps(valid, max_gap)
    s, e = _longest_run(valid_filled)
    for k in arr:
        seg = arr[k][s:e]
        for c in range(3):
            col = seg[:, c]
            bad = ~np.isfinite(col)
            if bad.any() and (~bad).sum() >= 2:
                col[bad] = np.interp(np.flatnonzero(bad), np.flatnonzero(~bad), col[~bad])
        arr[k] = seg

    motion_arr = np.asarray(motion, dtype=float)
    motion_arr = motion_arr[np.isfinite(motion_arr)]
    quality = {
        "face_ratio": float(found.mean()),
        "face_px": float(np.median(iod)) if iod else 0.0,
        "motion": float(np.median(motion_arr)) if motion_arr.size else 0.0,
        "fast_motion_frac": float(np.mean(motion_arr > 0.10)) if motion_arr.size else 0.0,
        "frames_read": int(n),
    }
    if bg_boxes is None:
        arr["background"] = None

    overlay = None
    if overlay_candidates:
        frame, hulls = overlay_candidates[0]
        overlay = draw_overlay(frame, hulls, bg_boxes or [])
    report(0.9, "Extracting pulse")
    return {"rgb": arr, "fps": float(fps), "quality": quality, "overlay": overlay}


def _fill_short_gaps(valid: np.ndarray, max_gap: int) -> np.ndarray:
    out = valid.copy()
    n = len(valid)
    i = 0
    while i < n:
        if not valid[i]:
            j = i
            while j < n and not valid[j]:
                j += 1
            if i > 0 and j < n and (j - i) <= max_gap:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def _longest_run(mask: np.ndarray) -> tuple:
    best, cur_s, best_se = 0, None, (0, 0)
    for i, v in enumerate(np.append(mask, False)):
        if v and cur_s is None:
            cur_s = i
        elif not v and cur_s is not None:
            if i - cur_s > best:
                best, best_se = i - cur_s, (cur_s, i)
            cur_s = None
    return best_se


def draw_overlay(frame_bgr: np.ndarray, hulls: dict, bg_boxes: list) -> np.ndarray:
    import cv2
    out = frame_bgr.copy()
    tint = out.copy()
    for k, hull in hulls.items():
        cv2.fillPoly(tint, [hull], ROI_COLORS[k])
    out = cv2.addWeighted(tint, 0.30, out, 0.70, 0)
    for k, hull in hulls.items():
        cv2.polylines(out, [hull], True, ROI_COLORS[k], 2, cv2.LINE_AA)
    for x0, y0, x1, y1 in bg_boxes:
        for xa in range(x0, x1, 8):
            cv2.line(out, (xa, y0), (min(xa + 4, x1), y0), ROI_COLORS["background"], 2)
            cv2.line(out, (xa, y1), (min(xa + 4, x1), y1), ROI_COLORS["background"], 2)
        for ya in range(y0, y1, 8):
            cv2.line(out, (x0, ya), (x0, min(ya + 4, y1)), ROI_COLORS["background"], 2)
            cv2.line(out, (x1, ya), (x1, min(ya + 4, y1)), ROI_COLORS["background"], 2)
    return out


def analyze_video(path: str, cfg: EngineConfig = EngineConfig(), progress: ProgressFn = None) -> AnalysisResult:
    """Full pipeline: video file -> AnalysisResult."""
    data = extract_traces(path, cfg, progress)
    rgb = data["rgb"]
    if rgb.get("background") is None:
        rgb = {k: v for k, v in rgb.items() if k != "background"}
    if progress:
        progress(0.92, "Comparing regions")
    result = analyze_traces(rgb, data["fps"], cfg, quality=data["quality"], overlay_frame=data["overlay"])
    if progress:
        progress(1.0, "Done")
    return result


def load_calibrated_config(path: Optional[str] = None, **overrides) -> EngineConfig:
    """EngineConfig with the threshold from tools/calibrate.py (calibration.json) if present."""
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")
    cfg = EngineConfig(**overrides)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cal = json.load(fh)
        cfg.threshold = float(cal.get("threshold", cfg.threshold))
    return cfg


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Analyse one video with SatyaSpandan")
    ap.add_argument("video")
    ap.add_argument("--method", default="POS", choices=["POS", "CHROM", "GREEN"])
    args = ap.parse_args()
    res = analyze_video(args.video, load_calibrated_config(method=args.method),
                        progress=lambda f, s: print(f"\r{s:<20} {f * 100:5.1f}%", end="", flush=True))
    print()
    d = res.to_dict()
    d.pop("overlay_jpeg_b64")
    print(json.dumps({k: d[k] for k in ("verdict", "risk_level", "confidence", "bpm", "coherence_score",
                                         "snr_db", "quality", "pairs")}, indent=2))
    for r in d["reasons"]:
        print(" -", r["text"])

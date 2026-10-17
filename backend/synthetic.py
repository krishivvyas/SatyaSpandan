"""
Synthetic RGB traces for SatyaSpandan (implementation.md, section 7).

Generates per-region mean-RGB traces (not pulses), so GREEN, CHROM and POS
are all exercised exactly as on real video. Used by demo_test.py and by the
API's /api/synthetic endpoint, so the website works without any video.
"""

from __future__ import annotations

import numpy as np
from scipy import signal

SCENARIOS = {
    "real": {
        "title": "Real face (coherent)",
        "expected": "real",
        "description": "One heart drives all three regions: same rate, natural lags of 0-30 ms, mild camera noise.",
    },
    "fake_desync": {
        "title": "Face-swap: regions out of sync",
        "expected": "manip",
        "description": "Cheeks pulse at different rates or with sudden phase jumps, as left by blending seams.",
    },
    "fake_inherited": {
        "title": "Face-swap: inherited heart rate",
        "expected": "manip",
        "description": "A believable global pulse is present (copied from the driver video), but the cheeks carry "
                       "strong independent noise and a 200 ms lag. Global HR alone would look fine.",
    },
    "unable_noise": {
        "title": "Heavily compressed video",
        "expected": "unable",
        "description": "Pulse almost erased by compression noise, as in a multi-forwarded clip.",
    },
    "unable_short": {
        "title": "Clip too short",
        "expected": "unable",
        "description": "A clean real face but only 4 seconds long.",
    },
    "unable_flicker": {
        "title": "Flickering coloured light",
        "expected": "unable",
        "description": "A coloured light flickering at 60 bpm dominates both the face and the background.",
    },
}

SKIN_TONES = [
    (200, 150, 130),
    (180, 120, 100),
    (150, 100, 75),
    (110, 70, 50),
    (75, 48, 35),
]

# Relative pulsatile strength per channel: blood absorbs green most (de Haan & van Leest, PBV).
PULSE_VECTOR = np.array([0.33, 0.77, 0.53])


def _band_noise(rng, n, fs, band=(0.7, 3.0)):
    sos = signal.butter(4, band, btype="bandpass", fs=fs, output="sos")
    x = signal.sosfiltfilt(sos, rng.standard_normal(n + 200))[100:-100]
    return x / (x.std() + 1e-12)


def _pulse_wave(phase):
    return np.sin(phase) + 0.3 * np.sin(2 * phase)


def make_scenario(name: str, seed: int = 0, fps: float = 30.0, duration: float = 20.0,
                  noise_scale: float = 1.0) -> dict:
    """Return {"rgb": {forehead, left, right, background: (T,3)}, "fps", "true_bpm", "expected"}."""
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}; choose from {list(SCENARIOS)}")
    rng = np.random.default_rng(seed)
    if name == "unable_short":
        duration = 4.0
    # noise_scale multiplies the sensor noise (robustness sweeps in tools/accuracy_report.py)
    n = int(round(duration * fps))
    t = np.arange(n) / fps

    f0 = rng.uniform(1.0, 1.6)                                   # 60-96 bpm
    f_inst = f0 + 0.03 * np.sin(2 * np.pi * 0.25 * t + rng.uniform(0, 2 * np.pi))  # HRV / respiration
    phase = 2 * np.pi * np.cumsum(f_inst) / fps

    skin = np.array(SKIN_TONES[seed % len(SKIN_TONES)], dtype=float)
    amp = 0.004                                                  # ~0.4 % intensity change (typical rPPG)
    noise_sd = 0.10 * noise_scale                                # sensor noise on an ROI mean (many pixels averaged)
    illum = 1 + 0.02 * np.sin(2 * np.pi * 0.05 * t + rng.uniform(0, 6.28))  # slow light drift, shared

    pulses = {}
    if name in ("real", "unable_short", "unable_noise", "unable_flicker"):
        lags = {"forehead": 0.0, "left": rng.uniform(0, 0.03), "right": rng.uniform(0, 0.03)}
        for k, lag in lags.items():
            pulses[k] = _pulse_wave(phase - 2 * np.pi * f0 * lag)
    elif name == "fake_desync":
        pulses["forehead"] = _pulse_wave(phase)
        if seed % 2 == 0:
            # cheeks at different rates
            for k, df in (("left", rng.uniform(0.25, 0.4)), ("right", -rng.uniform(0.2, 0.3))):
                ph = 2 * np.pi * np.cumsum(f_inst + df) / fps
                pulses[k] = _pulse_wave(ph)
        else:
            # same rate, random phase jumps every 2-3 s (blending-seam behaviour)
            for k in ("left", "right"):
                jumps = np.zeros(n)
                pos = 0
                while pos < n:
                    seg = int(rng.uniform(2, 3) * fps)
                    jumps[pos:pos + seg] = rng.uniform(-np.pi, np.pi)
                    pos += seg
                pulses[k] = _pulse_wave(phase + jumps)
    elif name == "fake_inherited":
        pulses["forehead"] = _pulse_wave(phase)
        for k in ("left", "right"):
            lag = 0.2
            pulses[k] = 0.3 * _pulse_wave(phase - 2 * np.pi * f0 * lag) + 1.2 * _band_noise(rng, n, fps)

    if name == "unable_noise":
        amp *= 0.05
        noise_sd = 2.5

    flicker = np.zeros(n)
    flicker_rgb = np.zeros(3)
    if name == "unable_flicker":
        flicker = np.sin(2 * np.pi * 1.0 * t)                    # 60 bpm coloured light
        flicker_rgb = np.array([0.0, 0.02, 0.008])              # mostly green: not cancelled by POS

    rgb = {}
    for k in ("forehead", "left", "right"):
        mod = 1 + amp * PULSE_VECTOR[None, :] * pulses[k][:, None] + flicker_rgb[None, :] * flicker[:, None]
        rgb[k] = skin[None, :] * illum[:, None] * mod + rng.normal(0, noise_sd, (n, 3))
    wall = np.array([120.0, 125.0, 130.0])
    rgb["background"] = wall[None, :] * illum[:, None] * (1 + flicker_rgb[None, :] * flicker[:, None]) \
        + rng.normal(0, noise_sd, (n, 3))
    return {"rgb": rgb, "fps": fps, "true_bpm": f0 * 60, "expected": SCENARIOS[name]["expected"]}

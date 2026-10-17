"""
SatyaSpandan: synthetic verification (implementation.md, section 7).

    python demo_test.py                 # run all scenarios x 20 seeds, exit 1 on failure
    python demo_test.py --plots         # also save wave/PSD plots to demo_out/
    python demo_test.py --video PATH    # run the full video pipeline on one clip

Real data
---------
UBFC-rPPG (Bobbia et al. 2017): download DATASET_2 from the Benezeth page.
Each subject folder has vid.avi and ground_truth.txt (line 1 = PPG wave,
line 2 = HR, line 3 = timestamps). Then:

    python demo_test.py --video D:/UBFC/DATASET_2/subject1/vid.avi
    python tools/eval_ubfc_hr.py --root D:/UBFC/DATASET_2       # HR MAE vs oximeter

FaceForensics++ (Rossler et al. 2019, access form required): compare
    original_sequences/youtube/c23/videos/000.mp4
    manipulated_sequences/Deepfakes/c23/videos/000_003.mp4
and calibrate the threshold with tools/calibrate.py.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from rppg_engine import EngineConfig, analyze_traces, analyze_video, load_calibrated_config
from synthetic import SCENARIOS, make_scenario

SEEDS = range(20)
METHODS = ("POS", "CHROM", "GREEN")


def run_suite(make_plots: bool = False) -> bool:
    ok = True
    print(f"{'scenario':<16}{'method':<7}{'pass':>6}  {'mean SCS':>9}  {'mean SNR':>9}  {'BPM err':>8}  verdicts")
    scs_by = {}
    for name, meta in SCENARIOS.items():
        for method in METHODS:
            cfg = EngineConfig(method=method)
            passes, scs, snr, errs, verdicts = 0, [], [], [], {}
            for seed in SEEDS:
                sc = make_scenario(name, seed)
                res = analyze_traces(sc["rgb"], sc["fps"], cfg)
                verdicts[res.verdict_key] = verdicts.get(res.verdict_key, 0) + 1
                passes += res.verdict_key == sc["expected"]
                if res.coherence_score is not None:
                    scs.append(res.coherence_score)
                if res.snr_db is not None and np.isfinite(res.snr_db):
                    snr.append(res.snr_db)
                if name == "real" and res.bpm is not None:
                    errs.append(abs(res.bpm - sc["true_bpm"]))
                if make_plots and seed == 0 and method == "POS":
                    _plot(name, res)
            scs_by[(name, method)] = np.mean(scs) if scs else float("nan")
            err = f"{np.mean(errs):8.2f}" if errs else f"{'-':>8}"
            print(f"{name:<16}{method:<7}{passes:>3}/{len(SEEDS):<2}  {np.mean(scs) if scs else float('nan'):9.1f}  "
                  f"{np.mean(snr) if snr else float('nan'):9.2f}  {err}  {verdicts}")
            # POS is the default and must be perfect. CHROM/GREEN may miss up to 10 %:
            # their colour combinations amplify sensor noise on the darkest synthetic skin tone
            # (a real rPPG limitation, disclosed in the UI), turning a few fakes into "unable".
            need = len(SEEDS) if method == "POS" else int(0.9 * len(SEEDS))
            if passes < need:
                print(f"  FAIL: {passes}/{len(SEEDS)} < {need} for {name} / {method}")
                ok = False
            elif passes < len(SEEDS):
                print(f"  note: {len(SEEDS) - passes} seed(s) missed (allowed for {method})")
            if name == "real" and errs and max(errs) > 3.0:
                print(f"  FAIL: BPM error {max(errs):.2f} > 3 bpm for {method}")
                ok = False
    for method in METHODS:
        gap = scs_by[("real", method)] - scs_by[("fake_desync", method)]
        if not gap >= 30:
            print(f"  FAIL: SCS gap real vs fake_desync is {gap:.1f} (< 30) for {method}")
            ok = False
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return ok


def _plot(name, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs("demo_out", exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(10, 6))
    if len(res.t):
        for k, c in (("forehead", "#d48a00"), ("left", "#1f6feb"), ("right", "#c43bd6")):
            ax[0].plot(res.t, res.signals[k], color=c, lw=1, label=k)
            ax[1].plot(res.psd["bpm_axis"], res.psd[k], color=c, lw=1, label=k)
        ax[1].plot(res.psd["bpm_axis"], res.psd["background"], "k--", lw=1, label="background")
        ax[1].set_xlim(30, 200)
    ax[0].set_title(f"{name}: {res.verdict} (SCS {res.coherence_score or 0:.0f}%, BPM {res.bpm or 0:.0f})")
    ax[0].set_xlabel("time (s)")
    ax[1].set_xlabel("bpm")
    ax[0].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(f"demo_out/{name}.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video")
    ap.add_argument("--method", default="POS", choices=METHODS)
    ap.add_argument("--plots", action="store_true")
    args = ap.parse_args()
    if args.video:
        res = analyze_video(args.video, load_calibrated_config(method=args.method),
                            progress=lambda f, s: print(f"\r{s:<20} {f * 100:5.1f}%", end="", flush=True))
        print(f"\n\nVerdict: {res.verdict}  (risk {res.risk_level}, confidence {res.confidence})")
        print(f"BPM {res.bpm}, coherence {res.coherence_score}, SNR {res.snr_db} dB")
        print("Quality:", {k: round(v, 3) if isinstance(v, float) else v for k, v in res.quality.items()})
        for r in res.reasons:
            print(" -", r["text"])
        if args.plots:
            _plot(os.path.splitext(os.path.basename(args.video))[0], res)
        sys.exit(0)
    sys.exit(0 if run_suite(args.plots) else 1)

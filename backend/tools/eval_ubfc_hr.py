"""
Heart-rate accuracy on UBFC-rPPG DATASET_2 (implementation.md, section 10.1).

    python tools/eval_ubfc_hr.py --root D:/UBFC/DATASET_2 [--methods POS CHROM GREEN] [--limit 10]

Reads subject*/vid.avi and subject*/ground_truth.txt (line 1 = PPG wave,
line 2 = HR, line 3 = timestamps), estimates BPM over the first 30 s, and
prints MAE / RMSE / Pearson against the pulse oximeter. Target: POS MAE < 5 bpm.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rppg_engine import EngineConfig, analyze_traces, extract_traces  # noqa: E402


def read_gt_hr(path: str, seconds: float) -> float:
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    hr = np.asarray([float(x) for x in lines[1].split()])
    ts = np.asarray([float(x) for x in lines[2].split()]) if len(lines) > 2 and lines[2].strip() else None
    if ts is not None and len(ts) == len(hr):
        hr = hr[ts - ts[0] <= seconds]
    return float(np.mean(hr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--methods", nargs="+", default=["POS", "CHROM", "GREEN"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    subjects = sorted(glob.glob(os.path.join(args.root, "subject*")), key=lambda p: int("".join(filter(str.isdigit, os.path.basename(p))) or 0))
    if args.limit:
        subjects = subjects[: args.limit]
    preds = {m: [] for m in args.methods}
    gts = []
    for sdir in subjects:
        vid = os.path.join(sdir, "vid.avi")
        gt = os.path.join(sdir, "ground_truth.txt")
        if not (os.path.exists(vid) and os.path.exists(gt)):
            continue
        cfg = EngineConfig()
        data = extract_traces(vid, cfg)
        n = len(data["rgb"]["forehead"])
        gt_hr = read_gt_hr(gt, n / data["fps"])
        gts.append(gt_hr)
        row = [f"{os.path.basename(sdir):<10} GT {gt_hr:6.1f}"]
        rgb = {k: v for k, v in data["rgb"].items() if v is not None}
        for m in args.methods:
            res = analyze_traces(rgb, data["fps"], EngineConfig(method=m), quality=data["quality"])
            preds[m].append(res.bpm if res.bpm is not None else np.nan)
            row.append(f"{m} {preds[m][-1]:6.1f}")
        print("  ".join(row), flush=True)

    gts = np.asarray(gts)
    print(f"\n{'method':<7}{'MAE':>7}{'RMSE':>7}{'Pearson':>9}   (n={len(gts)})")
    for m in args.methods:
        p = np.asarray(preds[m])
        ok = np.isfinite(p)
        err = p[ok] - gts[ok]
        r = np.corrcoef(p[ok], gts[ok])[0, 1] if ok.sum() > 2 else float("nan")
        print(f"{m:<7}{np.mean(np.abs(err)):7.2f}{np.sqrt(np.mean(err ** 2)):7.2f}{r:9.3f}")


if __name__ == "__main__":
    main()

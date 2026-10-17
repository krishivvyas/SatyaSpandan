"""
Calibrate the coherence threshold tau from labelled clips (implementation.md, section 10.2).

    python tools/calibrate.py --csv labels.csv [--specificity 0.90] [--out calibration.json]

labels.csv columns:  path,label,group
    label = real | fake
    group = source identity (a real video and every fake made from it share one group)

Tau is chosen so that at least --specificity of real clips score >= tau (bias
against false accusations). Thresholds are picked on training folds and
evaluated on held-out folds with GroupKFold, so the reported numbers are
honest for unseen people. The final tau (fitted on all data) is written to
calibration.json, which rppg_engine.load_calibrated_config() picks up.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rppg_engine import EngineConfig, analyze_video  # noqa: E402


def pick_tau(real_scores: np.ndarray, specificity: float) -> float:
    return float(np.quantile(real_scores, 1 - specificity)) if len(real_scores) else 55.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--specificity", type=float, default=0.90)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--method", default="POS")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calibration.json"))
    args = ap.parse_args()

    from sklearn.model_selection import GroupKFold

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    scores, labels, groups, unable = [], [], [], 0
    for row in rows:
        res = analyze_video(row["path"], EngineConfig(method=args.method))
        if res.verdict_key == "unable" or res.coherence_score is None:
            unable += 1
            print(f"unable  {row['label']:<5} {row['path']}  ({res.reasons[0]['code']})")
            continue
        scores.append(res.coherence_score)
        labels.append(1 if row["label"].lower() == "fake" else 0)
        groups.append(row["group"])
        print(f"{res.coherence_score:6.1f} {row['label']:<5} {row['path']}")

    scores, labels, groups = np.asarray(scores), np.asarray(labels), np.asarray(groups)
    print(f"\n{len(scores)} usable clips, {unable} returned 'Unable to assess'")
    n_groups = len(set(groups))
    folds = min(args.folds, n_groups)
    if folds >= 2:
        accs, sens, spec = [], [], []
        for tr, te in GroupKFold(n_splits=folds).split(scores, labels, groups):
            tau = pick_tau(scores[tr][labels[tr] == 0], args.specificity)
            pred_fake = scores[te] < tau
            y = labels[te]
            accs.append(np.mean(pred_fake == y))
            if (y == 1).any():
                sens.append(np.mean(pred_fake[y == 1]))
            if (y == 0).any():
                spec.append(np.mean(~pred_fake[y == 0]))
        print(f"GroupKFold ({folds} folds) accuracy {np.mean(accs):.3f}  "
              f"sensitivity {np.mean(sens) if sens else float('nan'):.3f}  "
              f"specificity {np.mean(spec) if spec else float('nan'):.3f}")
    tau = pick_tau(scores[labels == 0], args.specificity)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"threshold": round(tau, 2), "specificity_target": args.specificity,
                   "n_clips": int(len(scores)), "method": args.method}, fh, indent=2)
    print(f"tau = {tau:.2f}  ->  {args.out}")


if __name__ == "__main__":
    main()

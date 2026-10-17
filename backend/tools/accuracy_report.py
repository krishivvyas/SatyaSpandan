"""
Generate a standalone HTML accuracy report for SatyaSpandan.

    python tools/accuracy_report.py                          # synthetic tests only
    python tools/accuracy_report.py --videos D:/my_clips     # + real clips in D:/my_clips/real and D:/my_clips/fake
    python tools/accuracy_report.py --quick                  # fewer seeds (about 30 s)

Writes ../accuracy_report.html (open it in any browser; no server needed).

Sections
    1. Synthetic suite     every scenario x POS/CHROM/GREEN x N seeds, confusion matrices, BPM error
    2. Robustness          accuracy vs sensor noise and vs clip length
    3. Fairness            real-face pass rate by synthetic skin tone
    4. Real videos         accuracy, false accusations, coverage, blocking reasons (if --videos is given)

Synthetic accuracy shows that the maths behaves as designed. It is NOT real-world accuracy.
Only section 4, on consented labelled clips, says anything about real performance.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import html
import math
import os
import platform
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from rppg_engine import EngineConfig, analyze_traces, extract_traces, load_calibrated_config, load_calibration  # noqa: E402
from synthetic import SCENARIOS, SKIN_TONES, make_scenario  # noqa: E402

METHODS = ("POS", "GREEN", "CHROM")
DEFAULT = EngineConfig().method
VKEYS = ("real", "manip", "unable")
VLABEL = {"real": "No strong signs", "manip": "Possible manipulation", "unable": "Unable to assess"}
TONE_NAMES = ["Very light", "Light", "Medium", "Brown", "Dark"]
VIDEO_EXT = (".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v")
GATE_LABELS = {
    "too_short": "Clip too short", "face_missing": "Face not found often enough", "face_small": "Face too small",
    "motion": "Too much movement", "low_snr": "Pulse signal too weak", "ambient": "Background flicker / compression",
    "bad_fps": "Frame rate unreadable", "weak_for_flag": "Pulse too weak to compare regions",
}


# --------------------------------------------------------------------------
# Experiments
# --------------------------------------------------------------------------

def cfgs():
    return {m: load_calibrated_config(method=m) for m in METHODS}


def run_synthetic(seeds: int, progress) -> list[dict]:
    rows = []
    c = cfgs()
    total = len(SCENARIOS) * len(METHODS) * seeds
    for name, meta in SCENARIOS.items():
        for seed in range(seeds):
            sc = make_scenario(name, seed)
            for m in METHODS:
                r = analyze_traces(sc["rgb"], sc["fps"], c[m])
                rows.append({
                    "scenario": name, "method": m, "seed": seed, "expected": meta["expected"],
                    "verdict": r.verdict_key, "scs": r.coherence_score, "snr": r.snr_db, "bpm": r.bpm,
                    "true_bpm": sc["true_bpm"], "tone": seed % len(SKIN_TONES),
                })
                progress(len(rows) / total, "synthetic suite")
    return rows


def run_sweep(param: str, values: list, scenarios: tuple, seeds: int, progress) -> list[dict]:
    rows = []
    c = cfgs()
    total = len(values) * len(scenarios) * seeds * len(METHODS)
    done = 0
    for v in values:
        for name in scenarios:
            for seed in range(seeds):
                kw = {"noise_scale": v} if param == "noise" else {"duration": v}
                sc = make_scenario(name, 1000 + seed, **kw)
                for m in METHODS:
                    r = analyze_traces(sc["rgb"], sc["fps"], c[m])
                    rows.append({"value": v, "scenario": name, "method": m, "expected": sc["expected"], "verdict": r.verdict_key})
                    done += 1
                    progress(done / total, f"{param} sweep")
    return rows


def video_duration(path: str) -> float:
    import cv2
    cap = cv2.VideoCapture(path)
    fps, n = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return n / fps if fps and n and fps > 0 else 0.0


def collect_files(folders: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """(label, folder) pairs -> (label, file). A folder with real/ and fake/ subfolders is split by them."""
    files = []
    for label, folder in folders:
        if label == "auto":
            for sub in ("real", "fake"):
                files += [(sub, f) for f in sorted(glob.glob(os.path.join(folder, sub, "*"))) if f.lower().endswith(VIDEO_EXT)]
        else:
            files += [(label, f) for f in sorted(glob.glob(os.path.join(folder, "*"))) if f.lower().endswith(VIDEO_EXT)]
    return files


def run_videos(folders: list[tuple[str, str]], progress, segment: float = 0.0, max_segments: int = 6) -> list[dict]:
    """Score every clip; with segment > 0, long videos are cut into back-to-back segments of that length."""
    jobs = []
    for label, path in collect_files(folders):
        dur = video_duration(path)
        if segment > 0 and dur >= 2 * segment:
            for k in range(min(max_segments, int(dur // segment))):
                jobs.append((label, path, k * segment, segment))
        else:
            jobs.append((label, path, 0.0, 30.0))
    clips = []
    c = cfgs()
    for i, (label, path, start, length) in enumerate(jobs):
        name = os.path.basename(path) + (f"  @ {start:.0f}–{start + length:.0f} s" if start > 0 or length < 30 else "")
        progress(i / max(1, len(jobs)), f"clip {i + 1}/{len(jobs)}: {os.path.basename(path)[:40]}")
        clip = {"name": name, "label": label, "folder": os.path.basename(os.path.dirname(path)), "methods": {}, "error": None}
        try:
            data = extract_traces(path, EngineConfig(start_s=start, max_duration_s=length))
            rgb = {k: v for k, v in data["rgb"].items() if v is not None}
            for m in METHODS:
                r = analyze_traces(rgb, data["fps"], c[m], quality=data["quality"])
                gates = [x["code"] for x in r.reasons if x["severity"] == "block"]
                clip["methods"][m] = {"verdict": r.verdict_key, "scs": r.coherence_score, "snr": r.snr_db,
                                      "bpm": r.bpm, "gates": gates, "quality": dict(r.quality)}
        except Exception as e:  # report and keep going
            clip["error"] = str(e)
        clips.append(clip)
    progress(1.0, "videos")
    return clips


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def ratio(a, b):
    return a / b if b else None


def video_metrics(clips: list[dict], m: str) -> dict:
    mat = {"real": dict.fromkeys(VKEYS, 0), "fake": dict.fromkeys(VKEYS, 0)}
    gates: dict[str, int] = {}
    for c in clips:
        r = c["methods"].get(m)
        v = r["verdict"] if r else "unable"
        mat[c["label"]][v] += 1
        for g in (r["gates"] if r else ["error"]):
            gates[g] = gates.get(g, 0) + 1
    R, F = mat["real"], mat["fake"]
    n_real, n_fake = sum(R.values()), sum(F.values())
    assessed = R["real"] + R["manip"] + F["real"] + F["manip"]
    correct = R["real"] + F["manip"]
    return {
        "matrix": mat, "n_real": n_real, "n_fake": n_fake,
        "coverage": ratio(assessed, n_real + n_fake),
        "acc_assessed": ratio(correct, assessed),
        "acc_all": ratio(correct, n_real + n_fake),
        "specificity": ratio(R["real"], R["real"] + R["manip"]),
        "false_acc": ratio(R["manip"], n_real),
        "sensitivity": ratio(F["manip"], F["real"] + F["manip"]),
        "gates": gates,
    }


def pct(x, d=0):
    return "—" if x is None else f"{x * 100:.{d}f}%"


def num(x, d=1, unit=""):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{d}f}{unit}"


# --------------------------------------------------------------------------
# Inline SVG charts (no external libraries, works offline)
# --------------------------------------------------------------------------

SERIES_COLORS = {"POS": "var(--c1)", "CHROM": "var(--c2)", "GREEN": "var(--c3)"}


def svg_grouped_bars(cats: list[str], series: dict[str, list], height=240, ymax=100.0, unit="%") -> str:
    w, pad_l, pad_b, pad_t = 760, 44, 58, 14
    plot_w, plot_h = w - pad_l - 10, height - pad_b - pad_t
    n_s = len(series)
    gw = plot_w / max(1, len(cats))
    bw = min(26, (gw - 14) / max(1, n_s))
    out = [f'<svg viewBox="0 0 {w} {height}" class="chart" role="img">']
    for t in range(0, 101, 25):
        y = pad_t + plot_h * (1 - t / 100)
        out.append(f'<line x1="{pad_l}" x2="{w - 10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{pad_l - 6}" y="{y + 4:.1f}" class="ax" text-anchor="end">{t * ymax / 100:.0f}{unit}</text>')
    for i, cat in enumerate(cats):
        x0 = pad_l + i * gw + (gw - bw * n_s) / 2
        for j, (name, vals) in enumerate(series.items()):
            v = vals[i]
            if v is None:
                continue
            h = plot_h * min(v, ymax) / ymax
            x = x0 + j * bw
            out.append(f'<rect x="{x:.1f}" y="{pad_t + plot_h - h:.1f}" width="{bw - 3:.1f}" height="{h:.1f}" rx="3" '
                       f'fill="{SERIES_COLORS.get(name, "var(--c1)")}"><title>{html.escape(name)} · {html.escape(cat)}: {v:.1f}{unit}</title></rect>')
        lines = cat.split("\n")
        for k, ln in enumerate(lines):
            out.append(f'<text x="{pad_l + i * gw + gw / 2:.1f}" y="{pad_t + plot_h + 16 + 13 * k}" class="ax" text-anchor="middle">{html.escape(ln)}</text>')
    out.append("</svg>")
    return "".join(out) + legend(series.keys())


def svg_lines(xs: list, series: dict[str, list], xlabel: str, height=240, log_x=False) -> str:
    w, pad_l, pad_b, pad_t = 760, 44, 44, 14
    plot_w, plot_h = w - pad_l - 16, height - pad_b - pad_t
    fx = (lambda v: math.log(v)) if log_x else (lambda v: v)
    lo, hi = fx(min(xs)), fx(max(xs))
    X = lambda v: pad_l + plot_w * ((fx(v) - lo) / (hi - lo) if hi > lo else 0.5)  # noqa: E731
    Y = lambda v: pad_t + plot_h * (1 - v / 100)  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {height}" class="chart" role="img">']
    for t in range(0, 101, 25):
        out.append(f'<line x1="{pad_l}" x2="{w - 16}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/>'
                   f'<text x="{pad_l - 6}" y="{Y(t) + 4:.1f}" class="ax" text-anchor="end">{t}%</text>')
    for v in xs:
        out.append(f'<text x="{X(v):.1f}" y="{pad_t + plot_h + 16}" class="ax" text-anchor="middle">{v:g}</text>')
    out.append(f'<text x="{pad_l + plot_w / 2:.1f}" y="{height - 6}" class="ax" text-anchor="middle">{html.escape(xlabel)}</text>')
    for name, vals in series.items():
        color = SERIES_COLORS.get(name.split(" ")[0], "var(--c1)")
        dash = ' stroke-dasharray="6 4"' if "fake" in name.lower() or "unable" in name.lower() else ""
        pts = " ".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(xs, vals) if v is not None)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2"{dash}/>')
        for x, v in zip(xs, vals):
            if v is not None:
                out.append(f'<circle cx="{X(x):.1f}" cy="{Y(v):.1f}" r="3.2" fill="{color}"><title>{html.escape(name)} @ {x:g}: {v:.0f}%</title></circle>')
    out.append("</svg>")
    return "".join(out) + legend(series.keys(), dashed=True)


def svg_strip(groups: dict[str, list], threshold: float, height_per=34) -> str:
    """Dot strip of coherence scores per group, with the decision threshold."""
    w, pad_l, pad_t = 760, 200, 10
    plot_w = w - pad_l - 16
    height = pad_t + height_per * len(groups) + 30
    X = lambda v: pad_l + plot_w * v / 100  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {height}" class="chart" role="img">']
    for t in range(0, 101, 25):
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{pad_t}" y2="{height - 26}" class="grid"/>'
                   f'<text x="{X(t):.1f}" y="{height - 10}" class="ax" text-anchor="middle">{t}%</text>')
    out.append(f'<line x1="{X(threshold):.1f}" x2="{X(threshold):.1f}" y1="{pad_t}" y2="{height - 26}" class="tau"/>'
               f'<text x="{X(threshold) + 4:.1f}" y="{pad_t + 10}" class="ax">τ {threshold:g}</text>')
    for i, (name, vals) in enumerate(groups.items()):
        y = pad_t + height_per * i + height_per / 2
        exp = SCENARIOS.get(name, {}).get("expected", "")
        color = {"real": "var(--real)", "manip": "var(--manip)", "unable": "var(--unable)"}.get(exp, "var(--c1)")
        out.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" class="ax" text-anchor="end">{html.escape(SCENARIOS.get(name, {}).get("title", name))}</text>')
        for k, v in enumerate(vals):
            if v is None:
                continue
            jitter = ((k * 37) % 13 - 6) * 1.1
            out.append(f'<circle cx="{X(v):.1f}" cy="{y + jitter:.1f}" r="3" fill="{color}" fill-opacity="0.75"/>')
    out.append("</svg>")
    return "".join(out)


def legend(names, dashed=False) -> str:
    items = []
    for n in names:
        color = SERIES_COLORS.get(n.split(" ")[0], "var(--c1)")
        style = "border-top:2px dashed" if dashed and ("fake" in n.lower() or "unable" in n.lower()) else "border-top:3px solid"
        items.append(f'<span class="lg"><i style="{style} {color}"></i>{html.escape(n)}</span>')
    return f'<div class="legend">{"".join(items)}</div>'


def confusion_html(mat: dict, rows: list[str], row_label) -> str:
    head = "".join(f'<th class="v-{k}">{VLABEL[k]}</th>' for k in VKEYS)
    body = []
    for r in rows:
        cells = []
        for k in VKEYS:
            n = mat[r][k]
            good = (r in ("real",) and k == "real") or (r in ("manip", "fake") and k == "manip") or (r == "unable" and k == "unable")
            bad = n > 0 and not good and k != "unable" and r != "unable"
            cls = "good" if good and n else ("bad" if bad else "")
            cells.append(f'<td class="{cls}">{n}</td>')
        body.append(f"<tr><th>{html.escape(row_label(r))}</th>{''.join(cells)}</tr>")
    return f'<table class="cm"><thead><tr><th>Truth ↓ / Verdict →</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#fbfaf7;--fg:#1b1d21;--muted:#5d6470;--card:#fff;--border:#e5e2db;--accent:#b4232c;
--real:#1a7f37;--manip:#9a6700;--unable:#57606a;--c1:#b4232c;--c2:#1f6feb;--c3:#1a7f37;--grid:#ece9e2}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#111316;--fg:#e8eaed;--muted:#9aa3ad;--card:#181b1f;
--border:#2a2f36;--accent:#ff6b6b;--real:#3fb950;--manip:#d29922;--unable:#9ba3ad;--c1:#ff6b6b;--c2:#58a6ff;--c3:#3fb950;--grid:#23272d}}
:root[data-theme=dark]{--bg:#111316;--fg:#e8eaed;--muted:#9aa3ad;--card:#181b1f;--border:#2a2f36;--accent:#ff6b6b;
--real:#3fb950;--manip:#d29922;--unable:#9ba3ad;--c1:#ff6b6b;--c2:#58a6ff;--c3:#3fb950;--grid:#23272d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1060px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:30px;margin:0 0 4px}h2{font-size:21px;margin:40px 0 10px;padding-top:10px;border-top:1px solid var(--border)}
h3{font-size:16px;margin:22px 0 8px}.muted{color:var(--muted)}.small{font-size:13px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;margin:12px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px}
.kpi b{display:block;font-size:28px;line-height:1.2}.kpi span{color:var(--muted);font-size:13px}
.note{border-left:4px solid var(--manip);background:color-mix(in oklab,var(--manip) 10%,var(--card));padding:12px 14px;border-radius:8px}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:7px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
thead th{color:var(--muted);font-weight:600}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.cm td{text-align:center;font-size:18px;font-weight:600}.cm td.good{color:var(--real)}.cm td.bad{color:var(--manip)}
.v-real{color:var(--real)}.v-manip{color:var(--manip)}.v-unable{color:var(--unable)}
.chip{display:inline-block;border-radius:99px;padding:1px 8px;font-size:12px;font-weight:600}
.chip.real{background:color-mix(in oklab,var(--real) 16%,transparent);color:var(--real)}
.chip.manip{background:color-mix(in oklab,var(--manip) 16%,transparent);color:var(--manip)}
.chip.unable{background:color-mix(in oklab,var(--unable) 16%,transparent);color:var(--unable)}
.chart{width:100%;height:auto;display:block}.chart .grid{stroke:var(--grid);stroke-width:1}
.chart .ax{fill:var(--muted);font-size:11px}.chart .tau{stroke:var(--fg);stroke-dasharray:4 4}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--muted);margin-top:4px}
.lg i{display:inline-block;width:18px;margin-right:6px;vertical-align:middle}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:760px){.grid2{grid-template-columns:1fr}h1{font-size:25px}}
code{background:var(--grid);padding:1px 5px;border-radius:4px;font-size:13px}
button.tt{float:right;font:inherit;font-size:13px;background:var(--card);color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:4px 10px;cursor:pointer}
"""


def build_html(syn, noise, dur, videos, args, elapsed) -> str:
    c = cfgs()
    tau = c[DEFAULT].threshold
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    parts = []
    P = parts.append

    # ---- headline numbers
    def syn_acc(m):
        r = [x for x in syn if x["method"] == m]
        return sum(x["verdict"] == x["expected"] for x in r) / len(r)

    P(f"""<button class="tt" onclick="var r=document.documentElement;var d=r.getAttribute('data-theme')==='dark'||(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);r.setAttribute('data-theme',d?'light':'dark')">Theme</button>
<h1>SatyaSpandan accuracy report</h1>
<p class="muted">Generated {now} · {args.seeds} seeds per scenario · threshold τ = {tau:g}% · run time {elapsed:.0f} s</p>
<div class="note"><b>How to read this.</b> Sections 1–3 use <b>synthetic</b> skin-colour signals with a known answer.
They show that the signal processing behaves as designed. They do <b>not</b> measure real-world accuracy.
Real-world accuracy only comes from section 4: consented, labelled real and fake videos.</div>""")

    kp = [f'<div class="kpi"><span>Synthetic accuracy · {m}</span><b>{pct(syn_acc(m), 1)}</b></div>' for m in METHODS]
    if videos:
        vm = video_metrics(videos, DEFAULT)
        kp.append(f'<div class="kpi"><span>Real videos · {DEFAULT} accuracy (assessed)</span><b>{pct(vm["acc_assessed"])}</b></div>')
        kp.append(f'<div class="kpi"><span>Real videos · false accusations</span><b>{pct(vm["false_acc"])}</b></div>')
    else:
        kp.append('<div class="kpi"><span>Real-video accuracy</span><b>not measured</b><span>add <code>--videos</code></span></div>')
    P(f'<div class="kpis">{"".join(kp)}</div>')

    # ---- 1. synthetic
    P("<h2>1 · Synthetic test suite</h2>")
    P('<p class="muted">Six scenarios: a coherent real face; two face-swap patterns (regions out of sync, and an inherited heart rate with noisy, lagging cheeks); and three cases that should be refused (heavy compression noise, a 4-second clip, a flickering coloured light).</p>')
    rows = []
    for m in METHODS:
        r = [x for x in syn if x["method"] == m]
        real = [x for x in r if x["expected"] == "real"]
        fake = [x for x in r if x["expected"] == "manip"]
        unab = [x for x in r if x["expected"] == "unable"]
        err = [abs(x["bpm"] - x["true_bpm"]) for x in real if x["bpm"] is not None]
        rows.append(f'<tr><th>{m}</th><td class="num">{pct(sum(x["verdict"] == x["expected"] for x in r) / len(r), 1)}</td>'
                    f'<td class="num">{pct(sum(x["verdict"] == "real" for x in real) / len(real))}</td>'
                    f'<td class="num">{pct(sum(x["verdict"] == "manip" for x in real) / len(real))}</td>'
                    f'<td class="num">{pct(sum(x["verdict"] == "manip" for x in fake) / len(fake))}</td>'
                    f'<td class="num">{pct(sum(x["verdict"] == "unable" for x in unab) / len(unab))}</td>'
                    f'<td class="num">{num(np.mean(err) if err else None, 2, " bpm")}</td></tr>')
    P('<div class="card tw"><table><thead><tr><th>Method</th><th class="num">Overall accuracy</th><th class="num">Real passed</th>'
      '<th class="num">Real wrongly flagged</th><th class="num">Fakes flagged</th><th class="num">Correctly refused</th>'
      f'<th class="num">Heart-rate error (MAE)</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

    cats = [SCENARIOS[s]["title"].replace(": ", ":\n").replace(" (", "\n(") for s in SCENARIOS]
    series = {m: [100 * np.mean([x["verdict"] == x["expected"] for x in syn if x["method"] == m and x["scenario"] == s]) for s in SCENARIOS] for m in METHODS}
    P('<h3>Correct verdict per scenario</h3><div class="card">' + svg_grouped_bars(cats, series, height=270) + "</div>")

    P('<h3>Confusion matrices</h3><div class="grid2">')
    for m in METHODS:
        mat = {k: dict.fromkeys(VKEYS, 0) for k in VKEYS}
        for x in syn:
            if x["method"] == m:
                mat[x["expected"]][x["verdict"]] += 1
        P(f'<div class="card"><b>{m}</b>' + confusion_html(mat, list(VKEYS), lambda k: "Expected: " + VLABEL[k]) + "</div>")
    P("</div>")

    groups = {s: [x["scs"] for x in syn if x["method"] == DEFAULT and x["scenario"] == s] for s in SCENARIOS}
    P(f'<h3>Spatial coherence scores ({DEFAULT}, the default method)</h3><p class="muted small">Each dot is one run. Green = should pass, amber = should be flagged, grey = should be refused by the quality gate (their score is not used).</p>'
      f'<div class="card">{svg_strip(groups, tau)}</div>')

    # ---- 2. robustness
    P("<h2>2 · Robustness</h2>")
    P('<p class="muted">How verdicts hold up as the signal gets worse. In the noise chart, ×1 is the default synthetic sensor noise; larger values imitate heavier compression or darker scenes. The good failure mode is more “Unable to assess”, not more wrong verdicts.</p>')
    scales = sorted({x["value"] for x in noise})
    s_noise = {}
    for m in METHODS:
        s_noise[f"{m} real passed"] = [100 * np.mean([x["verdict"] == "real" for x in noise if x["method"] == m and x["value"] == v and x["scenario"] == "real"]) for v in scales]
        s_noise[f"{m} fake flagged"] = [100 * np.mean([x["verdict"] == "manip" for x in noise if x["method"] == m and x["value"] == v and x["scenario"] != "real"]) for v in scales]
    P('<h3>Accuracy vs noise level</h3><div class="card">' + svg_lines(scales, s_noise, "sensor noise (× default)", log_x=True) + "</div>")
    s_wrong = {}
    for m in METHODS:
        s_wrong[f"{m} wrong verdict"] = [100 * np.mean([(x["verdict"] != "unable" and x["verdict"] != x["expected"]) for x in noise if x["method"] == m and x["value"] == v]) for v in scales]
        s_wrong[f"{m} unable"] = [100 * np.mean([x["verdict"] == "unable" for x in noise if x["method"] == m and x["value"] == v]) for v in scales]
    P('<h3>Wrong verdicts vs refusals as noise rises</h3><div class="card">' + svg_lines(scales, s_wrong, "sensor noise (× default)", log_x=True) + "</div>")

    durs = sorted({x["value"] for x in dur})
    s_dur = {}
    for m in METHODS:
        s_dur[f"{m} real passed"] = [100 * np.mean([x["verdict"] == "real" for x in dur if x["method"] == m and x["value"] == v and x["scenario"] == "real"]) for v in durs]
        s_dur[f"{m} fake flagged"] = [100 * np.mean([x["verdict"] == "manip" for x in dur if x["method"] == m and x["value"] == v and x["scenario"] != "real"]) for v in durs]
    P('<h3>Accuracy vs clip length</h3><p class="muted small">Clips under the minimum duration are refused by design, so they show 0 %.</p><div class="card">' + svg_lines(durs, s_dur, "clip length (seconds)") + "</div>")

    # ---- 3. fairness
    P("<h2>3 · Fairness across skin tones (synthetic)</h2>")
    P('<p class="muted">Real-face scenario only: the share of runs that correctly pass, split by synthetic skin tone. With fixed sensor noise, darker skin gives a weaker pulse, as with real cameras. Real-world fairness must be checked on real clips.</p>')
    tone_series = {}
    for m in METHODS:
        tone_series[m] = []
        for t in range(len(SKIN_TONES)):
            sel = [x for x in syn if x["method"] == m and x["scenario"] == "real" and x["tone"] == t]
            tone_series[m].append(100 * np.mean([x["verdict"] == "real" for x in sel]) if sel else None)
    P('<h3>Real faces passed at default noise</h3><div class="card">' + svg_grouped_bars(TONE_NAMES, tone_series, height=230) + "</div>")
    # harder condition, where tone effects become visible
    P('<h3>Real faces passed at 4× noise, by tone</h3>')
    tone_hard = {}
    for m in METHODS:
        vals = []
        for t in range(len(SKIN_TONES)):
            sel = [x for x in noise_by_tone if x["method"] == m and x["tone"] == t]
            vals.append(100 * np.mean([x["verdict"] == "real" for x in sel]) if sel else None)
        tone_hard[m] = vals
    P('<div class="card">' + svg_grouped_bars(TONE_NAMES, tone_hard, height=230) + "</div>")

    # ---- 4. real videos
    P("<h2>4 · Real videos</h2>")
    if not videos:
        P('<div class="card"><b>Not measured yet.</b> Put consented clips in two folders and re-run:'
          '<pre><code>my_clips\\real\\*.mp4\nmy_clips\\fake\\*.mp4\n\npython tools/accuracy_report.py --videos my_clips</code></pre>'
          '<p class="muted small">Aim for at least 10 real and 10 fake clips, 15–20 s each, from several different people. '
          'The interactive Accuracy page (<code>/evaluate</code> in the app) gives the same numbers, plus threshold tuning.</p></div>')
    else:
        rows = []
        for m in METHODS:
            vm = video_metrics(videos, m)
            rows.append(f'<tr><th>{m}</th><td class="num">{pct(vm["coverage"])}</td><td class="num">{pct(vm["acc_assessed"])}</td>'
                        f'<td class="num">{pct(vm["acc_all"])}</td><td class="num">{pct(vm["specificity"])}</td>'
                        f'<td class="num">{pct(vm["false_acc"])}</td><td class="num">{pct(vm["sensitivity"])}</td></tr>')
        nr, nf = sum(c["label"] == "real" for c in videos), sum(c["label"] == "fake" for c in videos)
        P(f'<p class="muted">{len(videos)} clips: {nr} real, {nf} fake, from <code>{html.escape(args.videos)}</code>. With this few clips every percentage is very uncertain.</p>')
        P('<div class="card tw"><table><thead><tr><th>Method</th><th class="num">Assessed</th><th class="num">Accuracy (assessed)</th>'
          '<th class="num">Accuracy (all)</th><th class="num">Specificity</th><th class="num">False accusations</th><th class="num">Sensitivity</th>'
          f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
          '<p class="muted small">Assessed = clips that passed the quality gate. Accuracy (all) counts “Unable” as not correct. Specificity = assessed real clips that passed. False accusations = real clips flagged as manipulated. Sensitivity = assessed fakes flagged.</p></div>')
        # per source folder, every method
        srcs = sorted({(c.get("folder", ""), c["label"]) for c in videos})
        srows = []
        for folder, label in srcs:
            sel = [c for c in videos if c.get("folder", "") == folder and c["label"] == label]
            cells = []
            for m in METHODS:
                cnt = {k: sum(1 for c in sel if (c["methods"].get(m) or {}).get("verdict", "unable") == k) for k in VKEYS}
                cells.append("<td>" + " ".join(f'<span class="chip {k}">{cnt[k]} {VLABEL[k].split()[0]}</span>' for k in VKEYS if cnt[k]) + "</td>")
            srows.append(f'<tr><th>{html.escape(folder)}<div class="small muted">{label} · {len(sel)} clip(s)</div></th>{"".join(cells)}</tr>')
        P('<h3>By source folder</h3><div class="card tw"><table><thead><tr><th>Folder</th>' + "".join(f"<th>{m}</th>" for m in METHODS)
          + f'</tr></thead><tbody>{"".join(srows)}</tbody></table></div>')
        P('<div class="grid2">')
        for m in METHODS:
            vm = video_metrics(videos, m)
            gates = "".join(f"<li>{html.escape(GATE_LABELS.get(g, g))}: {n}</li>" for g, n in sorted(vm["gates"].items(), key=lambda kv: -kv[1]))
            P(f'<div class="card"><b>{m}</b>' + confusion_html(vm["matrix"], ["real", "fake"], lambda k: k.capitalize())
              + (f'<p class="small muted" style="margin-top:8px">Blocked by: </p><ul class="small">{gates}</ul>' if gates else "") + "</div>")
        P("</div>")
        trs = []
        for cl in videos:
            cells = []
            for m in METHODS:
                r = cl["methods"].get(m)
                if not r:
                    cells.append(f'<td><span class="chip unable">error</span><div class="small muted">{html.escape(cl["error"] or "")}</div></td>')
                    continue
                q = r["quality"]
                why = ", ".join(GATE_LABELS.get(g, g) for g in r["gates"])
                cells.append(f'<td><span class="chip {r["verdict"]}">{VLABEL[r["verdict"]]}</span>'
                             f'<div class="small muted">coh {num(r["scs"], 0, "%")} · SNR {num(r["snr"], 1, " dB")} · {num(r["bpm"], 0, " bpm")}</div>'
                             f'<div class="small muted">SNR F/L/R {num(q.get("snr_forehead"), 1)}/{num(q.get("snr_left"), 1)}/{num(q.get("snr_right"), 1)} · '
                             f'bg {num(q.get("bg_ratio"), 2)}/{num(q.get("bg_corr"), 2)}/{num(q.get("bg_amp_ratio"), 2)} · {num(q.get("duration_s"), 1, " s")}</div>'
                             + (f'<div class="small v-unable">{html.escape(why)}</div>' if why else "") + "</td>")
            trs.append(f'<tr><th>{html.escape(cl["name"])}<div class="small muted">{cl["label"]}</div></th>{"".join(cells)}</tr>')
        P('<h3>Every clip</h3><div class="card tw"><table><thead><tr><th>Clip</th>' + "".join(f"<th>{m}</th>" for m in METHODS)
          + f'</tr></thead><tbody>{"".join(trs)}</tbody></table><p class="muted small">bg = background peak ratio / correlation / strength vs face.</p></div>')

    # ---- settings
    cal = load_calibration()
    c0 = c[DEFAULT]
    P("<h2>Settings used</h2>")
    P(f'<div class="card small"><p>Thresholds: τ {c0.threshold:g}% · coherent windows ≥ {c0.min_frac_coherent:g} · signal quality ≥ {c0.min_snr_db:g} dB (≥ {c0.min_snr_flag_db:g} dB to flag) · '
      f'duration ≥ {c0.min_duration_s:g} s · background ratio ≤ {c0.max_bg_ratio:g}, correlation ≤ {c0.max_bg_corr:g} (only if background strength ≥ {c0.min_bg_amp_ratio:g}) · '
      f'motion ≤ {c0.max_median_motion:g} · face found ≥ {c0.min_face_ratio:g} · face ≥ {c0.min_face_px:g} px.</p>'
      f'<p>Calibration file: {"<code>backend/calibration.json</code> (" + ", ".join(f"{k}={v:g}" for k, v in cal.items()) + ")" if cal else "none, built-in defaults"}.</p>'
      f'<p>Filter 0.7–3.0 Hz, 5th-order Butterworth; 10 s windows, 2 s step. Python {platform.python_version()}, numpy {np.__version__}.</p></div>')
    P('<p class="muted small">SatyaSpandan results are probabilistic warning signs and can be wrong. They must never be used to definitively label a real person as a liar.</p>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SatyaSpandan Accuracy Report</title><style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>"""


noise_by_tone: list[dict] = []


def main():
    global noise_by_tone
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", action="append", default=[], help="folder with real/ and fake/ subfolders (repeatable)")
    ap.add_argument("--real", action="append", default=[], help="folder whose clips are all real (repeatable)")
    ap.add_argument("--fake", action="append", default=[], help="folder whose clips are all fake (repeatable)")
    ap.add_argument("--segment", type=float, default=0.0, help="cut videos at least twice this long into segments of this many seconds")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--quick", action="store_true", help="fewer seeds for a fast run")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "accuracy_report.html"))
    args = ap.parse_args()
    if args.quick:
        args.seeds = 6
    sweep_seeds = max(4, args.seeds // 2)

    t0 = time.time()

    def progress(frac, stage):
        print(f"\r{stage:<40} {frac * 100:5.1f}%", end="", flush=True)

    syn = run_synthetic(args.seeds, progress)
    print()
    noise = run_sweep("noise", [0.5, 1, 2, 4, 8, 16], ("real", "fake_desync", "fake_inherited"), sweep_seeds, progress)
    print()
    dur = run_sweep("duration", [4, 6, 8, 10, 15, 20, 30], ("real", "fake_desync"), sweep_seeds, progress)
    print()
    # tone breakdown at 4x noise: seeds 0..(5k-1) cycle through all tones
    c = cfgs()
    for seed in range(max(10, args.seeds)):
        sc = make_scenario("real", seed, noise_scale=4)
        for m in METHODS:
            r = analyze_traces(sc["rgb"], sc["fps"], c[m])
            noise_by_tone.append({"method": m, "tone": seed % len(SKIN_TONES), "verdict": r.verdict_key})
        progress((seed + 1) / max(10, args.seeds), "skin-tone check")
    print()
    folders = [("auto", f) for f in args.videos] + [("real", f) for f in args.real] + [("fake", f) for f in args.fake]
    videos = run_videos(folders, progress, args.segment) if folders else []
    if folders:
        print()
    args.videos = ", ".join(f for _, f in folders)
    report = build_html(syn, noise, dur, videos, args, time.time() - t0)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"Report written to {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()

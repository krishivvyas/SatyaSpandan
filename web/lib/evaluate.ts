// Client-side re-scoring for the accuracy page. Mirrors the quality gate and decision rule in
// backend/rppg_engine.py (analyze_traces), so thresholds can be explored without re-running videos.
import type { CompactResult, EvalResult, Thresholds, VerdictKey } from "./schemas";

export const METHODS = ["POS", "GREEN", "CHROM"] as const;
export type MethodName = (typeof METHODS)[number];

export type StoredClip = EvalResult & { id: string; addedAt: string };

export const GATE_LABELS: Record<string, string> = {
  no_data: "Too little usable video",
  too_short: "Clip too short",
  face_missing: "Face not found often enough",
  face_small: "Face too small",
  motion: "Too much movement",
  low_snr: "Pulse signal too weak",
  ambient: "Background flicker / compression",
  weak_for_flag: "Pulse too weak to compare regions",
};

export type Scored = { verdict: VerdictKey; gates: string[]; scs: number | null; frac: number | null };

export function rescore(r: CompactResult | undefined, t: Thresholds): Scored {
  if (!r) return { verdict: "unable", gates: ["no_data"], scs: null, frac: null };
  const q = r.quality;
  const v = (k: string, d = 0) => (q[k] ?? d) as number;
  const gates: string[] = [];
  if (r.coherence_score == null) gates.push("no_data");
  if (v("duration_s") < t.min_duration_s) gates.push("too_short");
  if (v("face_ratio", 1) < t.min_face_ratio) gates.push("face_missing");
  if (v("face_px", 100) < t.min_face_px) gates.push("face_small");
  if (v("motion") > t.max_median_motion || v("fast_motion_frac") > t.max_fast_motion_frac) gates.push("motion");
  if (r.snr_db == null || r.snr_db < t.min_snr_db) gates.push("low_snr");
  if (v("bg_amp_ratio", 1) >= t.min_bg_amp_ratio && (v("bg_ratio") > t.max_bg_ratio || v("bg_corr") > t.max_bg_corr))
    gates.push("ambient");
  const scs = r.coherence_score;
  const ws = r.windows.filter((w) => w.scs != null);
  const frac = ws.length ? ws.filter((w) => (w.scs as number) >= t.threshold).length / ws.length : null;
  if (gates.length) return { verdict: "unable", gates: [...new Set(gates)], scs, frac };
  // Grey zone (engine: grey_margin): only a score clearly below tau is flagged; borderline -> "No strong signs".
  const manip = scs != null && scs < t.threshold - t.grey_margin;
  // A flag needs a clear pulse: with a weak signal, regions disagree because of noise alone.
  if (manip && (r.snr_db ?? -99) < t.min_snr_flag_db) return { verdict: "unable", gates: ["weak_for_flag"], scs, frac };
  return { verdict: manip ? "manip" : "real", gates, scs, frac };
}

export type Metrics = {
  n: number;
  nReal: number;
  nFake: number;
  matrix: Record<"real" | "fake", Record<VerdictKey, number>>;
  coverage: number | null; // share of labelled clips that were assessed (not "unable")
  accuracyAssessed: number | null;
  accuracyOverall: number | null; // "unable" counted as not correct
  specificity: number | null; // real assessed -> real
  falseAccusation: number | null; // real (all) -> manip
  sensitivity: number | null; // fake assessed -> manip
  hrMae: number | null;
  hrN: number;
  gateCounts: Record<string, number>;
};

const ratio = (a: number, b: number) => (b > 0 ? a / b : null);

export function computeMetrics(clips: StoredClip[], method: MethodName, t: Thresholds): Metrics {
  const matrix = {
    real: { real: 0, manip: 0, unable: 0 },
    fake: { real: 0, manip: 0, unable: 0 },
  };
  const gateCounts: Record<string, number> = {};
  const hrErr: number[] = [];
  for (const c of clips) {
    const r = c.methods[method];
    const s = rescore(r, t);
    s.gates.forEach((g) => (gateCounts[g] = (gateCounts[g] ?? 0) + 1));
    if (c.label === "real" || c.label === "fake") matrix[c.label][s.verdict] += 1;
    if (c.true_bpm != null && r?.bpm != null) hrErr.push(Math.abs(r.bpm - c.true_bpm));
  }
  const R = matrix.real;
  const F = matrix.fake;
  const nReal = R.real + R.manip + R.unable;
  const nFake = F.real + F.manip + F.unable;
  const assessed = R.real + R.manip + F.real + F.manip;
  const correct = R.real + F.manip;
  return {
    n: clips.length,
    nReal,
    nFake,
    matrix,
    coverage: ratio(assessed, nReal + nFake),
    accuracyAssessed: ratio(correct, assessed),
    accuracyOverall: ratio(correct, nReal + nFake),
    specificity: ratio(R.real, R.real + R.manip),
    falseAccusation: ratio(R.manip, nReal),
    sensitivity: ratio(F.manip, F.real + F.manip),
    hrMae: hrErr.length ? hrErr.reduce((a, b) => a + b, 0) / hrErr.length : null,
    hrN: hrErr.length,
    gateCounts,
  };
}

/** Sensitivity / specificity of assessed clips as the coherence threshold sweeps 0-100. */
export function sweep(clips: StoredClip[], method: MethodName, t: Thresholds) {
  const rows = [];
  for (let tau = 0; tau <= 100; tau += 1) {
    const m = computeMetrics(clips, method, { ...t, threshold: tau });
    rows.push({
      tau,
      specificity: m.specificity == null ? null : Math.round(m.specificity * 1000) / 10,
      sensitivity: m.sensitivity == null ? null : Math.round(m.sensitivity * 1000) / 10,
    });
  }
  return rows;
}

/** Highest tau that keeps specificity on real clips >= target (catches the most fakes without exceeding the false-accusation budget). */
export function suggestTau(clips: StoredClip[], method: MethodName, t: Thresholds, target: number): number | null {
  let best: number | null = null;
  for (let tau = 0; tau <= 100; tau += 0.5) {
    const m = computeMetrics(clips, method, { ...t, threshold: tau });
    if (m.specificity != null && m.specificity >= target) best = tau;
  }
  return best;
}

export function pct(x: number | null | undefined, digits = 0) {
  return x == null ? "—" : `${(x * 100).toFixed(digits)}%`;
}

export function toCsv(clips: StoredClip[], t: Thresholds) {
  const head = ["file", "label", "true_bpm", "method", "verdict", "gates", "coherence", "frac_coherent", "snr_db", "bpm",
    "snr_forehead", "snr_left", "snr_right", "bg_ratio", "bg_corr", "bg_amp_ratio", "motion", "face_ratio", "face_px", "duration_s"];
  const lines = [head.join(",")];
  for (const c of clips) {
    for (const m of METHODS) {
      const r = c.methods[m];
      const s = rescore(r, t);
      const q = r?.quality ?? {};
      const cell = (x: unknown) => (x == null ? "" : typeof x === "number" ? String(Math.round(x * 1000) / 1000) : `"${String(x).replace(/"/g, '""')}"`);
      lines.push([c.name, c.label, c.true_bpm, m, s.verdict, s.gates.join("|"), r?.coherence_score, s.frac, r?.snr_db, r?.bpm,
        q.snr_forehead, q.snr_left, q.snr_right, q.bg_ratio, q.bg_corr, q.bg_amp_ratio, q.motion, q.face_ratio, q.face_px, q.duration_s]
        .map(cell).join(","));
    }
  }
  return lines.join("\n");
}

"use client";

import type { Thresholds } from "@/lib/schemas";

type Field = { key: keyof Thresholds; label: string; min: number; max: number; step: number; help: string };

const DECISION: Field[] = [
  { key: "threshold", label: "Coherence threshold τ (%)", min: 0, max: 100, step: 0.5, help: "Score at or above τ counts as a real face." },
  { key: "grey_margin", label: "Grey zone below τ (points)", min: 0, max: 40, step: 1, help: "“Possible manipulation” only if coherence < τ − this. Scores in between count as “No strong signs” (low confidence)." },
  { key: "min_frac_coherent", label: "Min. share of coherent windows", min: 0, max: 1, step: 0.05, help: "Below this a clip above τ is reported with low confidence (no longer changes the verdict)." },
];

const GATE: Field[] = [
  { key: "min_snr_db", label: "Min. signal quality (dB, best region)", min: -10, max: 10, step: 0.5, help: "Below this the clip is 'Unable to assess'. Pure camera noise reaches about +0.4 dB." },
  { key: "min_snr_flag_db", label: "Min. signal quality to flag (dB)", min: -10, max: 15, step: 0.5, help: "A 'Possible manipulation' verdict needs at least this; weaker clips that would be flagged become 'Unable to assess'." },
  { key: "min_duration_s", label: "Min. duration (s)", min: 2, max: 20, step: 0.5, help: "Usable face video needed." },
  { key: "max_bg_ratio", label: "Max. background peak ratio", min: 0, max: 2, step: 0.05, help: "Background's power at the pulse frequency vs the face's." },
  { key: "max_bg_corr", label: "Max. background correlation", min: 0, max: 1, step: 0.05, help: "Face pulse vs background wave." },
  { key: "min_bg_amp_ratio", label: "Background strength needed to block", min: 0, max: 2, step: 0.05, help: "Ambient check only applies if the background fluctuates at least this much relative to the face." },
  { key: "max_median_motion", label: "Max. head motion", min: 0, max: 0.3, step: 0.005, help: "Median landmark shift per frame ÷ eye distance." },
  { key: "max_fast_motion_frac", label: "Max. share of fast-motion frames", min: 0, max: 1, step: 0.05, help: "Frames moving > 0.10 eye distance." },
  { key: "min_face_ratio", label: "Min. face-found ratio", min: 0, max: 1, step: 0.05, help: "Share of frames with a tracked face." },
  { key: "min_face_px", label: "Min. face size (px)", min: 0, max: 200, step: 5, help: "Eye-to-eye distance in the original video." },
];

function Slider({ f, t, defaults, onChange }: { f: Field; t: Thresholds; defaults: Thresholds; onChange: (t: Thresholds) => void }) {
  const v = t[f.key];
  const changed = Math.abs(v - defaults[f.key]) > 1e-9;
  return (
    <label className="block text-sm">
      <span className="flex items-baseline gap-2">
        <span className="font-medium">{f.label}</span>
        <input
          type="number"
          value={v}
          min={f.min}
          max={f.max}
          step={f.step}
          onChange={(e) => onChange({ ...t, [f.key]: Number(e.target.value) })}
          className="ml-auto w-20 rounded-md border border-border bg-bg px-1.5 py-0.5 text-right tabular-nums"
        />
      </span>
      <input
        type="range"
        min={f.min}
        max={f.max}
        step={f.step}
        value={v}
        onChange={(e) => onChange({ ...t, [f.key]: Number(e.target.value) })}
        className="mt-1 w-full accent-[var(--accent)]"
      />
      <span className="block text-xs text-muted">
        {f.help} Default {defaults[f.key]}.{changed && <span className="text-accent"> Changed.</span>}
      </span>
    </label>
  );
}

export function ThresholdsPanel({
  t,
  defaults,
  onChange,
}: {
  t: Thresholds;
  defaults: Thresholds;
  onChange: (t: Thresholds) => void;
}) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div className="space-y-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Decision</p>
        {DECISION.map((f) => (
          <Slider key={f.key} f={f} t={t} defaults={defaults} onChange={onChange} />
        ))}
      </div>
      <div className="space-y-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Quality gate (“Unable to assess”)</p>
        {GATE.map((f) => (
          <Slider key={f.key} f={f} t={t} defaults={defaults} onChange={onChange} />
        ))}
      </div>
    </div>
  );
}

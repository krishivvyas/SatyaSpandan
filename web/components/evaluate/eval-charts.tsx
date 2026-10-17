"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { rescore, sweep, type MethodName, type StoredClip } from "@/lib/evaluate";
import type { Thresholds } from "@/lib/schemas";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };
const TT = {
  contentStyle: { background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "var(--fg)" },
};

/** Coherence score of every assessed clip, split by its true label, with the threshold line. */
export function ScoreStrip({ clips, method, t }: { clips: StoredClip[]; method: MethodName; t: Thresholds }) {
  const { real, fake, unknown } = useMemo(() => {
    const out = { real: [] as object[], fake: [] as object[], unknown: [] as object[] };
    clips.forEach((c, i) => {
      const s = rescore(c.methods[method], t);
      if (s.scs == null || s.verdict === "unable") return;
      const jitter = ((i * 37) % 21) / 100 - 0.1;
      const y = c.label === "real" ? 2 : c.label === "fake" ? 1 : 0;
      out[c.label].push({ scs: Math.round(s.scs * 10) / 10, y: y + jitter, name: c.name });
    });
    return out;
  }, [clips, method, t]);
  const any = real.length + fake.length + unknown.length > 0;
  return (
    <div>
      <h3 className="font-semibold">Coherence scores by true label</h3>
      <p className="text-sm text-muted mb-2">
        Good separation means green dots (real) sit right of the line and amber dots (fake) sit left. Clips stopped by
        the quality gate are not shown.
      </p>
      {!any ? (
        <div className="grid h-48 place-items-center text-sm text-muted">No assessed clips for {method} yet.</div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="scs" domain={[0, 100]} unit="%" {...AXIS} name="Coherence" />
            <YAxis type="number" dataKey="y" domain={[-0.5, 2.5]} ticks={[0, 1, 2]} tickFormatter={(v) => ["unknown", "fake", "real"][v] ?? ""} {...AXIS} width={64} />
            <ZAxis range={[60, 60]} />
            <Tooltip {...TT} cursor={{ strokeDasharray: "3 3" }} formatter={(v, n) => (n === "Coherence" ? `${v}%` : null)} labelFormatter={() => ""} />
            <ReferenceLine x={t.threshold} stroke="var(--fg)" strokeDasharray="4 4" label={{ value: `τ ${t.threshold}`, position: "insideTopRight", fill: "var(--fg)", fontSize: 11 }} />
            <Scatter name="Real" data={real} fill="var(--real)" />
            <Scatter name="Fake" data={fake} fill="var(--manip)" />
            <Scatter name="Unknown" data={unknown} fill="var(--unable)" />
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

/** Sensitivity and specificity as the threshold moves. */
export function ThresholdSweep({ clips, method, t }: { clips: StoredClip[]; method: MethodName; t: Thresholds }) {
  const data = useMemo(() => sweep(clips, method, t), [clips, method, t]);
  const any = data.some((d) => d.specificity != null || d.sensitivity != null);
  return (
    <div>
      <h3 className="font-semibold">Threshold sweep</h3>
      <p className="text-sm text-muted mb-2">
        Specificity = real clips passed. Sensitivity = fakes flagged. Raising τ catches more fakes but accuses more
        real people.
      </p>
      {!any ? (
        <div className="grid h-48 place-items-center text-sm text-muted">Add labelled clips that pass the quality gate.</div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis dataKey="tau" type="number" domain={[0, 100]} {...AXIS} unit="" />
            <YAxis domain={[0, 100]} unit="%" {...AXIS} />
            <Tooltip {...TT} labelFormatter={(v) => `τ = ${v}`} formatter={(v) => (v == null ? "—" : `${v}%`)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <ReferenceLine x={t.threshold} stroke="var(--fg)" strokeDasharray="4 4" />
            <ReferenceLine y={90} stroke="var(--real)" strokeDasharray="2 4" />
            <Line dataKey="specificity" name="Specificity (real passed)" stroke="var(--real)" dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
            <Line dataKey="sensitivity" name="Sensitivity (fakes flagged)" stroke="var(--manip)" dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

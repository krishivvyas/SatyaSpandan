"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ROI_META } from "@/lib/copy";
import type { AnalysisResult } from "@/lib/schemas";
import { cn } from "@/lib/utils";

const ROIS = ["forehead", "left", "right"] as const;
const AXIS = { stroke: "var(--muted)", fontSize: 12 };
const TOOLTIP_STYLE = {
  contentStyle: { background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "var(--fg)" },
};

function Empty({ text }: { text: string }) {
  return <div className="grid h-64 place-items-center text-sm text-muted">{text}</div>;
}

/** Filtered pulse waves of the three regions on one shared time axis. */
export function PulseWaveChart({ result }: { result: AnalysisResult }) {
  const [mode, setMode] = useState<"overlay" | "stacked">("overlay");
  const data = useMemo(
    () =>
      result.t.map((t, i) => ({
        t,
        forehead: result.signals.forehead?.[i],
        left: result.signals.left?.[i],
        right: result.signals.right?.[i],
      })),
    [result],
  );
  // shade the central 2-second step of each low-coherence window
  const bad = useMemo(() => {
    const w = result.windows;
    if (w.length === 0 || result.verdict_key === "unable") return [];
    const step = w.length > 1 ? w[1].t_start - w[0].t_start : w[0].t_end - w[0].t_start;
    const last = w.length - 1;
    return w
      .map((x, i): [number, number, number | null] => {
        if (w.length === 1) return [x.t_start, x.t_end, x.scs];
        const mid = (x.t_start + x.t_end) / 2;
        // the first and last windows also own the clip edges they alone cover
        return [i === 0 ? x.t_start : mid - step / 2, i === last ? x.t_end : mid + step / 2, x.scs];
      })
      .filter(([, , scs]) => scs != null && scs < result.threshold);
  }, [result]);

  if (data.length === 0) return <Empty text="Not enough usable video to draw the pulse waves." />;

  const shading = bad.map(([a, b], i) => (
    <ReferenceArea key={i} x1={a} x2={b} fill="var(--manip)" fillOpacity={0.12} strokeOpacity={0} ifOverflow="hidden" />
  ));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <p className="text-muted flex-1 min-w-48">
          In a real face the three lines rise and fall together.
          {bad.length > 0 && <span> Amber bands mark stretches where the regions disagree.</span>}
        </p>
        <div className="inline-flex rounded-lg border border-border p-0.5" role="group" aria-label="Chart layout">
          {(["overlay", "stacked"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              aria-pressed={mode === m}
              className={cn("rounded-md px-3 py-1 capitalize", mode === m ? "bg-fg text-bg" : "text-muted hover:text-fg")}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      {mode === "overlay" ? (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            {shading}
            <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => `${Math.round(v)}s`} {...AXIS} />
            <YAxis {...AXIS} tickFormatter={(v) => v.toFixed(0)} />
            <Tooltip {...TOOLTIP_STYLE} labelFormatter={(v) => `${Number(v).toFixed(2)} s`} formatter={(v) => Number(v).toFixed(2)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {ROIS.map((k) => (
              <Line key={k} dataKey={k} name={ROI_META[k].label} stroke={ROI_META[k].color} dot={false} strokeWidth={1.6} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="space-y-1">
          {ROIS.map((k) => (
            <div key={k}>
              <p className="text-xs font-medium" style={{ color: ROI_META[k].color }}>{ROI_META[k].label}</p>
              <ResponsiveContainer width="100%" height={110}>
                <LineChart data={data} syncId="pulse" margin={{ top: 4, right: 12, bottom: 0, left: -16 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                  {shading}
                  <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => `${Math.round(v)}s`} {...AXIS} hide={k !== "right"} />
                  <YAxis {...AXIS} tickFormatter={(v) => v.toFixed(0)} />
                  <Tooltip {...TOOLTIP_STYLE} labelFormatter={(v) => `${Number(v).toFixed(2)} s`} formatter={(v) => Number(v).toFixed(2)} />
                  <Line dataKey={k} name={ROI_META[k].label} stroke={ROI_META[k].color} dot={false} strokeWidth={1.6} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Power spectrum per region (x-axis in bpm) with the detected heart rate marked. */
export function SpectrumChart({ result }: { result: AnalysisResult }) {
  const data = useMemo(() => {
    const axis = result.psd.bpm_axis ?? [];
    return axis
      .map((bpm, i) => ({
        bpm,
        forehead: result.psd.forehead?.[i],
        left: result.psd.left?.[i],
        right: result.psd.right?.[i],
        background: result.psd.background?.[i],
      }))
      .filter((d) => d.bpm >= 30 && d.bpm <= 200);
  }, [result]);
  if (data.length === 0) return <Empty text="No spectrum available for this clip." />;
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Each region&apos;s strongest frequency should be the same heartbeat. A peak that also appears in the dashed
        background line is lighting or compression noise, not a pulse.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="bpm" type="number" domain={[30, 200]} ticks={[40, 60, 80, 100, 120, 140, 160, 180, 200]} {...AXIS} unit=" bpm" />
          <YAxis {...AXIS} tickFormatter={(v) => v.toFixed(1)} />
          <Tooltip {...TOOLTIP_STYLE} labelFormatter={(v) => `${Number(v).toFixed(0)} bpm`} formatter={(v) => Number(v).toFixed(3)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {ROIS.map((k) => (
            <Line key={k} dataKey={k} name={ROI_META[k].label} stroke={ROI_META[k].color} dot={false} strokeWidth={1.6} isAnimationActive={false} />
          ))}
          <Line dataKey="background" name="Background" stroke="var(--roi-bg)" strokeDasharray="5 4" dot={false} strokeWidth={1.4} isAnimationActive={false} />
          {result.bpm != null && (
            <ReferenceLine x={result.bpm} stroke="var(--accent)" strokeWidth={1.5} label={{ value: `${result.bpm.toFixed(0)} bpm`, position: "top", fill: "var(--accent)", fontSize: 12 }} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Spatial coherence score for each 10-second window, against the decision threshold. */
export function CoherenceTimeline({ result }: { result: AnalysisResult }) {
  const data = result.windows.map((w) => ({
    label: `${w.t_start.toFixed(0)}–${w.t_end.toFixed(0)}s`,
    scs: w.scs == null ? 0 : Math.round(w.scs * 10) / 10,
    bpm: w.bpm,
    pass: w.scs != null && w.scs >= result.threshold,
  }));
  if (data.length === 0) return <Empty text="No analysis windows for this clip." />;
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        The clip is checked in overlapping 10-second windows. Bars above the line ({result.threshold.toFixed(0)}%) look
        like a real face; bars below it show the regions disagreeing.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" />
          <YAxis domain={[0, 100]} {...AXIS} unit="%" />
          <Tooltip
            {...TOOLTIP_STYLE}
            cursor={{ fill: "var(--border)", fillOpacity: 0.4 }}
            formatter={(v, name) => (name === "scs" ? [`${v}%`, "Coherence"] : [v, name])}
          />
          <ReferenceLine y={result.threshold} stroke="var(--fg)" strokeDasharray="4 4" />
          <Bar dataKey="scs" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.pass ? "var(--real)" : "var(--manip)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

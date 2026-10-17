import { Activity, Gauge, HeartPulse, ScanFace } from "lucide-react";
import { METRIC_HELP } from "@/lib/copy";
import type { AnalysisResult } from "@/lib/schemas";
import { fmt, snrLabel } from "@/lib/utils";
import { InfoTip } from "./info-tip";

export function MetricCards({ result }: { result: AnalysisResult }) {
  const faceRatio = result.quality.face_ratio;
  // When the clip cannot be assessed, BPM and coherence are not meaningful: don't present them as findings.
  const unreliable = result.verdict_key === "unable";
  const na = "not reliable for this clip";
  const items = [
    { icon: HeartPulse, label: "Estimated heart rate", value: unreliable ? "—" : fmt(result.bpm, 0), unit: "bpm", sub: unreliable ? na : undefined, help: METRIC_HELP.bpm },
    {
      icon: Activity,
      label: "Spatial coherence",
      value: unreliable ? "—" : fmt(result.coherence_score, 0),
      unit: "%",
      sub: unreliable ? na : `threshold ${result.threshold.toFixed(0)}%`,
      help: METRIC_HELP.coherence,
    },
    {
      icon: Gauge,
      label: "Signal quality",
      value: fmt(result.snr_db, 1),
      unit: "dB",
      sub: snrLabel(result.snr_db),
      help: METRIC_HELP.snr,
    },
    {
      icon: ScanFace,
      label: "Face tracking",
      value: fmt(faceRatio == null ? null : faceRatio * 100, 0),
      unit: "%",
      sub: result.quality.duration_s ? `${result.quality.duration_s.toFixed(1)} s analysed` : undefined,
      help: METRIC_HELP.tracking,
    },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {items.map(({ icon: Icon, label, value, unit, sub, help }) => (
        <div key={label} className="card p-4">
          <div className="flex items-center gap-2 text-sm text-muted">
            <Icon className="size-4" aria-hidden />
            <span>{label}</span>
            <InfoTip text={help} />
          </div>
          <p className="mt-2 text-3xl font-bold tabular-nums">
            {value}
            {value !== "—" && <span className="ml-1 text-base font-medium text-muted">{unit}</span>}
          </p>
          {sub && <p className="text-xs text-muted mt-0.5">{sub}</p>}
        </div>
      ))}
    </div>
  );
}

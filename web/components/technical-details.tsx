import { ChevronDown, Wrench } from "lucide-react";
import type { AnalysisResult } from "@/lib/schemas";

type Row = [label: string, key: string, digits: number, unit: string, limit?: string];

// Quality-gate inputs, with the limits from backend EngineConfig, so a reviewer can see exactly what
// drove an "Unable to assess" result.
const ROWS: Row[] = [
  ["Duration analysed", "duration_s", 1, " s", "≥ 6 s"],
  ["Frame rate", "fps", 1, " fps"],
  ["Face found", "face_ratio", 2, "", "≥ 0.80"],
  ["Face size (eye-to-eye)", "face_px", 0, " px", "≥ 40 px"],
  ["Head / camera motion", "motion", 3, "", "≤ 0.05"],
  ["Signal quality, forehead", "snr_forehead", 2, " dB"],
  ["Signal quality, left cheek", "snr_left", 2, " dB"],
  ["Signal quality, right cheek", "snr_right", 2, " dB", "best region ≥ 1 dB (≥ 2 dB to flag)"],
  ["Background peak ratio", "bg_ratio", 2, "", "≤ 0.50"],
  ["Background correlation", "bg_corr", 2, "", "≤ 0.60"],
  ["Background strength vs face", "bg_amp_ratio", 2, "", "ambient only counted if ≥ 0.50"],
  ["Background box texture", "bg_texture", 1, "", "lower = plainer patch (more reliable)"],
  ["Coherent windows", "frac_coherent", 2, "", "≥ 0.60"],
  ["Largest heart-rate jump", "max_hr_jump_bpm", 1, " bpm", "≤ 15 bpm"],
];

export function TechnicalDetails({ result }: { result: AnalysisResult }) {
  const q = result.quality;
  return (
    <details className="card group">
      <summary className="flex cursor-pointer list-none items-center gap-2 p-4 font-semibold [&::-webkit-details-marker]:hidden">
        <Wrench className="size-5 text-muted" aria-hidden />
        Technical details
        <span className="ml-1 text-sm font-normal text-muted">Signal-quality checks behind this result</span>
        <ChevronDown className="ml-auto size-5 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="px-4 py-2 font-medium">Check</th>
              <th className="px-4 py-2 font-medium">Value</th>
              <th className="px-4 py-2 font-medium">Limit</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.filter(([, key]) => q[key] !== undefined).map(([label, key, digits, unit, limit]) => {
              const v = q[key];
              return (
                <tr key={key} className="border-t border-border">
                  <td className="px-4 py-2">{label}</td>
                  <td className="px-4 py-2 font-mono tabular-nums">{v == null ? "—" : `${v.toFixed(digits)}${unit}`}</td>
                  <td className="px-4 py-2 text-muted">{limit ?? ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

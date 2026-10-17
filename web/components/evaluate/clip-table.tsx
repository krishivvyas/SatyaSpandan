"use client";

import { Fragment, useState } from "react";
import { ChevronRight, Trash2 } from "lucide-react";
import { GATE_LABELS, METHODS, rescore, type StoredClip } from "@/lib/evaluate";
import type { Thresholds, VerdictKey } from "@/lib/schemas";
import { cn, fmt } from "@/lib/utils";

const CHIP: Record<VerdictKey, string> = {
  real: "bg-real/15 text-real",
  manip: "bg-manip/15 text-manip",
  unable: "bg-unable/15 text-unable",
};
const SHORT: Record<VerdictKey, string> = { real: "No signs", manip: "Manip.", unable: "Unable" };

function correctness(label: string, v: VerdictKey) {
  if (label === "unknown" || v === "unable") return null;
  return (label === "real" && v === "real") || (label === "fake" && v === "manip");
}

const DETAIL_ROWS: [string, string, number][] = [
  ["Duration (s)", "duration_s", 1],
  ["FPS", "fps", 1],
  ["Face found", "face_ratio", 2],
  ["Face size (px)", "face_px", 0],
  ["Motion", "motion", 3],
  ["SNR forehead (dB)", "snr_forehead", 2],
  ["SNR left (dB)", "snr_left", 2],
  ["SNR right (dB)", "snr_right", 2],
  ["Bg peak ratio", "bg_ratio", 2],
  ["Bg correlation", "bg_corr", 2],
  ["Bg strength vs face", "bg_amp_ratio", 2],
  ["Max HR jump (bpm)", "max_hr_jump_bpm", 1],
];

export function ClipTable({
  clips,
  t,
  onRemove,
}: {
  clips: StoredClip[];
  t: Thresholds;
  onRemove: (id: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (clips.length === 0) return <p className="text-sm text-muted">No clips yet. Add some above.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-muted">
            <th className="py-2 pr-2" />
            <th className="py-2 pr-3 font-medium">Clip</th>
            <th className="py-2 pr-3 font-medium">Truth</th>
            {METHODS.map((m) => (
              <th key={m} className="py-2 pr-3 font-medium">{m}</th>
            ))}
            <th />
          </tr>
        </thead>
        <tbody>
          {clips.map((c) => (
            <Fragment key={c.id}>
              <tr className="border-t border-border align-top">
                <td className="py-2 pr-2">
                  <button
                    aria-label="Show details"
                    aria-expanded={open === c.id}
                    onClick={() => setOpen(open === c.id ? null : c.id)}
                    className="text-muted hover:text-fg"
                  >
                    <ChevronRight className={cn("size-4 transition-transform", open === c.id && "rotate-90")} />
                  </button>
                </td>
                <td className="py-2 pr-3">
                  <div className="flex items-center gap-2">
                    {c.thumb_jpeg_b64 && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={`data:image/jpeg;base64,${c.thumb_jpeg_b64}`} alt="" className="h-10 w-8 rounded object-cover" />
                    )}
                    <span className="max-w-48 truncate" title={c.name ?? ""}>{c.name}</span>
                  </div>
                </td>
                <td className="py-2 pr-3">
                  <span className="capitalize">{c.label}</span>
                  {c.true_bpm != null && <span className="block text-xs text-muted">{c.true_bpm} bpm</span>}
                </td>
                {METHODS.map((m) => {
                  const r = c.methods[m];
                  const s = rescore(r, t);
                  const ok = correctness(c.label, s.verdict);
                  return (
                    <td key={m} className="py-2 pr-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", CHIP[s.verdict])}>
                        {SHORT[s.verdict]}
                        {ok === true && " ✓"}
                        {ok === false && " ✗"}
                      </span>
                      <span className="mt-1 block text-xs text-muted tabular-nums">
                        {fmt(r?.coherence_score, 0, "%")} · {fmt(r?.snr_db, 1, " dB")} · {fmt(r?.bpm, 0, " bpm")}
                      </span>
                    </td>
                  );
                })}
                <td className="py-2 text-right">
                  <button aria-label={`Remove ${c.name}`} onClick={() => onRemove(c.id)} className="text-muted hover:text-fg">
                    <Trash2 className="size-4" />
                  </button>
                </td>
              </tr>
              {open === c.id && (
                <tr className="bg-bg/50">
                  <td />
                  <td colSpan={METHODS.length + 3} className="py-3 pr-3">
                    <div className="grid gap-4 md:grid-cols-3">
                      {METHODS.map((m) => {
                        const r = c.methods[m];
                        const s = rescore(r, t);
                        return (
                          <div key={m} className="rounded-lg border border-border p-3">
                            <p className="font-semibold">{m}</p>
                            <p className="text-xs text-muted">
                              Coherence {fmt(r?.coherence_score, 1, "%")} · coherent windows {s.frac == null ? "—" : `${Math.round(s.frac * 100)}%`}
                            </p>
                            {s.gates.length > 0 && (
                              <p className="mt-1 text-xs text-unable">Blocked by: {s.gates.map((g) => GATE_LABELS[g] ?? g).join(", ")}</p>
                            )}
                            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
                              {DETAIL_ROWS.map(([label, key, d]) => (
                                <Fragment key={key}>
                                  <dt className="text-muted">{label}</dt>
                                  <dd className="text-right font-mono tabular-nums">{fmt(r?.quality[key] ?? null, d)}</dd>
                                </Fragment>
                              ))}
                              {r &&
                                Object.entries(r.pairs).map(([pair, p]) => (
                                  <Fragment key={pair}>
                                    <dt className="text-muted">r / MSC {pair}</dt>
                                    <dd className="text-right font-mono tabular-nums">{fmt(p.r, 2)} / {fmt(p.msc, 2)}</dd>
                                  </Fragment>
                                ))}
                            </dl>
                          </div>
                        );
                      })}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, RotateCcw, Save, Sparkles, Trash2 } from "lucide-react";
import { getCalibration, resetCalibration, saveCalibration } from "@/lib/api";
import { GATE_LABELS, METHODS, computeMetrics, pct, suggestTau, toCsv, type MethodName, type StoredClip } from "@/lib/evaluate";
import type { EvalResult, Thresholds } from "@/lib/schemas";
import { cn } from "@/lib/utils";
import { ClipTable } from "./clip-table";
import { ScoreStrip, ThresholdSweep } from "./eval-charts";
import { EvalUploader } from "./eval-uploader";
import { ThresholdsPanel } from "./thresholds-panel";

const STORE_KEY = "satya-eval-v1";

function loadClips(): StoredClip[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as StoredClip[]) : [];
  } catch {
    return [];
  }
}

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function EvalDashboard() {
  const cal = useQuery({ queryKey: ["calibration"], queryFn: getCalibration });
  const [clips, setClips] = useState<StoredClip[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [t, setT] = useState<Thresholds | null>(null);
  const [method, setMethod] = useState<MethodName>("POS");
  const [target, setTarget] = useState(0.9);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    // localStorage is only available after mount
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClips(loadClips());
    setLoaded(true);
  }, []);
  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(clips));
    } catch {
      /* storage full or blocked: results still work for this session */
    }
  }, [clips, loaded]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (cal.data && !t) setT({ ...cal.data.defaults, ...cal.data.current });
  }, [cal.data, t]);

  const metrics = useMemo(
    () => (t ? Object.fromEntries(METHODS.map((m) => [m, computeMetrics(clips, m, t)])) : null),
    [clips, t],
  );

  if (cal.error) return <p className="card p-6 text-manip">{cal.error.message}</p>;
  if (!t || !cal.data || !metrics) return <div className="card h-72 animate-pulse" />;
  const defaults = cal.data.defaults;
  const m = metrics[method];

  const addResult = (r: EvalResult) =>
    setClips((prev) => [...prev, { ...r, id: crypto.randomUUID(), addedAt: new Date().toISOString() }]);

  async function onSave() {
    try {
      await saveCalibration(t!);
      await cal.refetch();
      setMsg("Saved. New analyses on the main page now use these thresholds.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }
  async function onResetSaved() {
    await resetCalibration();
    await cal.refetch();
    setT({ ...defaults });
    setMsg("Saved calibration removed. The engine is back to its built-in defaults.");
  }

  const labelled = m.nReal + m.nFake;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Accuracy testing</h1>
        <p className="mt-2 max-w-3xl text-muted">
          Measure how SatyaSpandan performs on <strong>your own labelled clips</strong>, compare POS, CHROM and GREEN,
          see which quality check blocks clips, and tune the thresholds. Aim for at least 10 real and 10 fake clips
          from several different people, each 15–20 s long. For heart-rate accuracy, note the true pulse from a
          smartwatch or pulse oximeter while recording. Only use clips you have consent for.
        </p>
      </header>

      <EvalUploader onResult={addResult} />

      <section className="card p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-semibold">2 · Results</h2>
          <span className="text-sm text-muted">
            {clips.length} clip{clips.length === 1 ? "" : "s"} · {m.nReal} real · {m.nFake} fake
          </span>
          <div className="ml-auto flex flex-wrap gap-2">
            <button className="btn-secondary" disabled={!clips.length} onClick={() => download("satyaspandan-eval.csv", toCsv(clips, t), "text/csv")}>
              <Download className="size-4" /> CSV
            </button>
            <button className="btn-secondary" disabled={!clips.length} onClick={() => download("satyaspandan-eval.json", JSON.stringify({ thresholds: t, clips }, null, 2), "application/json")}>
              <Download className="size-4" /> JSON
            </button>
            <button
              className="btn-secondary"
              disabled={!clips.length}
              onClick={() => {
                if (confirm("Remove all clips from this page? (This only clears the results stored in this browser.)")) setClips([]);
              }}
            >
              <Trash2 className="size-4" /> Clear
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-2 pr-3 font-medium">Method</th>
                <th className="py-2 pr-3 font-medium" title="Labelled clips that passed the quality gate">Assessed</th>
                <th className="py-2 pr-3 font-medium" title="Correct among assessed clips">Accuracy (assessed)</th>
                <th className="py-2 pr-3 font-medium" title="Correct among all labelled clips; 'Unable' counts as not correct">Accuracy (all)</th>
                <th className="py-2 pr-3 font-medium" title="Assessed real clips that passed">Specificity</th>
                <th className="py-2 pr-3 font-medium" title="All real clips flagged as manipulated">False accusations</th>
                <th className="py-2 pr-3 font-medium" title="Assessed fakes that were flagged">Sensitivity</th>
                <th className="py-2 pr-3 font-medium">HR error (MAE)</th>
              </tr>
            </thead>
            <tbody>
              {METHODS.map((name) => {
                const x = metrics[name];
                return (
                  <tr
                    key={name}
                    onClick={() => setMethod(name)}
                    className={cn("cursor-pointer border-t border-border", name === method && "bg-accent/5")}
                  >
                    <td className="py-2 pr-3 font-semibold">{name}{name === method && <span className="ml-1 text-xs text-accent">selected</span>}</td>
                    <td className="py-2 pr-3 tabular-nums">{pct(x.coverage)}</td>
                    <td className="py-2 pr-3 tabular-nums">{pct(x.accuracyAssessed)}</td>
                    <td className="py-2 pr-3 tabular-nums">{pct(x.accuracyOverall)}</td>
                    <td className="py-2 pr-3 tabular-nums">{pct(x.specificity)}</td>
                    <td className={cn("py-2 pr-3 tabular-nums", (x.falseAccusation ?? 0) > 0.1 && "text-manip font-semibold")}>{pct(x.falseAccusation)}</td>
                    <td className="py-2 pr-3 tabular-nums">{pct(x.sensitivity)}</td>
                    <td className="py-2 pr-3 tabular-nums">{x.hrMae == null ? "—" : `${x.hrMae.toFixed(1)} bpm (n=${x.hrN})`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-1 text-xs text-muted">Click a row to choose the method for the charts below. With few clips, every percentage is very uncertain.</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div>
            <h3 className="font-semibold">Confusion matrix · {method}</h3>
            <table className="mt-2 w-full text-sm">
              <thead>
                <tr className="text-muted">
                  <th className="py-1 text-left font-medium">Truth ↓ / Verdict →</th>
                  <th className="py-1 font-medium text-real">No signs</th>
                  <th className="py-1 font-medium text-manip">Manip.</th>
                  <th className="py-1 font-medium text-unable">Unable</th>
                </tr>
              </thead>
              <tbody className="text-center tabular-nums">
                {(["real", "fake"] as const).map((truth) => (
                  <tr key={truth} className="border-t border-border">
                    <td className="py-2 text-left capitalize font-medium">{truth}</td>
                    {(["real", "manip", "unable"] as const).map((v) => {
                      const good = (truth === "real" && v === "real") || (truth === "fake" && v === "manip");
                      const bad = (truth === "real" && v === "manip") || (truth === "fake" && v === "real");
                      return (
                        <td key={v} className={cn("py-2 text-lg font-semibold", good && "text-real", bad && m.matrix[truth][v] > 0 && "text-manip")}>
                          {m.matrix[truth][v]}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {labelled === 0 && <p className="mt-2 text-xs text-muted">Label clips as real or fake to fill this in.</p>}
          </div>
          <div className="lg:col-span-2">
            <h3 className="font-semibold">Why clips were “Unable to assess” · {method}</h3>
            {Object.keys(m.gateCounts).length === 0 ? (
              <p className="mt-2 text-sm text-muted">No clips blocked by the quality gate.</p>
            ) : (
              <ul className="mt-2 space-y-1.5 text-sm">
                {Object.entries(m.gateCounts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([g, n]) => (
                    <li key={g} className="flex items-center gap-2">
                      <span className="w-56 shrink-0">{GATE_LABELS[g] ?? g}</span>
                      <span className="h-2 rounded-full bg-unable/60" style={{ width: `${(n / Math.max(1, clips.length)) * 100}%`, maxWidth: "60%" }} />
                      <span className="tabular-nums text-muted">{n}/{clips.length}</span>
                    </li>
                  ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted">A clip can fail several checks at once. Open a clip below to see its exact values.</p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <ScoreStrip clips={clips} method={method} t={t} />
          <ThresholdSweep clips={clips} method={method} t={t} />
        </div>
      </section>

      <section className="card p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-semibold">3 · Tune thresholds</h2>
          <span className="text-sm text-muted">Changes re-score every clip instantly; no re-upload needed.</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border p-3 text-sm">
          <Sparkles className="size-4 text-accent" aria-hidden />
          <span>Suggest τ for {method} that keeps specificity at or above</span>
          <select value={target} onChange={(e) => setTarget(Number(e.target.value))} className="rounded-md border border-border bg-bg px-1.5 py-0.5">
            {[0.8, 0.85, 0.9, 0.95, 1].map((x) => (
              <option key={x} value={x}>{Math.round(x * 100)}%</option>
            ))}
          </select>
          <button
            className="btn-secondary"
            onClick={() => {
              const tau = suggestTau(clips, method, t, target);
              if (tau == null) setMsg("Not enough assessed real clips to suggest a threshold.");
              else {
                setT({ ...t, threshold: tau });
                setMsg(`τ set to ${tau} for ${method}. Check the sweep chart, then save if it looks right.`);
              }
            }}
          >
            Suggest
          </button>
        </div>
        <ThresholdsPanel t={t} defaults={defaults} onChange={setT} />
        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          <button className="btn-primary" onClick={onSave}>
            <Save className="size-4" /> Save as engine calibration
          </button>
          <button className="btn-secondary" onClick={() => setT({ ...defaults })}>
            <RotateCcw className="size-4" /> Back to defaults (unsaved)
          </button>
          <button className="btn-secondary" disabled={Object.keys(cal.data.current).length === 0} onClick={onResetSaved}>
            Remove saved calibration
          </button>
        </div>
        {msg && <p className="text-sm" role="status">{msg}</p>}
        <p className="text-xs text-muted">
          Saved thresholds apply to all three methods and are stored in <code>backend/calibration.json</code>. Avoid
          tuning on the same few clips you then report accuracy on. Hold some clips back, and keep every clip of one
          person on the same side.
        </p>
      </section>

      <section className="card p-4 sm:p-5">
        <h2 className="mb-3 font-semibold">4 · Clips</h2>
        <ClipTable clips={clips} t={t} onRemove={(id) => setClips((p) => p.filter((c) => c.id !== id))} />
      </section>
    </div>
  );
}

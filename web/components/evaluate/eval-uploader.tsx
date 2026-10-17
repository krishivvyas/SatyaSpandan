"use client";

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { LoaderCircle, Play, Trash2, Upload } from "lucide-react";
import { evaluateUpload, getEvalJob } from "@/lib/api";
import type { EvalResult, Label } from "@/lib/schemas";
import { cn } from "@/lib/utils";

type Item = {
  key: string;
  file: File;
  label: Label;
  trueBpm: string;
  status: "waiting" | "uploading" | "running" | "done" | "error";
  stage?: string;
  progress?: number;
  error?: string;
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function EvalUploader({ onResult }: { onResult: (r: EvalResult) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [defaultLabel, setDefaultLabel] = useState<Label>("real");
  const [running, setRunning] = useState(false);
  const [rejectMsg, setRejectMsg] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      setRejectMsg(rejected.length ? `${rejected.length} file(s) skipped (not a video, or larger than 50 MB).` : null);
      setItems((prev) => [
        ...prev,
        ...accepted.map((file) => ({
          key: `${file.name}-${file.size}-${Math.random().toString(36).slice(2, 8)}`,
          file,
          label: defaultLabel,
          trueBpm: "",
          status: "waiting" as const,
        })),
      ]);
    },
    [defaultLabel],
  );
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "video/*": [".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v"] },
    maxSize: 50 * 1024 * 1024,
  });

  const patch = (key: string, p: Partial<Item>) => setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...p } : it)));

  async function runAll() {
    setRunning(true);
    // One clip at a time: face tracking is CPU-heavy, and the demo machine is a laptop.
    for (const it of items.filter((i) => i.status === "waiting" || i.status === "error")) {
      try {
        patch(it.key, { status: "uploading", error: undefined, progress: 0 });
        const bpm = it.trueBpm.trim() === "" ? null : Number(it.trueBpm);
        const { job_id } = await evaluateUpload(it.file, it.label, bpm != null && Number.isFinite(bpm) ? bpm : null);
        patch(it.key, { status: "running" });
        for (;;) {
          await sleep(700);
          const job = await getEvalJob(job_id);
          patch(it.key, { stage: job.stage, progress: job.progress });
          if (job.status === "done" && job.result) {
            onResult(job.result);
            patch(it.key, { status: "done" });
            break;
          }
          if (job.status === "error") throw new Error(job.error ?? "Analysis failed.");
        }
      } catch (e) {
        patch(it.key, { status: "error", error: e instanceof Error ? e.message : String(e) });
      }
    }
    setRunning(false);
    setItems((prev) => prev.filter((i) => i.status !== "done"));
  }

  const pending = items.filter((i) => i.status === "waiting" || i.status === "error").length;

  return (
    <section className="card p-4 sm:p-5 space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">1 · Add labelled clips</h2>
        <label className="ml-auto flex items-center gap-2 text-sm">
          New files are
          <select value={defaultLabel} onChange={(e) => setDefaultLabel(e.target.value as Label)} className="rounded-lg border border-border bg-bg px-2 py-1">
            <option value="real">Real</option>
            <option value="fake">Fake</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
      </div>
      <div
        {...getRootProps()}
        className={cn(
          "cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors",
          isDragActive ? "border-accent bg-accent/5" : "border-border hover:border-accent/60",
        )}
      >
        <input {...getInputProps()} aria-label="Choose video files" />
        <Upload className="mx-auto size-7 text-muted" aria-hidden />
        <p className="mt-2 font-medium">Drop several videos here, or click to choose</p>
        <p className="text-xs text-muted">Each clip is tracked once and scored with POS, CHROM and GREEN. Videos are deleted after analysis.</p>
      </div>
      {rejectMsg && <p className="text-sm text-manip">{rejectMsg}</p>}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-1.5 pr-3 font-medium">File</th>
                <th className="py-1.5 pr-3 font-medium">Truth</th>
                <th className="py-1.5 pr-3 font-medium">True BPM (optional)</th>
                <th className="py-1.5 pr-3 font-medium">Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.key} className="border-t border-border">
                  <td className="py-1.5 pr-3 max-w-56 truncate" title={it.file.name}>{it.file.name}</td>
                  <td className="py-1.5 pr-3">
                    <select
                      value={it.label}
                      disabled={it.status !== "waiting" && it.status !== "error"}
                      onChange={(e) => patch(it.key, { label: e.target.value as Label })}
                      className="rounded-md border border-border bg-bg px-1.5 py-0.5"
                    >
                      <option value="real">Real</option>
                      <option value="fake">Fake</option>
                      <option value="unknown">Unknown</option>
                    </select>
                  </td>
                  <td className="py-1.5 pr-3">
                    <input
                      inputMode="decimal"
                      placeholder="e.g. 74"
                      value={it.trueBpm}
                      disabled={it.status !== "waiting" && it.status !== "error"}
                      onChange={(e) => patch(it.key, { trueBpm: e.target.value })}
                      className="w-20 rounded-md border border-border bg-bg px-1.5 py-0.5"
                    />
                  </td>
                  <td className="py-1.5 pr-3">
                    {it.status === "waiting" && <span className="text-muted">Waiting</span>}
                    {it.status === "uploading" && <span className="flex items-center gap-1"><LoaderCircle className="size-3.5 animate-spin" />Uploading</span>}
                    {it.status === "running" && (
                      <span className="flex items-center gap-1"><LoaderCircle className="size-3.5 animate-spin" />{it.stage} {Math.round((it.progress ?? 0) * 100)}%</span>
                    )}
                    {it.status === "error" && <span className="text-manip">{it.error}</span>}
                  </td>
                  <td className="py-1.5 text-right">
                    {!running && (
                      <button aria-label={`Remove ${it.file.name}`} onClick={() => setItems((p) => p.filter((x) => x.key !== it.key))} className="text-muted hover:text-fg">
                        <Trash2 className="size-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button className="btn-primary" disabled={running || pending === 0} onClick={runAll}>
        {running ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
        {running ? "Analysing…" : `Analyse ${pending} clip${pending === 1 ? "" : "s"}`}
      </button>
    </section>
  );
}

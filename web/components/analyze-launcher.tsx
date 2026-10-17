"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Film, FlaskConical, LoaderCircle, Upload } from "lucide-react";
import { analyzeSample, listSamples, listScenarios, uploadVideo } from "@/lib/api";
import { METHOD_HELP, VERDICT_TEXT } from "@/lib/copy";
import type { Method } from "@/lib/schemas";
import { cn } from "@/lib/utils";

const MAX_BYTES = 50 * 1024 * 1024;
type Tab = "upload" | "samples" | "synthetic";

export function AnalyzeLauncher() {
  const [tab, setTab] = useState<Tab>("upload");
  const [method, setMethod] = useState<Method>("POS");
  const tabs: { id: Tab; label: string; icon: typeof Upload }[] = [
    { id: "upload", label: "Upload video", icon: Upload },
    { id: "samples", label: "Demo samples", icon: Film },
    { id: "synthetic", label: "Synthetic test", icon: FlaskConical },
  ];
  return (
    <div className="card overflow-hidden">
      <div role="tablist" aria-label="Choose input" className="grid grid-cols-3 border-b border-border">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              "flex items-center justify-center gap-2 px-2 py-3 text-sm font-medium border-b-2 -mb-px",
              tab === id ? "border-accent text-fg bg-bg/40" : "border-transparent text-muted hover:text-fg",
            )}
          >
            <Icon className="size-4" aria-hidden />
            <span className="hidden sm:inline">{label}</span>
            <span className="sm:hidden">{label.split(" ")[0]}</span>
          </button>
        ))}
      </div>
      <div className="p-4 sm:p-6" role="tabpanel">
        {tab === "upload" && <UploadPanel method={method} />}
        {tab === "samples" && <SamplesPanel method={method} />}
        {tab === "synthetic" && <SyntheticPanel method={method} />}
        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-border pt-4 text-sm">
          <label htmlFor="method" className="font-medium">Pulse method</label>
          <select
            id="method"
            value={method}
            onChange={(e) => setMethod(e.target.value as Method)}
            className="rounded-lg border border-border bg-bg px-2 py-1.5"
          >
            <option value="POS">POS (default)</option>
            <option value="GREEN">GREEN</option>
            <option value="CHROM">CHROM</option>
          </select>
          <span className="text-muted">{METHOD_HELP[method]}</span>
        </div>
      </div>
    </div>
  );
}

function UploadPanel({ method }: { method: Method }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [consent, setConsent] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const onDrop = useCallback((accepted: File[], rejected: FileRejection[]) => {
    setLocalError(null);
    if (rejected.length) {
      const code = rejected[0].errors[0]?.code;
      setLocalError(code === "file-too-large" ? "The file is larger than 50 MB. Please trim or compress it." : "Please choose a video file.");
      return;
    }
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    setDuration(null);
    const url = URL.createObjectURL(f);
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => {
      setDuration(Number.isFinite(v.duration) ? v.duration : null);
      URL.revokeObjectURL(url);
    };
    v.onerror = () => URL.revokeObjectURL(url);
    v.src = url;
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "video/*": [".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v"] },
    maxFiles: 1,
    maxSize: MAX_BYTES,
  });

  const upload = useMutation({
    mutationFn: () => uploadVideo(file!, method),
    onSuccess: ({ job_id }) => router.push(`/analyze/${job_id}`),
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors",
          isDragActive ? "border-accent bg-accent/5" : "border-border hover:border-accent/60",
        )}
      >
        <input {...getInputProps()} aria-label="Choose a video file" />
        <Upload className="mx-auto size-8 text-muted" aria-hidden />
        {file ? (
          <p className="mt-2 font-medium break-all">
            {file.name}{" "}
            <span className="text-muted font-normal">
              · {(file.size / 1e6).toFixed(1)} MB{duration != null && ` · ${duration.toFixed(1)} s`}
            </span>
          </p>
        ) : (
          <p className="mt-2 font-medium">Drop a video here, or click to choose</p>
        )}
        <p className="mt-1 text-xs text-muted">
          MP4, MOV, WebM or AVI · up to 50 MB · one clearly visible face · 10–30 s works best
        </p>
      </div>
      {duration != null && duration < 6 && (
        <p className="text-sm text-manip">
          This clip is only {duration.toFixed(1)} s long. At least 6 s is needed, so the result will be “{VERDICT_TEXT.unable}”.
        </p>
      )}
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 accent-[var(--accent)]" />
        <span>
          I have the right to analyse this video. I understand it is processed only to produce this result and then
          deleted, and that the result is a warning sign, not proof.
        </span>
      </label>
      {(localError || upload.error) && (
        <p className="text-sm text-manip" role="alert">{localError ?? upload.error?.message}</p>
      )}
      <button className="btn-primary w-full sm:w-auto" disabled={!file || !consent || upload.isPending} onClick={() => upload.mutate()}>
        {upload.isPending ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <ArrowRight className="size-4" aria-hidden />}
        Analyse video
      </button>
    </div>
  );
}

function SamplesPanel({ method }: { method: Method }) {
  const router = useRouter();
  const samples = useQuery({ queryKey: ["samples"], queryFn: listSamples });
  const run = useMutation({
    mutationFn: (id: string) => analyzeSample(id, method),
    onSuccess: ({ job_id }) => router.push(`/analyze/${job_id}`),
  });
  if (samples.isLoading) return <p className="text-sm text-muted">Loading samples…</p>;
  if (samples.error) return <p className="text-sm text-manip">{samples.error.message}</p>;
  const tag = { real: "Real reference", fake: "Demo fake", other: "Quality test" } as const;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">Pre-loaded clips from openly licensed datasets or recorded with consent.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {samples.data?.map((s) => (
          <div key={s.id} className="flex flex-col rounded-xl border border-border p-4">
            <span
              className={cn(
                "self-start rounded-full px-2 py-0.5 text-xs font-medium",
                s.kind === "real" ? "bg-real/15 text-real" : s.kind === "fake" ? "bg-manip/15 text-manip" : "bg-unable/15 text-unable",
              )}
            >
              {tag[s.kind]}
            </span>
            <p className="mt-2 font-semibold">{s.title}</p>
            <p className="mt-1 flex-1 text-xs text-muted">{s.description}</p>
            <p className="mt-2 text-[11px] text-muted">Licence: {s.licence}</p>
            <button
              className="btn-secondary mt-3"
              disabled={!s.available || run.isPending}
              onClick={() => run.mutate(s.id)}
              title={s.available ? undefined : "Clip file not installed on the server"}
            >
              {run.isPending && run.variables === s.id ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : null}
              {s.available ? "Analyse" : "Not installed"}
            </button>
          </div>
        ))}
      </div>
      {run.error && <p className="text-sm text-manip" role="alert">{run.error.message}</p>}
    </div>
  );
}

function SyntheticPanel({ method }: { method: Method }) {
  const router = useRouter();
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: listScenarios });
  const [seed, setSeed] = useState(0);
  if (scenarios.isLoading) return <p className="text-sm text-muted">Loading scenarios…</p>;
  if (scenarios.error) return <p className="text-sm text-manip">{scenarios.error.message}</p>;
  const dot = { real: "bg-real", manip: "bg-manip", unable: "bg-unable" } as const;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        Computer-generated skin-colour signals with a known answer. They test the maths with no video and no real person.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {scenarios.data?.map((s) => (
          <button
            key={s.id}
            onClick={() => router.push(`/analyze/synthetic-${s.id}?method=${method}&seed=${seed}`)}
            className="group rounded-xl border border-border p-3 text-left hover:border-accent/60"
          >
            <span className="flex items-center gap-2 font-medium">
              <span className={cn("size-2.5 rounded-full", dot[s.expected])} aria-hidden />
              {s.title}
              <ArrowRight className="ml-auto size-4 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
            </span>
            <span className="mt-1 block text-xs text-muted">{s.description}</span>
            <span className="mt-1 block text-[11px] text-muted">Expected: {VERDICT_TEXT[s.expected]}</span>
          </button>
        ))}
      </div>
      <label className="flex items-center gap-2 text-sm">
        Random seed
        <input
          type="number"
          min={0}
          max={999}
          value={seed}
          onChange={(e) => setSeed(Math.max(0, Number(e.target.value) || 0))}
          className="w-20 rounded-lg border border-border bg-bg px-2 py-1"
        />
      </label>
    </div>
  );
}

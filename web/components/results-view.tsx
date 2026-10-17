"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CircleAlert, LoaderCircle, RotateCcw } from "lucide-react";
import { getJob, getSynthetic } from "@/lib/api";
import { Method, type AnalysisResult } from "@/lib/schemas";
import { cn } from "@/lib/utils";
import { CoherenceTimeline, PulseWaveChart, SpectrumChart } from "./charts";
import { DisclaimerBanner } from "./disclaimer-banner";
import { LimitationsPanel } from "./limitations-panel";
import { MetricCards } from "./metric-cards";
import { ReasonsList } from "./reasons-list";
import { RoiOverlay } from "./roi-overlay";
import { VerdictBadge } from "./verdict-badge";

const STAGES = ["Reading video", "Tracking face", "Extracting pulse", "Comparing regions"];

export function ResultsView() {
  const { jobId } = useParams<{ jobId: string }>();
  const search = useSearchParams();
  const method = Method.catch("POS").parse(search.get("method") ?? "POS");
  const seed = Number(search.get("seed") ?? 0) || 0;
  const synthetic = jobId.startsWith("synthetic-") ? jobId.slice("synthetic-".length) : null;

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    enabled: !synthetic,
    refetchInterval: (q) => (q.state.data && ["done", "error"].includes(q.state.data.status) ? false : 800),
    retry: 1,
  });
  const syn = useQuery({
    queryKey: ["synthetic", synthetic, method, seed],
    queryFn: () => getSynthetic(synthetic!, method, seed),
    enabled: !!synthetic,
    retry: 0,
  });

  const error = synthetic ? syn.error?.message : job.error?.message ?? (job.data?.status === "error" ? job.data.error : null);
  if (error) return <ErrorState message={error} />;

  const result = synthetic ? syn.data : job.data?.result;
  if (!result) {
    return <Progress progress={synthetic ? 0.5 : job.data?.progress ?? 0} stage={synthetic ? "Generating signals" : job.data?.stage ?? "Queued"} />;
  }
  return <Results result={result} />;
}

function Results({ result }: { result: AnalysisResult }) {
  const [tab, setTab] = useState<"waves" | "spectrum" | "time">("waves");
  const src = result.source;
  return (
    <div className="space-y-5">
      <DisclaimerBanner />
      {src && (
        <p className="text-sm text-muted">
          {src.type === "synthetic" ? "Synthetic scenario" : src.type === "sample" ? "Demo sample" : "Uploaded video"}:{" "}
          <span className="font-medium text-fg">{String(src.name ?? "")}</span>
          {src.type === "synthetic" && src.true_bpm != null && <> · true heart rate {Number(src.true_bpm).toFixed(0)} bpm</>}
        </p>
      )}
      <VerdictBadge result={result} />
      <MetricCards result={result} />
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <RoiOverlay result={result} />
        </div>
        <div className="lg:col-span-3">
          <ReasonsList result={result} />
        </div>
      </div>
      <section className="card p-4">
        <div role="tablist" aria-label="Evidence charts" className="mb-4 flex gap-1 overflow-x-auto border-b border-border">
          {(
            [
              ["waves", "Pulse waves"],
              ["spectrum", "Spectrum"],
              ["time", "Coherence over time"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={cn(
                "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium",
                tab === k ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          {tab === "waves" && <PulseWaveChart result={result} />}
          {tab === "spectrum" && <SpectrumChart result={result} />}
          {tab === "time" && <CoherenceTimeline result={result} />}
        </div>
      </section>
      <LimitationsPanel />
      <div className="flex justify-center pt-2">
        <Link href="/" className="btn-primary">
          <RotateCcw className="size-4" aria-hidden /> Analyse another video
        </Link>
      </div>
    </div>
  );
}

function Progress({ progress, stage }: { progress: number; stage: string }) {
  const active = Math.max(0, STAGES.findIndex((s) => stage.startsWith(s)));
  return (
    <div className="space-y-5">
      <DisclaimerBanner />
      <div className="card p-6 sm:p-8" aria-busy="true">
        <div className="flex items-center gap-3">
          <LoaderCircle className="size-6 animate-spin text-accent" aria-hidden />
          <h1 className="text-xl font-semibold">Analysing… {stage}</h1>
        </div>
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-border" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${Math.max(4, progress * 100)}%` }} />
        </div>
        <ol className="mt-5 grid gap-2 text-sm sm:grid-cols-4">
          {STAGES.map((s, i) => (
            <li key={s} className={cn("flex items-center gap-2", i <= active ? "text-fg" : "text-muted")}>
              <span className={cn("size-2 rounded-full", i < active ? "bg-real" : i === active ? "bg-accent animate-pulse" : "bg-border")} />
              {s}
            </li>
          ))}
        </ol>
      </div>
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="card h-24 animate-pulse" />
        ))}
      </div>
      <div className="card h-72 animate-pulse" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="card mx-auto max-w-xl p-6 text-center">
      <CircleAlert className="mx-auto size-10 text-manip" aria-hidden />
      <h1 className="mt-3 text-xl font-semibold">We couldn&apos;t analyse this</h1>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <Link href="/" className="btn-primary mt-5 inline-flex">
        <RotateCcw className="size-4" aria-hidden /> Try again
      </Link>
    </div>
  );
}

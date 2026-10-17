import { HelpCircle, ShieldCheck, TriangleAlert } from "lucide-react";
import { VERDICT_SUMMARY, VERDICT_SUMMARY_BORDERLINE, VERDICT_TEXT } from "@/lib/copy";
import type { AnalysisResult } from "@/lib/schemas";
import { cn } from "@/lib/utils";

const STYLE = {
  real: { icon: ShieldCheck, ring: "border-real/40 bg-real/10", text: "text-real", dot: "🟢" },
  manip: { icon: TriangleAlert, ring: "border-manip/40 bg-manip/10", text: "text-manip", dot: "🟡" },
  unable: { icon: HelpCircle, ring: "border-unable/40 bg-unable/10", text: "text-unable", dot: "⚪" },
} as const;

export function VerdictBadge({ result }: { result: AnalysisResult }) {
  const key = result.verdict_key;
  const s = STYLE[key];
  const Icon = s.icon;
  return (
    <section
      role="status"
      aria-live="polite"
      className={cn("rounded-2xl border-2 p-5 sm:p-6 flex flex-col sm:flex-row gap-4 sm:items-center", s.ring)}
    >
      <Icon className={cn("size-12 shrink-0", s.text)} aria-hidden />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Result</p>
        <h1 className={cn("text-2xl sm:text-3xl font-bold leading-tight", s.text)}>
          <span aria-hidden className="mr-2">{s.dot}</span>
          {VERDICT_TEXT[key]}
        </h1>
        <p className="mt-1 text-sm text-fg/80">
          {key === "real" && result.confidence === "Low" ? VERDICT_SUMMARY_BORDERLINE : VERDICT_SUMMARY[key]}
        </p>
      </div>
      <dl className="flex sm:flex-col gap-x-6 gap-y-1 text-sm shrink-0">
        <div className="flex gap-2">
          <dt className="text-muted">Risk level</dt>
          <dd className="font-semibold">{result.risk_level}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-muted">Confidence</dt>
          <dd className="font-semibold">{result.confidence}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-muted">Method</dt>
          <dd className="font-semibold">{result.method}</dd>
        </div>
      </dl>
    </section>
  );
}

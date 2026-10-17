import { CircleCheck, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import type { AnalysisResult } from "@/lib/schemas";

export function ReasonsList({ result }: { result: AnalysisResult }) {
  const iconFor = (sev: string, key: string) => {
    if (sev === "block") return <OctagonAlert className="size-5 text-unable shrink-0" aria-label="blocking issue" />;
    if (sev === "warn") return <TriangleAlert className="size-5 text-manip shrink-0" aria-label="warning" />;
    if (key === "real") return <CircleCheck className="size-5 text-real shrink-0" aria-label="ok" />;
    return <Info className="size-5 text-muted shrink-0" aria-label="note" />;
  };
  return (
    <div className="card p-4 h-full">
      <h2 className="font-semibold mb-3">Why this result</h2>
      <ul className="space-y-3">
        {result.reasons.map((r, i) => (
          <li key={r.code + i} className="flex gap-3 text-sm leading-relaxed">
            {iconFor(r.severity, r.code === "coherent" ? "real" : "")}
            <span className={r.code === "caveat_global_hr" ? "text-muted" : ""}>{r.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

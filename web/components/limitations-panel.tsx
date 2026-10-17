import { ChevronDown, Eye } from "lucide-react";
import { LIMITATIONS, LIMITATIONS_TITLE } from "@/lib/copy";

export function LimitationsPanel({ defaultOpen = false }: { defaultOpen?: boolean }) {
  return (
    <details className="card group" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center gap-2 p-4 font-semibold [&::-webkit-details-marker]:hidden">
        <Eye className="size-5 text-accent" aria-hidden />
        {LIMITATIONS_TITLE}
        <span className="ml-1 text-sm font-normal text-muted">What SatyaSpandan cannot reliably detect</span>
        <ChevronDown className="ml-auto size-5 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <ol className="space-y-3 border-t border-border p-4 pt-3">
        {LIMITATIONS.map((l, i) => (
          <li key={l.title} className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent/10 text-xs font-bold text-accent">
              {i + 1}
            </span>
            <div>
              <p className="font-medium">{l.title}</p>
              <p className="text-sm text-muted">{l.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}

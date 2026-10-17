import { ShieldAlert } from "lucide-react";
import { DISCLAIMER } from "@/lib/copy";

/** Mandatory, permanent, not dismissible. */
export function DisclaimerBanner() {
  return (
    <div
      role="note"
      className="sticky top-14 z-30 flex gap-3 rounded-xl border border-manip/40 bg-[color-mix(in_oklab,var(--manip)_12%,var(--bg))] p-3 text-sm backdrop-blur"
    >
      <ShieldAlert className="size-5 shrink-0 text-manip mt-0.5" aria-hidden />
      <p className="font-medium italic">{DISCLAIMER}</p>
    </div>
  );
}

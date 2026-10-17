import Link from "next/link";
import { Activity, ScanFace, Scale } from "lucide-react";
import { AnalyzeLauncher } from "@/components/analyze-launcher";
import { LimitationsPanel } from "@/components/limitations-panel";
import { VERDICT_TEXT } from "@/lib/copy";

const STEPS = [
  {
    icon: ScanFace,
    title: "Find the skin",
    body: "Face landmarks mark the forehead and both cheeks. We average their colour in every frame.",
  },
  {
    icon: Activity,
    title: "Read the pulse",
    body: "Each heartbeat changes skin colour very slightly. Filtering reveals a pulse wave for each region.",
  },
  {
    icon: Scale,
    title: "Compare the regions",
    body: "One heart feeds the whole face, so real regions pulse together. Face-swaps often break that sync.",
  },
];

export default function Home() {
  return (
    <div className="space-y-10">
      <section className="grid items-center gap-8 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-accent">Is this video real?</p>
          <h1 className="mt-2 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            Check the <span className="text-accent">pulse</span> before you share.
          </h1>
          <p className="mt-4 max-w-xl text-lg text-muted">
            SatyaSpandan looks for the faint heartbeat in a face on video and checks whether every part of the face
            pulses in sync, as a real face does. You get an explained warning sign, never a final judgement.
          </p>
          <ul className="mt-5 flex flex-wrap gap-2 text-sm">
            <li className="rounded-full bg-real/12 px-3 py-1 font-medium text-real">🟢 {VERDICT_TEXT.real}</li>
            <li className="rounded-full bg-manip/12 px-3 py-1 font-medium text-manip">🟡 {VERDICT_TEXT.manip}</li>
            <li className="rounded-full bg-unable/12 px-3 py-1 font-medium text-unable">⚪ {VERDICT_TEXT.unable}</li>
          </ul>
        </div>
        <svg viewBox="0 0 600 160" className="w-full" role="img" aria-label="Three pulse waves rising and falling together">
          {[
            { y: 40, c: "var(--roi-forehead)" },
            { y: 80, c: "var(--roi-left)" },
            { y: 120, c: "var(--roi-right)" },
          ].map(({ y, c }) => (
            <path
              key={y}
              className="ecg-line"
              d={`M0 ${y} h70 l15 -22 l18 44 l14 -30 l10 8 h83 l15 -22 l18 44 l14 -30 l10 8 h83 l15 -22 l18 44 l14 -30 l10 8 h83 l15 -22 l18 44 l14 -30 l10 8 h40`}
              fill="none"
              stroke={c}
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
        </svg>
      </section>

      <AnalyzeLauncher />

      <section>
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-xl font-semibold">How it works</h2>
          <Link href="/how-it-works" className="text-sm text-accent hover:underline">The science →</Link>
        </div>
        <ol className="mt-4 grid gap-4 sm:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, body }, i) => (
            <li key={title} className="card p-5">
              <div className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded-full bg-accent/10 text-sm font-bold text-accent">{i + 1}</span>
                <Icon className="size-5 text-muted" aria-hidden />
              </div>
              <p className="mt-3 font-semibold">{title}</p>
              <p className="mt-1 text-sm text-muted">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <LimitationsPanel />
    </div>
  );
}

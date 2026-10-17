import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/disclaimer-banner";
import { LimitationsPanel } from "@/components/limitations-panel";

export const metadata: Metadata = { title: "Limitations · SatyaSpandan" };

const PRINCIPLES = [
  ["Three cautious outcomes", "We say “Possible manipulation detected”, never “fake”. When the signal is poor we say “Unable to assess” instead of guessing."],
  ["Biased against false accusations", "The decision threshold is calibrated so that at least 90% of real test clips pass. Missing some fakes is preferred to accusing real people."],
  ["Explainable by design", "Every verdict shows the regions analysed, the pulse waves and plain-language reasons, so a person can check the evidence."],
  ["Privacy", "Uploaded videos are analysed and then deleted. There is no face recognition and no identity inference, and results are kept in memory for 15 minutes only."],
  ["Consented and open data", "Demo clips come from openly licensed research datasets or from team members who gave written consent."],
];

export default function LimitationsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-3xl font-bold">Limitations &amp; responsible design</h1>
      <DisclaimerBanner />
      <LimitationsPanel defaultOpen />
      <section className="card p-5">
        <h2 className="text-lg font-semibold">How we try to stay fair and safe</h2>
        <dl className="mt-3 space-y-3">
          {PRINCIPLES.map(([t, b]) => (
            <div key={t}>
              <dt className="font-medium">{t}</dt>
              <dd className="text-sm text-muted">{b}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}

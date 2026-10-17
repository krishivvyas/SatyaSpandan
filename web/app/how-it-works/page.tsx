import type { Metadata } from "next";

export const metadata: Metadata = { title: "How it works · SatyaSpandan" };

const STAGES = [
  ["1. Read the video", "OpenCV reads each frame and the video's true frame rate. Every heart-rate number depends on it."],
  ["2. Track the face", "MediaPipe Face Landmarker places 478 points on the face. From them we outline the forehead, the left cheek and the right cheek, plus two background patches that measure lighting and compression noise."],
  ["3. Extract the pulse", "For each region we average the red, green and blue values in every frame. The POS method (Wang et al., 2017) turns those three colour traces into one pulse signal that resists skin-tone and lighting changes. CHROM and GREEN are also available."],
  ["4. Clean the signal", "Slow drift is removed, then a 5th-order Butterworth band-pass filter keeps only 0.7–3.0 Hz (42–180 beats per minute), following Seibold et al. (2025). Zero-phase filtering keeps the timing between regions true."],
  ["5. Find the heartbeat", "A Fourier transform shows which frequencies are present. The background spectrum is subtracted from the face spectrum, and the strongest remaining peak is the heart rate. Signal quality (SNR) is the power at the heartbeat versus everything else."],
  ["6. Compare the regions", "In every 10-second window we measure how well each pair of regions agrees: correlation, spectral coherence at the heart rate, timing offset, and whether they show the same rate. These combine into the Spatial Coherence Score, following FakeCatcher (Ciftci et al., 2020)."],
  ["7. Decide carefully", "If the face is missing, too small, moving too much, the clip is too short or the signal is too weak, the answer is “Unable to assess”. Otherwise a coherence score above the calibrated threshold gives “No strong signs detected”, and a score below it gives “Possible manipulation detected”."],
];

const REFS = [
  "Ciftci, Demir & Yin. FakeCatcher: Detection of Synthetic Portrait Videos using Biological Signals. IEEE TPAMI, 2020.",
  "Seibold et al. High-quality deepfakes have a heart! Frontiers in Imaging, 2025.",
  "Wang, den Brinker, Stuijk & de Haan. Algorithmic principles of remote PPG (POS). IEEE TBME, 2017.",
  "de Haan & Jeanne. Robust pulse rate from chrominance-based rPPG (CHROM). IEEE TBME, 2013.",
  "Verkruysse, Svaasand & Nelson. Remote plethysmographic imaging using ambient light. Optics Express, 2008.",
  "Bobbia et al. Unsupervised skin tissue segmentation for remote photoplethysmography (UBFC-rPPG). Pattern Recognition Letters, 2017.",
  "Liu et al. rPPG-Toolbox: Deep Remote PPG Toolbox. NeurIPS, 2023.",
];

export default function HowItWorks() {
  return (
    <article className="mx-auto max-w-3xl space-y-8">
      <header>
        <h1 className="text-3xl font-bold">How SatyaSpandan works</h1>
        <p className="mt-3 text-lg text-muted">
          Every heartbeat pushes blood into the skin, which changes its colour very slightly. A normal camera records
          it. This is remote photoplethysmography (rPPG).
        </p>
      </header>

      <section className="card border-accent/30 p-5">
        <h2 className="text-lg font-semibold">Why not just check for a heartbeat?</h2>
        <p className="mt-2 text-sm leading-relaxed">
          Research in 2025 showed that high-quality face-swaps can <strong>copy the heart rate</strong> of the real video
          they are made from. Finding a pulse therefore proves nothing. SatyaSpandan asks a harder question:{" "}
          <strong>do the forehead and both cheeks pulse together?</strong> One heart feeds the whole face, so in a real
          video they do. Face-swaps warp, blend and regenerate the face region by region, which often breaks that
          agreement.
        </p>
      </section>

      <ol className="space-y-4">
        {STAGES.map(([t, b]) => (
          <li key={t} className="card p-5">
            <h3 className="font-semibold">{t}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted">{b}</p>
          </li>
        ))}
      </ol>

      <section>
        <h2 className="text-lg font-semibold">References</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
          {REFS.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </section>
    </article>
  );
}

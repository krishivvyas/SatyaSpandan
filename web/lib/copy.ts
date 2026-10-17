// Single source for all mandated and user-facing wording (implementation.md §8).
import type { VerdictKey } from "./schemas";

export const APP_NAME = "SatyaSpandan";
export const TAGLINE = "The Pulse of Truth";

export const VERDICT_TEXT: Record<VerdictKey, string> = {
  real: "No strong signs detected",
  manip: "Possible manipulation detected",
  unable: "Unable to assess",
};

export const VERDICT_SUMMARY: Record<VerdictKey, string> = {
  real: "The skin regions of this face pulse together the way a real face does. This is not proof that the video is genuine.",
  manip: "The skin regions of this face do not pulse together the way a real face does. Treat this video with caution before trusting or sharing it.",
  unable: "The video does not carry a clear enough pulse signal for a fair judgement. We prefer to say so rather than guess.",
};

export const VERDICT_SUMMARY_BORDERLINE =
  "The skin regions neither clearly pulse together nor clearly disagree. This borderline result is not evidence either way. A longer, steadier, well-lit clip will give a clearer answer.";

export const DISCLAIMER =
  "Disclaimer: Automated AI forensics results are probabilistic warning signs and can be wrong. This output should not be treated as final proof and must never be used to definitively label a real person as a liar.";

export const LIMITATIONS_TITLE = "System Limitations & Transparency";

export const LIMITATIONS: { title: string; body: string }[] = [
  {
    title: "Heavily compressed or pixelated videos",
    body: "Multi-forwarded WhatsApp clips and similar low-quality videos lose the tiny colour changes that rPPG relies on. Compression artefacts destroy the signal, and SatyaSpandan will usually answer “Unable to assess”.",
  },
  {
    title: "Camera shake, fast head movement, or changing light",
    body: "Extreme camera shake, rapid head movement or severe lighting changes swamp the pulse signal.",
  },
  {
    title: "Ultra-high-quality full-head synthesis",
    body: "Full-head synthesis or style-transferred fakes that preserve spatial pulse coherence across the entire face can pass as “No strong signs detected”.",
  },
  {
    title: "A heartbeat is not proof of authenticity",
    body: "Modern face-swaps can inherit the heart rate of the source video (Seibold et al., 2025). That is why SatyaSpandan compares regions of the face instead of only checking for a pulse.",
  },
  {
    title: "Skin tone and lighting",
    body: "rPPG signals are weaker on darker skin tones and in low light. Such clips are more likely to return “Unable to assess”, which we prefer to a wrong verdict.",
  },
  {
    title: "Face only",
    body: "This tool analyses facial skin only. It does not check the audio, lip-sync, or edits elsewhere in the frame.",
  },
];

export const METRIC_HELP = {
  bpm: "Estimated heart rate from the whole face, after removing background noise. A 10-second window resolves about 6 bpm.",
  coherence: "How closely the forehead, left cheek and right cheek pulse together (correlation, spectral coherence and rate agreement). Real faces score high.",
  snr: "Signal quality: power at the heart-rate frequency versus everything else in the 42–180 bpm band, in decibels.",
  tracking: "Share of frames in which a face was found and tracked.",
};

export const ROI_META = {
  forehead: { label: "Forehead", color: "var(--roi-forehead)" },
  left: { label: "Left cheek", color: "var(--roi-left)" },
  right: { label: "Right cheek", color: "var(--roi-right)" },
  background: { label: "Background", color: "var(--roi-bg)" },
} as const;

export const METHOD_HELP: Record<string, string> = {
  POS: "POS (Wang 2017): default. Designed to resist skin-tone and lighting changes; needs a well-lit clip.",
  CHROM: "CHROM (de Haan 2013): chrominance-based, good under white light.",
  GREEN: "GREEN (Verkruysse 2008): green channel only. Held up better on noisy phone clips in our tests, but sensitive to changing light.",
};

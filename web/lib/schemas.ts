// Mirrors backend/schemas.py exactly. Every API response is parsed with these.
import { z } from "zod";

export const VerdictKey = z.enum(["real", "manip", "unable"]);
export type VerdictKey = z.infer<typeof VerdictKey>;

export const Method = z.enum(["POS", "CHROM", "GREEN"]);
export type Method = z.infer<typeof Method>;

export const Reason = z.object({
  code: z.string(),
  severity: z.enum(["info", "warn", "block"]),
  text: z.string(),
});
export type Reason = z.infer<typeof Reason>;

const num = z.number().nullable();

export const Window = z.object({
  t_start: z.number(),
  t_end: z.number(),
  scs: num,
  bpm: num,
  r_lr: num,
  r_lm: num,
  r_rm: num,
  msc: num,
  agree: num,
  bpm_forehead: num,
  bpm_left: num,
  bpm_right: num,
});
export type Window = z.infer<typeof Window>;

export const AnalysisResult = z.object({
  verdict: z.string(),
  verdict_key: VerdictKey,
  risk_level: z.enum(["Low", "Medium", "High", "—"]),
  confidence: z.enum(["High", "Medium", "Low", "—"]),
  bpm: num,
  coherence_score: num,
  snr_db: num,
  reasons: z.array(Reason),
  quality: z.record(z.string(), num),
  fps: num,
  method: Method,
  threshold: z.number(),
  t: z.array(z.number()),
  signals: z.record(z.string(), z.array(z.number())),
  psd: z.record(z.string(), z.array(z.number())),
  windows: z.array(Window),
  pairs: z.record(z.string(), z.record(z.string(), num)),
  overlay_jpeg_b64: z.string().nullable(),
  source: z.record(z.string(), z.any()).nullable().optional(),
});
export type AnalysisResult = z.infer<typeof AnalysisResult>;

export const JobCreated = z.object({ job_id: z.string() });

export const JobStatus = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running", "done", "error"]),
  progress: z.number(),
  stage: z.string(),
  result: AnalysisResult.nullable().optional(),
  error: z.string().nullable().optional(),
});
export type JobStatus = z.infer<typeof JobStatus>;

export const Sample = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  licence: z.string(),
  kind: z.enum(["real", "fake", "other"]),
  available: z.boolean(),
});
export type Sample = z.infer<typeof Sample>;

export const Scenario = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  expected: VerdictKey,
});
export type Scenario = z.infer<typeof Scenario>;

// ---- Accuracy testing (/evaluate) ----

export const CompactResult = AnalysisResult.omit({ t: true, signals: true, psd: true, overlay_jpeg_b64: true });
export type CompactResult = z.infer<typeof CompactResult>;

export const Label = z.enum(["real", "fake", "unknown"]);
export type Label = z.infer<typeof Label>;

export const EvalResult = z.object({
  name: z.string().nullable(),
  label: Label,
  true_bpm: z.number().nullable(),
  methods: z.record(z.string(), CompactResult),
  thumb_jpeg_b64: z.string().nullable(),
});
export type EvalResult = z.infer<typeof EvalResult>;

export const EvalJob = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running", "done", "error"]),
  progress: z.number(),
  stage: z.string(),
  result: EvalResult.nullable().optional(),
  error: z.string().nullable().optional(),
});

export const Thresholds = z.object({
  threshold: z.number(),
  grey_margin: z.number(),
  min_frac_coherent: z.number(),
  min_snr_db: z.number(),
  min_snr_flag_db: z.number(),
  max_bg_ratio: z.number(),
  max_bg_corr: z.number(),
  min_bg_amp_ratio: z.number(),
  min_duration_s: z.number(),
  min_face_ratio: z.number(),
  min_face_px: z.number(),
  max_median_motion: z.number(),
  max_fast_motion_frac: z.number(),
});
export type Thresholds = z.infer<typeof Thresholds>;

export const CalibrationInfo = z.object({
  defaults: Thresholds,
  current: Thresholds.partial(),
});

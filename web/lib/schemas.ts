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
  scs: z.number(),
  bpm: num,
  r_lr: z.number(),
  r_lm: z.number(),
  r_rm: z.number(),
  msc: z.number(),
  agree: z.number(),
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

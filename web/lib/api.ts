import { z } from "zod";
import { AnalysisResult, CalibrationInfo, EvalJob, JobCreated, JobStatus, Method, Sample, Scenario, type Label, type Thresholds } from "./schemas";

// Same-origin in the browser: next.config.ts rewrites /api/* to the FastAPI server.
// Uploads can go straight to the API (NEXT_PUBLIC_UPLOAD_BASE) to avoid proxy body limits.
const API = "/api";
const UPLOAD_BASE = process.env.NEXT_PUBLIC_UPLOAD_BASE ?? API;

async function request<T>(url: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("Cannot reach the SatyaSpandan analysis server. Is the backend running on port 8000?");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      body && typeof body.detail === "string"
        ? body.detail
        : res.status >= 500
          ? `The analysis server did not answer properly (error ${res.status}). Check that the backend window is still running, then try again.`
          : `Request failed (${res.status}).`;
    throw new Error(detail);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    console.error(parsed.error);
    throw new Error("The server sent a response this page does not understand. Frontend and backend versions may differ.");
  }
  return parsed.data;
}

export function uploadVideo(file: File, method: Method) {
  const form = new FormData();
  form.append("file", file);
  form.append("method", method);
  return request(`${UPLOAD_BASE}/analyze`, JobCreated, { method: "POST", body: form });
}

export function analyzeSample(id: string, method: Method) {
  return request(`${API}/analyze/sample/${encodeURIComponent(id)}?method=${method}`, JobCreated, { method: "POST" });
}

export function getJob(jobId: string) {
  return request(`${API}/jobs/${encodeURIComponent(jobId)}`, JobStatus, { cache: "no-store" });
}

export function getSynthetic(scenario: string, method: Method, seed = 0) {
  return request(
    `${API}/synthetic/${encodeURIComponent(scenario)}?method=${method}&seed=${seed}`,
    AnalysisResult,
    { cache: "no-store" },
  );
}

export function listSamples() {
  return request(`${API}/samples`, z.array(Sample));
}

export function listScenarios() {
  return request(`${API}/scenarios`, z.array(Scenario));
}

// ---- Accuracy testing ----

export function evaluateUpload(file: File, label: Label, trueBpm: number | null) {
  const form = new FormData();
  form.append("file", file);
  form.append("label", label);
  if (trueBpm != null) form.append("true_bpm", String(trueBpm));
  return request(`${UPLOAD_BASE}/evaluate`, JobCreated, { method: "POST", body: form });
}

export function getEvalJob(jobId: string) {
  return request(`${API}/evaluate/${encodeURIComponent(jobId)}`, EvalJob, { cache: "no-store" });
}

export function getCalibration() {
  return request(`${API}/calibration`, CalibrationInfo, { cache: "no-store" });
}

export function saveCalibration(t: Thresholds) {
  return request(`${API}/calibration`, z.object({ ok: z.boolean() }), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(t),
  });
}

export function resetCalibration() {
  return request(`${API}/calibration`, z.object({ ok: z.boolean() }), { method: "DELETE" });
}

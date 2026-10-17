"""
SatyaSpandan API (implementation.md, section 8.1).

    uvicorn api:app --reload --port 8000      # docs at http://localhost:8000/docs

Uploaded videos are written to a temporary file, analysed, and deleted.
Results live in memory for 15 minutes. Nothing is stored permanently.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from rppg_engine import DEFAULT_MODEL_PATH, analyze_traces, analyze_video, load_calibrated_config
from schemas import AnalysisResult, JobCreated, JobStatus, Sample, Scenario
from synthetic import SCENARIOS, make_scenario

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(HERE, "samples")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_VIDEO_SECONDS = 120
JOB_TTL_S = 15 * 60
ALLOWED_EXT = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".m4v"}

app = FastAPI(title="SatyaSpandan API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

def _new_job() -> str:
    _purge()
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {"status": "queued", "progress": 0.0, "stage": "Queued", "result": None,
                         "error": None, "created": time.time()}
    return job_id


def _update(job_id: str, **kw):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def _purge():
    now = time.time()
    with _lock:
        for k in [k for k, v in _jobs.items() if now - v["created"] > JOB_TTL_S]:
            del _jobs[k]


def _run_video_job(job_id: str, path: str, method: str, source: dict, delete_after: bool):
    try:
        _update(job_id, status="running", stage="Reading video")
        _check_duration(path)
        cfg = load_calibrated_config(method=method)
        res = analyze_video(path, cfg, progress=lambda f, s: _update(job_id, progress=f, stage=s))
        out = res.to_dict()
        out["source"] = source
        _update(job_id, status="done", progress=1.0, stage="Done", result=out)
    except ValueError as e:
        _update(job_id, status="error", stage="Error", error=str(e))
    except Exception:  # never leak a stack trace to the browser
        import traceback
        traceback.print_exc()
        _update(job_id, status="error", stage="Error",
                error="Something went wrong while analysing this video. Try an MP4 (H.264) clip with one clearly visible face.")
    finally:
        if delete_after:
            try:
                os.remove(path)
            except OSError:
                pass


def _check_duration(path: str):
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("We couldn't read this video file. Try an MP4 (H.264) file.")
    ok, _ = cap.read()
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    if not ok:
        raise ValueError("We couldn't decode any frames from this file. Try an MP4 (H.264) file.")
    if fps > 0 and frames / fps > MAX_VIDEO_SECONDS:
        raise ValueError(f"Please upload a clip shorter than {MAX_VIDEO_SECONDS // 60} minutes. "
                         "Only the first 30 seconds are analysed anyway.")


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True, "mediapipe_model_loaded": os.path.exists(DEFAULT_MODEL_PATH)}


@app.post("/api/analyze", response_model=JobCreated, status_code=202)
async def analyze_upload(file: UploadFile = File(...), method: Literal["POS", "CHROM", "GREEN"] = Form("POS")):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, "Please upload a video file (MP4, MOV, WebM, AVI or MKV).")
    fd, path = tempfile.mkstemp(suffix=ext, prefix="satya_")
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "The file is larger than 50 MB. Please trim or compress it.")
                out.write(chunk)
    except HTTPException:
        os.remove(path)
        raise
    job_id = _new_job()
    _executor.submit(_run_video_job, job_id, path, method, {"type": "upload", "name": file.filename}, True)
    return {"job_id": job_id}


def _load_samples() -> list[dict]:
    p = os.path.join(SAMPLES_DIR, "samples.json")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        items = json.load(fh)
    for it in items:
        it["available"] = os.path.exists(os.path.join(SAMPLES_DIR, it["file"]))
    return items


@app.get("/api/samples", response_model=list[Sample])
def list_samples():
    return _load_samples()


@app.post("/api/analyze/sample/{sample_id}", response_model=JobCreated, status_code=202)
def analyze_sample(sample_id: str, method: Literal["POS", "CHROM", "GREEN"] = "POS"):
    sample = next((s for s in _load_samples() if s["id"] == sample_id), None)
    if sample is None or not sample["available"]:
        raise HTTPException(404, "That sample clip is not available on this server.")
    job_id = _new_job()
    path = os.path.join(SAMPLES_DIR, sample["file"])
    _executor.submit(_run_video_job, job_id, path, method, {"type": "sample", "name": sample["title"]}, False)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "This analysis has expired or does not exist. Please run it again.")
        return {"job_id": job_id, **{k: job[k] for k in ("status", "progress", "stage", "result", "error")}}


@app.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios():
    return [{"id": k, "title": v["title"], "description": v["description"], "expected": v["expected"]}
            for k, v in SCENARIOS.items()]


@app.get("/api/synthetic/{scenario}", response_model=AnalysisResult)
def synthetic(scenario: str, seed: int = 0, method: Literal["POS", "CHROM", "GREEN"] = "POS"):
    if scenario not in SCENARIOS:
        raise HTTPException(404, f"Unknown scenario. Choose one of: {', '.join(SCENARIOS)}")
    sc = make_scenario(scenario, seed)
    res = analyze_traces(sc["rgb"], sc["fps"], load_calibrated_config(method=method))
    out = res.to_dict()
    out["source"] = {"type": "synthetic", "name": SCENARIOS[scenario]["title"],
                     "true_bpm": round(sc["true_bpm"], 1), "expected": sc["expected"]}
    return out

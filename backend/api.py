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
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from dataclasses import asdict

from rppg_engine import (CALIBRATABLE, CALIBRATION_PATH, DEFAULT_MODEL_PATH, EngineConfig, analyze_traces,
                         analyze_video, extract_traces, load_calibrated_config, load_calibration)
from schemas import AnalysisResult, Calibration, JobCreated, JobStatus, Sample, Scenario
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
    allow_methods=["GET", "POST", "DELETE"],
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


# --------------------------------------------------------------------------
# Accuracy testing (/evaluate page)
# --------------------------------------------------------------------------

EVAL_METHODS = ("POS", "GREEN", "CHROM")


def _run_eval_job(job_id: str, path: str, meta: dict):
    """Track the face once, then score the same traces with every pulse method."""
    import base64

    import cv2
    try:
        _update(job_id, status="running", stage="Reading video")
        _check_duration(path)
        data = extract_traces(path, EngineConfig(), progress=lambda f, s: _update(job_id, progress=0.9 * f, stage=s))
        rgb = {k: v for k, v in data["rgb"].items() if v is not None}
        methods = {}
        for m in EVAL_METHODS:
            _update(job_id, stage=f"Scoring with {m}")
            res = analyze_traces(rgb, data["fps"], load_calibrated_config(method=m), quality=data["quality"])
            methods[m] = res.to_dict(compact=True)
        thumb = None
        if data["overlay"] is not None:
            img = data["overlay"]
            img = cv2.resize(img, (240, int(img.shape[0] * 240 / img.shape[1])), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            thumb = base64.b64encode(buf.tobytes()).decode("ascii") if ok else None
        _update(job_id, status="done", progress=1.0, stage="Done",
                result={**meta, "methods": methods, "thumb_jpeg_b64": thumb})
    except ValueError as e:
        _update(job_id, status="error", stage="Error", error=str(e))
    except Exception:
        import traceback
        traceback.print_exc()
        _update(job_id, status="error", stage="Error", error="Analysis failed for this clip (see the API window for details).")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@app.post("/api/evaluate", response_model=JobCreated, status_code=202)
async def evaluate_upload(
    file: UploadFile = File(...),
    label: Literal["real", "fake", "unknown"] = Form("unknown"),
    true_bpm: Optional[float] = Form(None),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, "Please upload a video file (MP4, MOV, WebM, AVI or MKV).")
    fd, path = tempfile.mkstemp(suffix=ext, prefix="satya_eval_")
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
    meta = {"name": file.filename, "label": label, "true_bpm": true_bpm}
    _executor.submit(_run_eval_job, job_id, path, meta)
    return {"job_id": job_id}


@app.get("/api/evaluate/{job_id}")
def evaluate_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "This evaluation job has expired or does not exist.")
        return {"job_id": job_id, **{k: job[k] for k in ("status", "progress", "stage", "result", "error")}}


@app.get("/api/calibration")
def get_calibration():
    defaults = asdict(EngineConfig())
    return {"defaults": {k: defaults[k] for k in CALIBRATABLE}, "current": load_calibration()}


@app.post("/api/calibration")
def save_calibration(cal: Calibration):
    import datetime
    values = {k: v for k, v in cal.model_dump().items() if v is not None}
    values["saved_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    values["source"] = "evaluate page"
    with open(CALIBRATION_PATH, "w", encoding="utf-8") as fh:
        json.dump(values, fh, indent=2)
    return {"ok": True, "current": load_calibration()}


@app.delete("/api/calibration")
def reset_calibration():
    if os.path.exists(CALIBRATION_PATH):
        os.remove(CALIBRATION_PATH)
    return {"ok": True, "current": {}}

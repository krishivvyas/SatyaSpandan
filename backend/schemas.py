"""Pydantic models: the JSON contract shared with web/lib/schemas.ts."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Reason(BaseModel):
    code: str
    severity: Literal["info", "warn", "block"]
    text: str


class Window(BaseModel):
    # Optional everywhere: real video can yield NaN (-> null); a strict float would turn that into a 500.
    t_start: Optional[float]
    t_end: Optional[float]
    scs: Optional[float]
    bpm: Optional[float]
    r_lr: Optional[float]
    r_lm: Optional[float]
    r_rm: Optional[float]
    msc: Optional[float]
    agree: Optional[float]
    bpm_forehead: Optional[float]
    bpm_left: Optional[float]
    bpm_right: Optional[float]


class AnalysisResult(BaseModel):
    verdict: str
    verdict_key: Literal["real", "manip", "unable"]
    risk_level: Literal["Low", "Medium", "High", "—"]
    confidence: Literal["High", "Medium", "Low", "—"]
    bpm: Optional[float]
    coherence_score: Optional[float]
    snr_db: Optional[float]
    reasons: list[Reason]
    quality: dict[str, Optional[float]]
    fps: Optional[float]
    method: Literal["POS", "CHROM", "GREEN"]
    threshold: float
    t: list[float]
    signals: dict[str, list[float]]
    psd: dict[str, list[float]]
    windows: list[Window]
    pairs: dict[str, dict[str, Optional[float]]]
    overlay_jpeg_b64: Optional[str]
    source: Optional[dict] = None


class Calibration(BaseModel):
    threshold: Optional[float] = None
    grey_margin: Optional[float] = None
    min_frac_coherent: Optional[float] = None
    min_snr_db: Optional[float] = None
    min_snr_flag_db: Optional[float] = None
    max_bg_ratio: Optional[float] = None
    max_bg_corr: Optional[float] = None
    min_bg_amp_ratio: Optional[float] = None
    min_duration_s: Optional[float] = None
    min_face_ratio: Optional[float] = None
    min_face_px: Optional[float] = None
    max_median_motion: Optional[float] = None
    max_fast_motion_frac: Optional[float] = None


class JobCreated(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    progress: float
    stage: str
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None


class Sample(BaseModel):
    id: str
    title: str
    description: str
    licence: str
    kind: Literal["real", "fake", "other"]
    available: bool


class Scenario(BaseModel):
    id: str
    title: str
    description: str
    expected: Literal["real", "manip", "unable"]

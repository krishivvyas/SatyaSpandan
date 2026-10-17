"""
Turn one still face photo into short test videos with a known pulse pattern.

    python tools/make_pulse_video.py --image me.jpg --out samples/

Writes three clips:
    pulse_real.avi   one heartbeat drives the whole face (coherent)
    pulse_fake.avi   cheeks pulse at different rates / with phase jumps (desynchronised)
    pulse_short.avi  coherent but only 4 s long

The colour change is about 1 % (real rPPG is 0.1-0.5 %), so the end-to-end video path
(OpenCV -> MediaPipe -> ROI traces -> engine) can be checked without a dataset.
Use ONLY a photo of a team member who has consented. Never a third party.
"""

from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rppg_engine import DEFAULT_MODEL_PATH, ROI_LANDMARKS  # noqa: E402

FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
             148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]


def landmarks(img_bgr):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    with open(DEFAULT_MODEL_PATH, "rb") as fh:
        opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_buffer=fh.read()), num_faces=1)
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))
    if not res.face_landmarks:
        raise SystemExit("No face found in the photo.")
    h, w = img_bgr.shape[:2]
    return np.array([[p.x * w, p.y * h] for p in res.face_landmarks[0]])


def soft_mask(shape, pts, ids, grow=1.0):
    hull = cv2.convexHull(pts[ids].astype(np.float32))
    c = hull.mean(axis=0)
    hull = ((hull - c) * grow + c).astype(np.int32)
    m = np.zeros(shape[:2], np.float32)
    cv2.fillPoly(m, [hull], 1.0)
    return cv2.GaussianBlur(m, (0, 0), 6)


def writer(path, fps, size):
    for fourcc in ("FFV1", "MJPG"):
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*fourcc), fps, size)
        if vw.isOpened():
            return vw
    raise SystemExit("Could not open a video writer (FFV1/MJPG).")


def render(img, masks_pulses, path, fps=30.0, seconds=20.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * fps)
    h, w = img.shape[:2]
    base = img.astype(np.float32)
    pv = np.array([0.53, 0.77, 0.33], np.float32)  # BGR order of the pulse vector (B, G, R)
    vw = writer(path, fps, (w, h))
    for i in range(n):
        frame = base.copy()
        for mask, pulse in masks_pulses:
            frame *= 1 + 0.012 * pulse[i] * mask[..., None] * pv[None, None, :]
        frame += rng.normal(0, 1.0, frame.shape).astype(np.float32)   # sensor noise (also dithers rounding)
        vw.write(np.clip(frame, 0, 255).astype(np.uint8))
    vw.release()
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", default="samples")
    ap.add_argument("--bpm", type=float, default=72)
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit("Cannot read image")
    if img.shape[1] > 640:
        s = 640 / img.shape[1]
        img = cv2.resize(img, (640, int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    pts = landmarks(img)
    os.makedirs(args.out, exist_ok=True)
    fps, f0 = 30.0, args.bpm / 60
    t = np.arange(int(20 * fps)) / fps
    wave = lambda ph: np.sin(ph) + 0.3 * np.sin(2 * ph)  # noqa: E731
    phase = 2 * np.pi * np.cumsum(f0 + 0.03 * np.sin(2 * np.pi * 0.25 * t)) / fps

    face = soft_mask(img.shape, pts, FACE_OVAL)
    render(img, [(face, wave(phase))], os.path.join(args.out, "pulse_real.avi"))

    left = soft_mask(img.shape, pts, ROI_LANDMARKS["left"], 1.4)
    right = soft_mask(img.shape, pts, ROI_LANDMARKS["right"], 1.4)
    rest = np.clip(face - left - right, 0, 1)
    rng = np.random.default_rng(1)
    jumps = np.repeat(rng.uniform(-np.pi, np.pi, 20), int(fps * 2.5))[: len(t)]
    render(img, [(rest, wave(phase)),
                 (left, wave(2 * np.pi * np.cumsum(np.full(len(t), f0 + 0.35)) / fps)),
                 (right, wave(phase + jumps))],
           os.path.join(args.out, "pulse_fake.avi"))

    render(img, [(face, wave(phase))], os.path.join(args.out, "pulse_short.avi"), seconds=4)


if __name__ == "__main__":
    main()

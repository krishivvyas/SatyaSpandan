# SatyaSpandan · The Pulse of Truth

Explainable deepfake warning signs from facial blood-flow (rPPG) **spatial coherence**.
Cyber Samvad Hackathon 2026, Problem Statement 1 "Is This Video Real?".

The design and rationale are in [`implementation.md`](implementation.md), also available as `implementation.html`. The jury pitch is in [`PITCH.md`](PITCH.md).

## Run it (two terminals)

**1. Backend (Python 3.11)**

```powershell
conda create -n satya python=3.11 -y      # first time only
conda activate satya
cd backend
pip install -r requirements.txt           # first time only
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task   # first time only
python demo_test.py                       # synthetic checks, must end with ALL CHECKS PASSED
uvicorn api:app --port 8000               # API docs: http://localhost:8000/docs
```

**2. Website (Node 22)**

```powershell
cd web
npm install                               # first time only
npm run dev                               # http://localhost:3000
# or, for the demo: npm run build; npm start
```

Open http://localhost:3000. The **Synthetic test** tab works immediately. **Demo samples** become clickable once the clips listed in `backend/samples/samples.json` are added.

> Do not use the base Anaconda environment. On this machine it has a NumPy/SciPy mismatch that crashes `import sklearn`.

## Layout

| Path | What it is |
|---|---|
| `backend/rppg_engine.py` | Whole pipeline: OpenCV ingest, MediaPipe ROIs, GREEN/CHROM/POS, Butterworth filter, PSD/SNR, background subtraction, spatial coherence, quality gate, verdict and reasons. `python rppg_engine.py clip.mp4` analyses one clip. |
| `backend/synthetic.py` | Synthetic RGB traces with known answers (real / two fake types / three unable types) |
| `backend/demo_test.py` | Runs every scenario × 3 methods × 20 seeds; `--video PATH` runs a real clip; `--plots` saves charts to `demo_out/` |
| `backend/api.py`, `schemas.py` | FastAPI: upload jobs with polling, samples, synthetic scenarios. Uploads are deleted after analysis. |
| `backend/tools/eval_ubfc_hr.py` | Heart-rate MAE/RMSE/Pearson against UBFC-rPPG pulse-oximeter ground truth |
| `backend/tools/calibrate.py` | Chooses the coherence threshold τ at ≥ 90 % real-clip specificity with GroupKFold, and writes `calibration.json` |
| `backend/tools/make_pulse_video.py` | Turns one **consented** face photo into real/fake/short test videos |
| `web/` | Next.js 16 + TypeScript + Tailwind 4 site. `lib/copy.ts` holds all mandated wording. `lib/schemas.ts` mirrors the API with Zod. |

## Before the demo

1. Download UBFC-rPPG DATASET_2. Copy one `subjectN/vid.avi` to `backend/samples/real_ubfc.mp4` (or `.avi`, then update `samples.json`). Then run `python tools/eval_ubfc_hr.py --root <UBFC>/DATASET_2`.
2. Create `compressed_demo.mp4` with `ffmpeg -i real_ubfc.mp4 -crf 40 compressed_demo.mp4`.
3. Make `fake_demo.mp4` **only from a consenting team member's face**.
4. Once FaceForensics++ access arrives, run `tools/calibrate.py` so τ is no longer the 55 % placeholder.

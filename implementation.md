# SatyaSpandan — Implementation Plan

> **सत्य स्पंदन · *The Pulse of Truth***
> An explainable deepfake warning tool for **Cyber Samvad Hackathon 2026 — Problem Statement 1: "Is This Video Real?"**
> Approach: remote photoplethysmography (rPPG) and **spatial pulse coherence** across facial regions. It does not use a black-box pixel classifier.

| | |
|---|---|
| **Status** | v1.2: **implemented**. Engine, tests, API, website and pitch are built and verified; see §14 for what changed during the build. |
| **Date** | 17 Oct 2026 |
| **Deliverables in order** | `backend/rppg_engine.py` → `backend/demo_test.py` → `backend/api.py` (FastAPI) → `web/` (Next.js + TypeScript + Tailwind) → 3-minute pitch |
| **Stack** | **Engine:** Python 3.11, OpenCV, MediaPipe, SciPy · **API:** FastAPI + Uvicorn + Pydantic · **Web:** Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, TanStack Query, Zod |
| **Source material** | `ref/` folder (5 PDFs) and [`ubicomplab/rPPG-Toolbox`](https://github.com/ubicomplab/rPPG-Toolbox) |

---

## 1. What we are building, in one paragraph

Each heartbeat pushes blood into facial skin, which changes its colour very slightly (mostly in green). A normal camera can record this. In a **real** face, the forehead, left cheek and right cheek all pulse **at the same rate and almost in phase**, because one heart feeds all of them. Face-swap and reenactment pipelines warp, blend and regenerate the face region by region. Modern fakes can carry a believable *global* heart rate (Seibold et al., 2025), but the *local* agreement between regions is often broken. SatyaSpandan measures that agreement, explains it with plots, and reports one of three cautious verdicts. It never claims proof.

---

## 2. What the reference material tells us (and how it shapes the design)

| Source (in `ref/`) | Key finding | Design decision it drives |
|---|---|---|
| **Cyber Samvad guidelines** (PS-1) | Upload or demo file; three outputs: *"Possible manipulation detected" / "No strong signs detected" / "Unable to assess"*; highlight clues; confidence + plain-language explanation; reminder that results can be wrong; explain what it **cannot** detect; never call a real person a liar; use consented or openly licensed media. | These are hard UI requirements (§8). The verdict strings are copied exactly. Only open datasets are used (§9). |
| **FakeCatcher** — Ciftci, Demir, Yin (arXiv 1901.02212, TPAMI 2020) | Uses six signals `{G_L, G_R, G_M, C_L, C_R, C_M}` (Green and CHROM on the left cheek, right cheek and mid-region). **Spatial coherence + temporal consistency** is the key prior. Cross-PSD between regions separated 99.39 % of real/fake *pairs*, but a *generalised* SVM on that feature alone reached only ~69 %. Segments use ω = 128 frames. Reported 96 % on FF and 91 % on Celeb-DF / Deep Fakes. | The core feature is cross-region coherence (Pearson, CPSD, magnitude-squared coherence). **Expect lower accuracy from a feature set this small.** We will not quote 96 %. |
| **"High-quality deepfakes have a heart!"** — Seibold et al., *Frontiers in Imaging* 2025 | DeepFaceLive-style fakes **inherit the driver video's heart rate** (strong correlation). Pipeline: MediaPipe landmarks, **POS** on a **10 s (300-frame) sliding window**, normalise, **5th-order Butterworth 0.7–3.0 Hz**, FFT, and **two background patches** whose FFT is subtracted from the face FFT. HR error std is 1.39 bpm at 10 s and 3.38 bpm at 8 s, rising further at 6 s and 5 s. The authors suggest spatial blood-flow plausibility as the way forward. | (1) A global HR on its own **never** gives a "real" verdict. (2) We use their filter, window length and background-subtraction recipe. (3) The default window is 10 s and the hard minimum is 6 s. |
| **"Deepfake detection from your pulse"** (build guide) | Concrete stack: `cv2.VideoCapture`, `CAP_PROP_FPS`, MediaPipe Face Landmarker (478 points), `detrend`, `butter(..., output='sos')`, `sosfiltfilt`, `rfft`. Compare 3–6 patches per window. Use logistic regression or SVM with **GroupKFold by person**. Pitfalls: compression, motion, short clips (a 10 s clip only resolves about 6 bpm), skin tone, quoting 96 %. | This is our module layout and pitfall checklist. The upgrade path in §7.4 uses logistic regression with GroupKFold. |
| **UBFC-rPPG** — Bobbia et al. 2017 | Logitech C920, 30 fps, 640×480, **uncompressed**, CMS50E pulse-oximeter ground truth. Dataset 2 has 42 subjects doing a maths game. | Our "real" reference clips and HR-accuracy benchmark. Because the dataset is uncompressed, we must also test on re-encoded copies (§10). |
| **rPPG-Toolbox** (UW Ubicomp, NeurIPS 2023) | Reference implementations of `GREEN`, `CHROME_DEHAAN`, `POS_WANG`, plus `_calculate_fft_hr` (periodogram, next-power-of-2 nfft, argmax in band) and `_calculate_SNR` (power within ±6 bpm of the 1st and 2nd harmonics vs the rest of the band, in dB). Has a ready `UBFC-rPPG_UNSUPERVISED.yaml` config. | We re-implement POS, CHROM and SNR following those algorithms in our own vectorised NumPy code, with the papers cited. We use the toolbox itself as an **independent benchmark** to sanity-check our HR MAE on UBFC. ⚠️ The toolbox uses the *Responsible AI Source Code License*, so we **do not copy-paste** its code into our repo. |

---

## 3. System architecture

```
                         ┌──────────────────────────────────────────────────────────────┐
  video (.mp4/.avi) ───▶ │ 1. INGEST     cv2.VideoCapture · true FPS · ≤ 30 s · resize  │
                         └──────────────┬───────────────────────────────────────────────┘
                                        ▼
                         ┌──────────────────────────────────────────────────────────────┐
                         │ 2. LANDMARKS  MediaPipe FaceLandmarker (478 pts, VIDEO mode)  │
                         │    ROI masks: Forehead(M) · Left cheek(L) · Right cheek(R)    │
                         │               + 2 background patches (BG1, BG2)               │
                         │    per-frame mean RGB per ROI  →  T × 5 × 3 array             │
                         │    quality: face-found ratio, face size, motion               │
                         └──────────────┬───────────────────────────────────────────────┘
                                        ▼
                         ┌──────────────────────────────────────────────────────────────┐
                         │ 3. PULSE      GREEN | CHROM | POS  (per ROI)                 │
                         │ 4. FILTER     detrend → Butterworth-5 SOS 0.7–3.0 Hz         │
                         │               (sosfiltfilt) → z-normalise                     │
                         └──────────────┬───────────────────────────────────────────────┘
                                        ▼
               ┌────────────────────────┴─────────────────────────┐
               ▼                                                  ▼
 ┌──────────────────────────────┐              ┌───────────────────────────────────────┐
 │ 5. SPECTRAL / QUALITY        │              │ 6. SPATIAL COHERENCE (per 10 s window)│
 │  PSD (periodogram, nfft=2^k) │              │  Pearson r: L–R, L–M, R–M             │
 │  BPM = argmax in band × 60   │              │  CPSD + MSC at HR ± 0.15 Hz           │
 │  SNR (dB, harmonic method)   │              │  phase lag at HR (ms)                 │
 │  face PSD − background PSD   │              │  per-ROI BPM agreement                │
 └──────────────┬───────────────┘              └───────────────────┬───────────────────┘
                └────────────────────┬─────────────────────────────┘
                                     ▼
                ┌──────────────────────────────────────────────────┐
                │ 7. DECISION                                      │
                │  quality gate fails ─▶ ⚪ Unable to assess        │
                │  coherence ≥ τ      ─▶ 🟢 No strong signs detected│
                │  coherence <  τ     ─▶ 🟡 Possible manipulation   │
                │  + risk level + reasons[] (plain language)       │
                └──────────────────────┬───────────────────────────┘
                                       ▼
                ┌──────────────────────────────────────────────────┐
                │ 8. api.py  FastAPI  (JSON contract, Pydantic)    │
                │  POST /api/analyze → job_id · GET /api/jobs/{id} │
                └──────────────────────┬───────────────────────────┘
                                       ▼  HTTP / JSON (polled)
                ┌──────────────────────────────────────────────────┐
                │ 9. web/  Next.js + TypeScript + Tailwind         │
                │  ROI overlay · synced waves · PSD · metrics ·    │
                │  explanation · disclaimer · limitations panel    │
                └──────────────────────────────────────────────────┘
```

**Why it is split this way:** MediaPipe, OpenCV and SciPy only run well in Python, so the signal processing stays in Python. The Python API exposes it as JSON. The browser app is pure TypeScript and never sees the maths, so the two halves can be built in parallel once the JSON contract (§8.3) is agreed.

---

## 4. Repository layout

```
SatyaSpandan/
├── implementation.md / implementation.html   ← this plan
├── docker-compose.yml       ← optional: runs api + web together
├── backend/
│   ├── requirements.txt
│   ├── rppg_engine.py       ← Step 1: all signal processing and scoring (no web code)
│   ├── synthetic.py         ← synthetic Real / Fake / Unable trace generator (shared)
│   ├── demo_test.py         ← Step 2: runs synthetic scenarios + checks
│   ├── api.py               ← Step 3a: FastAPI app (jobs, samples, synthetic)
│   ├── schemas.py           ← Pydantic models = the JSON contract
│   ├── tools/
│   │   ├── calibrate.py     ← fits thresholds τ from labelled clips (GroupKFold)
│   │   └── eval_ubfc_hr.py  ← HR MAE vs UBFC ground_truth.txt
│   ├── models/face_landmarker.task   (downloaded, ~3.6 MB)
│   └── samples/             ← demo clips (open licence or consented only)
│       ├── samples.json     ← id, title, description, licence, file
│       ├── real_ubfc_subjectXX.mp4
│       └── fake_demo.mp4
├── web/                     ← Step 3b: Next.js app
│   ├── app/
│   │   ├── layout.tsx       ← fonts, theme provider, header, footer
│   │   ├── page.tsx         ← landing: upload / pick sample / synthetic
│   │   ├── analyze/[jobId]/page.tsx   ← results dashboard
│   │   ├── how-it-works/page.tsx      ← science explainer
│   │   └── limitations/page.tsx       ← full transparency page
│   ├── components/
│   │   ├── upload-dropzone.tsx   sample-picker.tsx   analysis-progress.tsx
│   │   ├── verdict-badge.tsx     metric-cards.tsx    roi-overlay.tsx
│   │   ├── pulse-wave-chart.tsx  spectrum-chart.tsx  coherence-timeline.tsx
│   │   ├── reasons-list.tsx      disclaimer-banner.tsx  limitations-panel.tsx
│   │   └── ui/               ← shadcn/ui primitives (card, tabs, accordion, …)
│   ├── lib/
│   │   ├── api.ts            ← typed fetch wrappers
│   │   ├── schemas.ts        ← Zod schemas mirroring backend/schemas.py
│   │   └── copy.ts           ← verdict strings, disclaimer, limitations (single source)
│   ├── next.config.ts        ← rewrites /api/* → FastAPI in dev
│   └── package.json
└── ref/                      ← papers (already present)
```

---

## 5. Environment setup

> ⚠️ **Found on this machine:** base Anaconda has **NumPy 2.5.2 with a SciPy / scikit-learn built for NumPy 1.x**, so `import sklearn` crashes. **Do not use the base env.** Create an isolated one.

**Backend (Python)**

```powershell
# Python 3.11 or 3.12 (MediaPipe wheels exist for both)
conda create -n satya python=3.11 -y
conda activate satya
cd backend
pip install -r requirements.txt
# MediaPipe face landmarker model
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
uvicorn api:app --reload --port 8000        # http://localhost:8000/docs for Swagger
```

`backend/requirements.txt` (pin after the first working install with `pip freeze`):

```
numpy>=1.26,<2.3
scipy>=1.11
opencv-python-headless>=4.9   # headless: no GUI libs needed on a server
mediapipe>=0.10.14
scikit-learn>=1.4
fastapi>=0.115
uvicorn[standard]>=0.30
python-multipart>=0.0.9       # needed for file uploads
pydantic>=2.7
matplotlib>=3.8               # only for demo_test.py plots
```

**Frontend (Node 22, already installed on this machine)**

```powershell
npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir=false --import-alias "@/*" --use-npm
cd web
npx shadcn@latest init
npx shadcn@latest add card button tabs accordion badge progress alert tooltip separator skeleton
npm install @tanstack/react-query zod recharts react-dropzone lucide-react next-themes
npm run dev                                   # http://localhost:3000
```

Versions current on npm today: `next` 16.4, `tailwindcss` 4.3, `recharts` 3.10. Commit `package-lock.json` so the whole team installs identical versions.

**Running both for the demo:** use two terminals (`uvicorn` + `npm run dev`), or `docker compose up`. **Run the live demo on a local laptop**, not a cloud host. That way venue Wi-Fi cannot break it and no uploaded video leaves the machine.

---

## 6. Step 1 — `rppg_engine.py` (detailed spec)

The design rule: **pure functions plus one orchestrator.** Every stage can be tested on its own, and `demo_test.py` can feed synthetic RGB traces into stage 3 directly, skipping video entirely.

### 6.1 Public API

```python
@dataclass
class EngineConfig:
    method: str = "POS"            # "GREEN" | "CHROM" | "POS"
    band_hz: tuple = (0.7, 3.0)    # 42–180 bpm (Seibold 2025)
    filter_order: int = 5
    window_s: float = 10.0         # Seibold: best HR stability at 10 s
    step_s: float = 2.0
    min_duration_s: float = 6.0
    max_duration_s: float = 30.0   # cap processing time for the demo
    max_width: int = 640           # downscale before landmarking
    # quality-gate & decision thresholds → §7 (calibrated, not hard-coded truths)

@dataclass
class AnalysisResult:
    verdict: str                   # exactly one of the 3 hackathon strings
    verdict_key: str               # "real" | "manip" | "unable"
    risk_level: str                # "Low" | "Medium" | "High" | "—"
    bpm: float | None
    coherence_score: float | None  # 0–100 %
    snr_db: float | None
    reasons: list[str]             # plain-language bullet points
    quality: dict                  # face_ratio, face_px, motion, duration_s, fps
    fps: float
    t: np.ndarray                  # time axis (s)
    signals: dict[str, np.ndarray] # filtered pulse per ROI: "forehead","left","right"
    psd: dict                      # freqs, per-ROI PSD, background PSD, cleaned PSD
    windows: list[dict]            # per-window metrics (for the timeline chart)
    overlay_frame: np.ndarray      # BGR frame with ROI polygons drawn

def analyze_video(path: str, cfg: EngineConfig = EngineConfig(), progress=None) -> AnalysisResult
def analyze_traces(rgb: dict[str, np.ndarray], fps: float, cfg=EngineConfig(), quality=None) -> AnalysisResult
```

`analyze_traces` is the seam that lets `demo_test.py` test all the maths without MediaPipe.

`AnalysisResult.to_dict()` converts NumPy arrays to lists. For the web it also **downsamples the waves to about 600 points**, keeps PSD bins only for 30–240 bpm, and encodes `overlay_frame` as a base64 JPEG, which keeps the JSON payload around 100–200 KB.

### 6.2 Stage 1 — Ingestion

- `cap = cv2.VideoCapture(path)` and `fps = cap.get(cv2.CAP_PROP_FPS)`.
  - **Sanity check:** if `fps` is 0, NaN or outside 10–120, fall back to `CAP_PROP_POS_MSEC` timestamps (`n_frames / duration`). If that also fails, return **Unable to assess** ("could not read the frame rate").
  - Variable-frame-rate phone clips: store the per-frame `POS_MSEC` timestamps. If their jitter is above 10 %, resample the RGB traces to a uniform grid at the median FPS with `np.interp` before filtering.
- Read at most `max_duration_s × fps` frames. Downscale to `max_width` (this keeps MediaPipe fast and does not change the spatial means).
- Convert BGR to RGB once per frame.

### 6.3 Stage 2 — Landmarks and ROIs

**MediaPipe Tasks API** (`mediapipe.tasks.python.vision.FaceLandmarker`), `running_mode=VIDEO`, `num_faces=1`, `min_face_detection_confidence=0.5`, `min_tracking_confidence=0.5`. Call `detect_for_video(mp_image, timestamp_ms)` with monotonically increasing timestamps (`int(i * 1000 / fps)`).

ROI polygons, using MediaPipe 478-mesh indices. "Left/Right" means the **subject's** side. These are starting sets: **verify them in the first hour** by drawing the indices on one frame, as the build guide recommends.

| ROI | Landmark polygon (starting set) | Why this region |
|---|---|---|
| Forehead (M) | `10, 338, 297, 299, 296, 336, 9, 107, 66, 69, 67, 109` | Thin skin and strong signal (Verkruysse 2008). Avoid hair and eyebrows. |
| Left cheek (L) | `345, 346, 347, 348, 349, 329, 371, 266, 425, 411, 352` | Large flat skin patch, away from the mouth. |
| Right cheek (R) | `116, 117, 118, 119, 120, 100, 142, 36, 205, 187, 123` | Mirror of L. |
| Background BG1 and BG2 | Two squares, each 12 % of frame width, at the top-left and top-right of the frame. Any square that overlaps the face bounding box (+15 % margin) is shifted down. | Measures ambient flicker and compression noise (Seibold 2025). |

Per frame:
1. Convert landmarks to pixel coordinates. Fill each polygon with `cv2.fillPoly` into a small mask, cropped to the polygon's bounding rectangle for speed.
2. **Skin filter** inside the mask: drop pixels outside a broad YCrCb skin range and the top and bottom 5 % of luminance. This removes specular highlights, beard and shadow edges. The YCrCb range must be **wide enough for all Fitzpatrick skin types** (see §11).
3. Mean R, G, B of the remaining pixels. Store `NaN` if fewer than 50 pixels are left.
4. Quality bookkeeping:
   - `face_found[i]` (true/false)
   - `face_px` = inter-ocular distance in pixels (landmarks 33 to 263)
   - `motion[i]` = median landmark displacement since the previous frame ÷ inter-ocular distance
5. Save one overlay frame (the middle frame) with the polygons drawn: forehead amber, left cheek blue, right cheek magenta, background grey dashed.

Missing frames: if a gap is shorter than 0.5 s, fill it by linear interpolation. Longer gaps split the clip into segments, and only segments of at least `min_duration_s` are analysed.

### 6.4 Stage 3 — Pulse extraction (per ROI)

All three methods take `rgb: (T, 3)` and return `pulse: (T,)`. Our code is vectorised and written from the original papers, following the same algorithmic steps as the rPPG-Toolbox implementations.

**GREEN** (Verkruysse 2008, the baseline): `pulse = rgb[:, 1]`.

**CHROM** (de Haan & Jeanne 2013): within sliding windows of 1.6 s with 50 % overlap,
```
Cn = rgb_win / mean(rgb_win)
X  = 3·R − 2·G
Y  = 1.5·R + G − 1.5·B
Xf, Yf = bandpass(X), bandpass(Y)
S  = Xf − (σ(Xf)/σ(Yf))·Yf
```
Then apply a Hann window and overlap-add the windows.

**POS** (Wang et al. 2017, the default because Seibold 2025 uses it), with window `l = ceil(1.6·fs)`:
```
Cn = rgb[m:n] / mean(rgb[m:n])        # temporal normalisation
S  = [[0, 1, −1], [−2, 1, 1]] @ Cnᵀ   # project onto plane orthogonal to skin tone
h  = S0 + (σ(S0)/σ(S1))·S1            # alpha tuning
H[m:n] += h − mean(h)                 # overlap-add
```

Run the method on each ROI separately (`forehead`, `left`, `right`) **and** on the pooled skin (the pixel-weighted mean of all three) to get the global pulse used for BPM.

**Background traces:** the background patches use the **green channel** (POS assumes skin, so it means nothing on a wall). The two background traces are averaged into one, as Seibold does.

### 6.5 Stage 4 — Filtering

```python
x = scipy.signal.detrend(pulse, type="linear")            # slow illumination drift
sos = scipy.signal.butter(5, [0.7, 3.0], btype="bandpass", fs=fps, output="sos")
x = scipy.signal.sosfiltfilt(sos, x)                       # zero-phase, keeps inter-ROI lags real
x = (x - x.mean()) / (x.std() + 1e-9)                      # z-normalise
```
- **Zero-phase** filtering (`sosfiltfilt`) is essential. A one-way filter would add phase shifts that could be mistaken for inter-region lag.
- Guard: `sosfiltfilt` needs `len(x) > 3·(2·order+1)`. This is always true above 6 s.
- Optional: a `detrend` λ-smoothness prior (Tarvainen, as used in the toolbox) with λ = 100, behind a flag, for strong lighting drift.

### 6.6 Stage 5 — Spectrum, BPM, SNR, background subtraction

```python
nfft = next_pow2(len(x)) * 2                     # zero-pad for finer bins
f, P = scipy.signal.periodogram(x, fs=fps, nfft=nfft, detrend=False)
band = (f >= 0.7) & (f <= 3.0)
bpm  = 60 * f[band][argmax(P[band])]
```
- **SNR (dB)**, following the toolbox `_calculate_SNR` definition with the *estimated* HR because we have no oximeter: power within ±0.1 Hz (6 bpm) of the 1st and 2nd harmonics, divided by the remaining in-band power, then `10·log10`.
- **Background-cleaned PSD** (Seibold): normalise the face and background PSDs to unit area in the band, then compute `P_clean = clip(P_face − P_bg, 0, ∞)`. Take the BPM from `P_clean`. Also compute `bg_ratio = P_bg(f_hr) / P_face(f_hr)`. A high ratio means the "pulse" is really ambient flicker or a compression artefact, and the clip goes to **Unable to assess**.
- **Sliding windows:** 10 s windows with a 2 s step. The BPM per window gives a HR-over-time trace. A HR that jumps by more than 15 bpm between neighbouring windows is physiologically implausible, and becomes a reason string plus a small penalty.
- Resolution note for the UI: a window of length W seconds resolves `60/W` bpm, which is 6 bpm at 10 s. Zero-padding only interpolates the spectrum and does not add resolution.

### 6.7 Stage 6 — Spatial coherence (the core forensic feature)

For each 10 s window and each ROI pair `(L,R)`, `(L,M)`, `(R,M)`:

| Feature | Computation | Real face expectation |
|---|---|---|
| Pearson r | `np.corrcoef(xa, xb)[0,1]` on filtered signals | High (≳ 0.5 for clean video) |
| Magnitude-squared coherence at HR | `f, C = scipy.signal.coherence(xa, xb, fs, nperseg=min(len, int(4*fs)))`, then mean C over `f_hr ± 0.15 Hz` | High (≳ 0.6) |
| Cross-PSD peak and phase | `f, Pxy = scipy.signal.csd(xa, xb, fs, nperseg=…)`, then `abs(Pxy)` at f_hr (FakeCatcher F1: mean and max of CPSD), and `angle(Pxy)` at f_hr converted to a lag in ms: `Δφ / (2π f_hr) · 1000` | Small lag (pulse transit across the face is only tens of ms) |
| BPM agreement | `|BPM_a − BPM_b|` per ROI | ≤ 6 bpm (one bin) |
| Region–background correlation | `corr(x_roi, x_bg)` | Low. If it is high, the "pulse" is global lighting or compression. |

**Spatial Coherence Score (SCS, 0–100 %)**, per window:
```
r̄    = mean of the 3 pair Pearson r, clipped to [0, 1]
MSC̄  = mean of the 3 pair coherences at f_hr
agree = fraction of the 3 pairs with |ΔBPM| ≤ 6 and |lag| ≤ lag_max (start lag_max = 150 ms)
SCS_w = 100 · (0.4·r̄ + 0.4·MSC̄ + 0.2·agree)
```
Video SCS = **median** over windows, which is robust to one bad window from a head turn. Also report `frac_coherent` = the share of windows with `SCS_w ≥ τ`.

The weights (0.4 / 0.4 / 0.2) are a transparent starting point. In §7.4 a logistic regression on the same features replaces hand-set weights, and its coefficients can still be explained.

### 6.8 Stage 7 — Decision logic

**A. Quality gate.** If **any** of these is true, the verdict is ⚪ **"Unable to assess"**, with the specific reason:

| Check | Starting threshold | Reason shown to user |
|---|---|---|
| Usable duration | < 6 s | "The clip is too short to measure a heartbeat reliably (at least 6 seconds of visible face needed)." |
| Face found ratio | < 80 % of frames | "A face was not visible clearly enough in most frames." |
| Face size | inter-ocular < 40 px | "The face is too small or far away for skin-colour analysis." |
| Motion | median motion > 0.05 inter-ocular/frame, or > 30 % of frames above 0.10 | "There is too much head or camera movement." |
| Signal quality | best single-region SNR < −1 dB (SNR band = ±max(0.1 Hz, 1/duration) around the 1st and 2nd harmonics) | "The pulse signal is too weak, which is typical of heavily compressed, forwarded or very dark videos." |
| Ambient dominance | on the best region: bg_ratio > 0.5 or ROI–bg corr > 0.6 | "Lighting flicker or compression noise looks like a pulse, so no reliable reading is possible." |

**B. Verdict** (only if the gate passes):
- `SCS ≥ τ` **and** `frac_coherent ≥ 0.6` → 🟢 **"No strong signs detected"**
- otherwise → 🟡 **"Possible manipulation detected"**

Starting value τ = 55. **It is replaced by the calibrated value from `tools/calibrate.py`** (§10).

**C. Risk level** (shown next to the badge, never as a "fake probability"):
- `|SCS − τ| ≥ 20` → High confidence in the direction of the verdict
- `10–20` → Medium
- `< 10` → Low ("borderline: please treat with extra caution")

Wording maps to: 🟢 + High → "Low risk"; 🟡 + High → "High risk".

**D. Reasons generator.** This is a pure function from metrics to a list of strings. Each rule fires independently, and the UI shows the top 3–4. Examples:
- `r_LR < 0.3` → "The left and right cheeks do not pulse together (correlation 0.21). In a real face both cheeks are fed by the same heartbeat."
- `|BPM_L − BPM_M| > 10` → "The forehead shows 96 bpm but the left cheek shows 72 bpm. A single heart cannot produce two different rates."
- `lag > 150 ms` → "The right cheek lags the forehead by 240 ms, far more than natural blood-flow delays."
- `HR jumps` → "The heart rate jumps by 25 bpm within 2 seconds, which is physiologically unlikely."
- Green verdict → "All three skin regions rise and fall together at about 74 bpm (coherence 81 %)."
- **Always appended:** "A visible heartbeat does not prove a video is real. Modern face-swaps can copy the pulse of the source video (Seibold et al., 2025)."

Reasons are returned as `{code, severity, text}`, for example `{"code": "cheek_desync", "severity": "warn", "text": "..."}`. The website can then show an icon per reason, and translate by `code` later (Hindi is a stretch goal).

---

## 7. Step 2 — `demo_test.py` (synthetic verification)

Goal: prove the maths **before** touching real video, and give the jury a deterministic demo that needs no dataset.

The generator lives in `backend/synthetic.py`, so that both `demo_test.py` and the API's `/api/synthetic/{scenario}` endpoint use the same code. The website therefore has a "Synthetic scenarios" tab that works with no video at all.

### 7.1 Signal generator

Generate per-ROI **RGB** traces (not pulses), so that GREEN, CHROM and POS are all exercised:
```
skin_base  = [R,G,B] ≈ (180, 120, 100)   (vary across Fitzpatrick-like tones)
pulse(t)   = sin(2π·f_hr(t)·t + φ_roi) + 0.3·sin(2·2π·f_hr·t)     # 2nd harmonic
f_hr(t)    = 1.2 Hz + 0.03·sin(2π·0.25·t)                          # HRV / respiration modulation
pulse vector (relative) = [0.33, 0.77, 0.53] · A    (blood absorbs green most; de Haan PBV)
rgb_roi(t) = skin_base · (1 + 0.01·illum(t)) · (1 + pulse_vector·pulse(t)) + noise
illum(t)   = slow drift (0.05 Hz) + optional flicker
```

| Scenario | Construction | Expected verdict |
|---|---|---|
| **REAL** | Same `f_hr` everywhere, φ lags of 0–30 ms, Gaussian noise σ at SNR ≈ +5 dB | 🟢 No strong signs |
| **FAKE — desync** | Forehead at 1.2 Hz; cheeks at 1.45 Hz and 0.95 Hz, or the same rate with random phase jumps every 2–3 s (blending-seam behaviour) | 🟡 Possible manipulation |
| **FAKE — inherited HR** (Seibold case) | All ROIs share a *global* 1.2 Hz component, but the cheeks add strong independent band-limited noise plus a 200 ms lag | 🟡, and it demonstrates that the global HR alone looks fine |
| **UNABLE — noise** | Pulse amplitude 0.05×, noise ×10 (simulating compression) | ⚪ Unable (SNR) |
| **UNABLE — short** | REAL but only 4 s long | ⚪ Unable (duration) |
| **UNABLE — flicker** | Strong 1.0 Hz illumination flicker present in the background too | ⚪ Unable (ambient) |

### 7.2 Checks (run with `python demo_test.py`, which exits non-zero on failure)
- Recovered BPM is within ±3 bpm of the true value for REAL, for each of GREEN, CHROM and POS.
- Verdict matches the table for every scenario, with seeds 0–19 (20 runs each, so we test robustness rather than a lucky seed). The default **POS must be 20/20**. CHROM and GREEN must reach at least 18/20, because their colour combinations amplify sensor noise on the darkest synthetic skin tone (see §14).
- SCS(REAL) − SCS(FAKE-desync) ≥ 30 points on average.
- Plots are saved to `demo_out/*.png` so the team can see the waves.

### 7.3 Plugging in real clips (instructions written into the script's docstring)
- `python demo_test.py --video samples/real_ubfc_subject1.mp4` runs the full pipeline and prints a report.
- `python tools/eval_ubfc_hr.py --root D:/UBFC/DATASET_2` reads `subject*/vid.avi` and `ground_truth.txt` (line 1 = PPG wave, line 2 = HR, line 3 = timestamps), then prints MAE, RMSE and Pearson against the oximeter. **Target: POS MAE < 5 bpm on still clips.** For comparison, run rPPG-Toolbox with `configs/infer_configs/UBFC-rPPG_UNSUPERVISED.yaml` (set `DATA_PATH`, and `DO_PREPROCESS: True` on the first run).
- FaceForensics++ pairs: `original_sequences/youtube/c23/videos/XXX.mp4` vs `manipulated_sequences/Deepfakes/c23/videos/XXX_YYY.mp4`. This needs the FF++ access form, so request it **today**.

### 7.4 Upgrade path: a learned decision (only if time permits)
- Per-window feature vector of about 20 numbers: 3×r, 3×MSC, 3×|lag|, 3×ΔBPM, 3× CPSD mean and max, SNR, bg_ratio, HR jump.
- `LogisticRegression(class_weight="balanced")` + `StandardScaler`, using **`GroupKFold` by source identity**. A real video and every fake derived from it stay on the same side of the split.
- Windows vote, and the video score is the mean probability. Report the cross-validated accuracy **honestly**. Above chance on unseen people is a valid result.
- The coefficients remain explainable ("cheek correlation carries the most weight").

---

## 8. Step 3 — Website: FastAPI backend + Next.js frontend

### 8.1 Backend API (`backend/api.py`)

Analysing a 15–30 s clip takes 5–30 s, which is too long for a single blocking request with a nice progress bar. So the API uses a **job + polling** pattern: an in-memory job store, with `BackgroundTasks` or a `ThreadPoolExecutor(max_workers=2)`.

| Method & path | Body / params | Returns |
|---|---|---|
| `POST /api/analyze` | multipart `file` (mp4/avi/mov/webm, **≤ 50 MB**), optional `method=POS\|CHROM\|GREEN` | `202 {job_id}` |
| `POST /api/analyze/sample/{sample_id}` | — | `202 {job_id}` |
| `GET /api/jobs/{job_id}` | — | `{status: "queued"\|"running"\|"done"\|"error", progress: 0–1, stage: "Tracking face…", result?: AnalysisResult, error?: string}` |
| `GET /api/samples` | — | list from `samples.json` (id, title, description, licence, thumbnail) |
| `GET /api/synthetic/{scenario}` | `real \| fake_desync \| fake_inherited \| unable_noise \| unable_short \| unable_flicker`, `seed` | `AnalysisResult` (instant, no job) |
| `GET /api/health` | — | `{ok, mediapipe_model_loaded}` |

Backend rules:
- Check the file **type by content**, using `cv2.VideoCapture` opening successfully, not only the extension. Reject clips longer than 2 minutes.
- Write uploads to `tempfile.NamedTemporaryFile` and **delete them in `finally`** once the job ends. Results expire from memory after 15 minutes. Video is never saved to disk permanently.
- Create the MediaPipe `FaceLandmarker` per job. It is not thread-safe, and VIDEO mode needs increasing timestamps.
- CORS: allow only `http://localhost:3000` in dev. In production the web app proxies through its own domain, so CORS is not needed.
- Errors return a friendly message ("We couldn't read this video file. Try MP4 (H.264)."), never a stack trace.

### 8.2 JSON contract (`backend/schemas.py` ⇄ `web/lib/schemas.ts`)

```ts
// web/lib/schemas.ts — mirrors the Pydantic models exactly
export const Verdict = z.enum(["real", "manip", "unable"]);
export const AnalysisResult = z.object({
  verdict: z.string(),                       // exact hackathon wording
  verdict_key: Verdict,
  risk_level: z.enum(["Low", "Medium", "High", "—"]),
  bpm: z.number().nullable(),
  coherence_score: z.number().nullable(),    // 0–100
  snr_db: z.number().nullable(),
  reasons: z.array(z.object({ code: z.string(), severity: z.enum(["info","warn","block"]), text: z.string() })),
  quality: z.object({ face_ratio: z.number(), face_px: z.number(), motion: z.number(),
                      duration_s: z.number(), fps: z.number() }),
  t: z.array(z.number()),                                         // ≤ 600 points
  signals: z.object({ forehead: z.array(z.number()), left: z.array(z.number()), right: z.array(z.number()) }),
  psd: z.object({ bpm_axis: z.array(z.number()), forehead: z.array(z.number()), left: z.array(z.number()),
                  right: z.array(z.number()), background: z.array(z.number()), cleaned: z.array(z.number()) }),
  windows: z.array(z.object({ t_start: z.number(), t_end: z.number(), scs: z.number(), bpm: z.number(),
                              r_lr: z.number(), r_lm: z.number(), r_rm: z.number() })),
  threshold: z.number(),                     // τ, for the timeline line
  overlay_jpeg_b64: z.string().nullable(),
  method: z.enum(["POS", "CHROM", "GREEN"]),
});
export type AnalysisResult = z.infer<typeof AnalysisResult>;
```

The frontend runs `AnalysisResult.parse(json)` on every response. If the backend changes shape, the page shows a clear error instead of a broken chart.

### 8.3 Frontend pages and flow

```
 /  (landing)                          /analyze/[jobId]  (results)
┌─────────────────────────────────┐   ┌───────────────────────────────────────────────┐
│ 🫀 SatyaSpandan                  │   │ ⚠️ Disclaimer banner (sticky, not dismissible) │
│ "Is this video real?"            │   │ ┌───────────────────────────────────────────┐ │
│ ┌─────────────────────────────┐ │   │ │ VERDICT  🟢/🟡/⚪  risk level · method      │ │
│ │ Tabs: Upload | Samples |    │ │   │ └───────────────────────────────────────────┘ │
│ │       Synthetic             │ │   │ [BPM] [Coherence %] [SNR dB] [Face tracking %]│
│ │  ┌───────────────────────┐  │ │   │ ┌─────────────────┐ ┌───────────────────────┐ │
│ │  │ Drop a video here     │  │ │──▶│ │ ROI overlay img │ │ Why this result       │ │
│ │  │ MP4/MOV/WebM ≤ 50 MB  │  │ │   │ └─────────────────┘ │ • cheeks out of sync  │ │
│ │  └───────────────────────┘  │ │   │                     │ • …                   │ │
│ │ Method: POS ▾  [Analyse]    │ │   │                     └───────────────────────┘ │
│ └─────────────────────────────┘ │   │ Tabs: Pulse waves | Spectrum | Over time      │
│ How it works (3 steps) · Limits │   │ ▸ System Limitations & Transparency           │
└─────────────────────────────────┘   │ [Analyse another video]                       │
                                      └───────────────────────────────────────────────┘
```

While a job runs, the results page shows `analysis-progress.tsx`: the stage name from the API ("Reading video → Tracking face → Extracting pulse → Comparing regions"), a progress bar, and skeleton cards. Polling uses TanStack Query `useQuery` with `refetchInterval: 800` that stops once the status is `done` or `error`.

### 8.4 Components

| Component | Implementation detail |
|---|---|
| `upload-dropzone.tsx` | `react-dropzone`, accepting `video/*` up to 50 MB, with a client-side duration check through a hidden `<video>` element's `loadedmetadata`. Shows a consent checkbox: "I have the right to analyse this video." Sends with `FormData`, then `router.push('/analyze/' + jobId)`. |
| `sample-picker.tsx` | Cards from `GET /api/samples`, showing title, licence line and "Real reference" / "Demo fake" tag. |
| Synthetic tab | Six scenario buttons that call `/api/synthetic/...`. The result renders on the same results view (`/analyze/synthetic-<scenario>`). This keeps the demo usable even if the video pipeline fails. |
| `verdict-badge.tsx` | Large card. Green `#1a7f37` with a `ShieldCheck` icon for "No strong signs detected"; amber `#9a6700` with `AlertTriangle` for "Possible manipulation detected"; grey `#57606a` with `HelpCircle` for "Unable to assess". The text is always present, so colour is never the only cue. `role="status"` and `aria-live="polite"` let screen readers announce it. |
| `metric-cards.tsx` | Four cards, each with a `Tooltip` explaining the metric in one sentence. SNR also shows a Good/Fair/Poor label. |
| `roi-overlay.tsx` | `<img src={"data:image/jpeg;base64," + b64}>` with a colour legend: forehead amber, left cheek blue, right cheek magenta, background grey. |
| `pulse-wave-chart.tsx` | Recharts `LineChart`, three `Line`s on a shared time axis, `isAnimationActive={false}`. Toggle between overlaid and stacked (three small `LineChart`s with the same `syncId` so the tooltips move together). Low-coherence windows are shaded with `ReferenceArea` in amber. |
| `spectrum-chart.tsx` | Recharts PSD per region plus a dashed background line. A `ReferenceLine` marks the detected BPM. The x-axis is labelled in **bpm**. |
| `coherence-timeline.tsx` | `BarChart` of SCS per window, coloured by pass/fail, with a `ReferenceLine` at τ. |
| `reasons-list.tsx` | Reasons with icons by severity. The Seibold caveat is always last. |
| `disclaimer-banner.tsx` | shadcn `Alert` with the **exact text** below. It appears on every results view, is sticky at the top, and has no close button. |
| `limitations-panel.tsx` | shadcn `Accordion` titled **"System Limitations & Transparency"**, plus a full `/limitations` page. |
| Theme | `next-themes` light/dark. Chart colours come from CSS variables so they work in both themes. |
| Responsive | Single column under `md`, so a judge can open it on a phone. |

All user-facing wording (verdicts, disclaimer, limitations, metric tooltips) lives in **`web/lib/copy.ts`**, so the mandated text exists in exactly one place.

### 8.5 Dev wiring

```ts
// web/next.config.ts
const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_URL ?? "http://127.0.0.1:8000"}/api/:path*` }];
  },
};
export default nextConfig;
```

The browser only ever calls `/api/...` on the same origin. Note that Next.js rewrites have a default proxy body limit. If 50 MB uploads fail through the proxy, either raise the limit in `next.config.ts` or point the dropzone directly at `NEXT_PUBLIC_API_URL` and enable CORS for that one origin.

### 8.6 Deployment options

| Option | Web | API | Notes |
|---|---|---|---|
| **A. Local laptop (recommended for the demo)** | `npm run build && npm start` | `uvicorn api:app` | No network risk; uploads never leave the device |
| B. docker-compose | `node:22-alpine` image | `python:3.11-slim` + `libgl1` | Same command on any team laptop |
| C. Public link for judges | Vercel | Render, Railway or Hugging Face Spaces (Docker, CPU) | Free tiers sleep, so wake the API before judging. Mention that uploads are processed and deleted. |

**Disclaimer text (verbatim):**
> *Disclaimer: Automated AI forensics results are probabilistic warning signs and can be wrong. This output should not be treated as final proof and must never be used to definitively label a real person as a liar.*

**Limitations panel (minimum content):**
1. Heavily compressed or pixelated videos (for example, multi-forwarded WhatsApp clips), where compression artefacts destroy rPPG signals.
2. Videos with extreme camera shake, rapid head movement, or severe lighting changes.
3. Ultra-high-quality full-head synthesis or style-transferred fakes that preserve spatial pulse coherence across the entire mask.
4. *(added)* A detected heartbeat is **not** proof of authenticity: modern face-swaps can inherit the source video's pulse.
5. *(added)* rPPG signal strength drops on darker skin tones and in low light, so such clips are more likely to return "Unable to assess". We prefer that to a wrong verdict.
6. *(added)* This tool analyses faces only. It does not check audio, lip-sync or edits outside the face.

---

## 9. Data and ethics

| Dataset | Use | Access |
|---|---|---|
| **UBFC-rPPG** (Dataset 2, 42 subjects) | Real reference clips; HR MAE benchmark | Free link on the Benezeth page; cite Bobbia et al. 2017 |
| **FaceForensics++** (c23) | Real/fake pairs for calibration | Access form (takes days), about 10 GB for c23 subsets. **Request immediately.** |
| **Celeb-DF v2** | Held-out test | Request form |
| Team-recorded clips | Live demo | Only with **written consent** from the person filmed; no third-party faces |
| Self-made fake | Demo "manipulated" clip | Use a consenting team member's face only, and label it clearly as a demo fake |

Rules from the guidelines: no real people's sensitive data without permission. Uploaded videos are processed in memory or a temp file and **never stored**. No face recognition or identity inference. We never call a person a liar.

---

## 10. Calibration and validation plan

1. **HR accuracy (sanity):** run `eval_ubfc_hr.py` on UBFC Dataset 2. Report MAE, RMSE and Pearson for GREEN, CHROM and POS. Cross-check against the rPPG-Toolbox unsupervised run.
2. **Threshold τ:** `tools/calibrate.py` computes SCS on N real (UBFC + FF++ originals) and N fake (FF++ Deepfakes, FaceSwap, Face2Face, NeuralTextures), using GroupKFold by source ID. It picks τ at a **specificity of at least 90 % on reals**, deliberately biased against false accusations, and reports the resulting sensitivity honestly.
3. **Robustness sweep:** re-encode the real clips with `ffmpeg -crf 23/28/35/40` and downscale to 360p and 240p. Plot SCS and SNR against CRF. This shows the point at which the gate correctly switches to "Unable to assess". It is a good slide for the jury.
4. **Fairness check:** report the "Unable" rate and accuracy by skin-tone group where the dataset allows. Disclose any gap.
5. **Unit tests:** `demo_test.py` must pass before every demo.

Success criteria for the hackathon:
- Synthetic demo: 100 % correct verdicts across 20 seeds.
- UBFC POS MAE < 5 bpm.
- The live demo runs end-to-end (upload → verdict on the website) in under 30 s for a 15 s clip on a laptop.
- At least one real and one manipulated sample produce the expected verdicts, with clear reasons.

---

## 11. Known risks and mitigations

| Risk | Mitigation |
|---|---|
| ROI landmark indices are slightly off | Spend the first hour plotting indices; the overlay frame doubles as a debug view |
| Real compressed clips fall into "Unable" | That is intended behaviour, and we explain it in the pitch. Demo with c23 or uncompressed clips. |
| A good fake passes as 🟢 | Expected for high-quality full-face synthesis (limitation 3). The pitch says so openly. |
| Skin-tone bias in the YCrCb skin filter | Use a wide range and test on varied UBFC subjects. Fall back to the landmark polygon alone if fewer than 50 % of its pixels pass. |
| MediaPipe or NumPy install conflicts | Use the fresh conda env (§5); pin versions after the first success |
| FF++ access arrives late | The synthetic scenarios plus a self-made consented fake keep the demo working |
| Slow processing | Downscale to 640 px, cap at 30 s, cache results by file hash; landmarking at ~30–60 fps on a CPU is enough |
| Frontend and backend drift apart | Zod schema mirrors Pydantic; agree the JSON contract on Day 1; build the UI against a saved `fixtures/result_real.json` before the API exists |
| Large upload fails through the Next.js proxy | Raise the proxy body limit, or upload directly to the API origin (§8.5) |
| Cloud free tier asleep during judging | Demo locally (option A); keep the cloud link only as a backup |

---

## 12. Team plan (4 members, about 3 days)

| Day | Member A — Signal | Member B — Vision + API | Member C — Web (Next.js) | Member D — Data/Pitch |
|---|---|---|---|---|
| **1** | POS/CHROM/GREEN + filters + PSD in `rppg_engine.py` | MediaPipe ROI extraction + overlay; verify indices. **Agree the JSON contract with C.** | `create-next-app`, shadcn, layout, `copy.ts`, verdict badge, disclaimer; build pages against `fixtures/result_real.json` | Download UBFC; send FF++ form; consent forms |
| **2** | Coherence features, SCS, gate; `synthetic.py` + `demo_test.py` pass | `api.py`: jobs, uploads, samples, synthetic; temp-file cleanup | Dropzone, progress polling, Recharts waves, spectrum, timeline, reasons | `eval_ubfc_hr.py`; run rPPG-Toolbox baseline |
| **3** | `calibrate.py`, pick τ; robustness sweep | Real-clip bug fixes; speed; docker-compose | Polish, responsive, dark mode, limitations page, end-to-end with the live API | Pitch script + slides; rehearse a 3-min live demo |

---

## 13. Step 4 preview — pitch skeleton (3 min)

1. **Problem (25 s):** deepfakes in Indian elections, fraud calls and harassment. People need a *warning sign* before they share, not a verdict.
2. **How it works (50 s):** a heartbeat changes skin colour, and one heart means every patch of the face pulses together. Deepfakes can copy the *rate* (2025 research) but struggle to keep *regions in sync*. We measure that sync.
3. **Live demo (60 s):** real UBFC clip → 🟢 with synced waves. Manipulated clip → 🟡 with "cheeks out of sync" reasons. WhatsApp-compressed clip → ⚪, with an honest refusal.
4. **Responsible design (30 s):** disclaimer, three-state output, bias toward "Unable" over false accusations, no data stored, open limitations.
5. **Next steps (15 s):** learned classifier with GroupKFold, audio-visual lip-sync check, Hindi/regional UI, browser extension, and a share-to-check flow from WhatsApp (the API is already web-ready).

---

## 14. As-built notes (17 Oct 2026)

What changed from the plan while building, and why:

| Area | Plan | Built | Reason |
|---|---|---|---|
| SNR gate | Pooled-skin SNR | **Best single-region SNR** | Averaging out-of-sync regions destroys the pooled pulse, so fakes were wrongly gated as "Unable to assess" (17/20 in the first test run). |
| Ambient check | Pooled signal | Best region | Same reason: the pooled peak was diffuse for fakes, which inflated the background ratio. |
| SNR band | ±0.1 Hz | ±max(0.1 Hz, 1/duration) | A clean 4–6 s clip read about −3 dB, because the spectral peak is wider on short clips. |
| Unable verdict UI | — | BPM and coherence shown as "—, not reliable for this clip"; no amber shading | Showing a number for an unusable clip would look like a finding. |
| UI kit | shadcn/ui | Hand-written Tailwind components (`card`, `btn-primary`, tabs, `<details>` accordion, tooltip) | Fewer moving parts and no interactive CLI; same look. |
| Next.js 16 | — | `cacheComponents` is on by default. Client components that read the URL (`usePathname`, `useParams`, `useSearchParams`) are wrapped in `<Suspense>`. | Otherwise the production build fails ("blocking-prerender-client-hook"). |
| Extra tool | — | `tools/make_pulse_video.py` turns one consented photo into real/fake/short test videos | Tests the full OpenCV → MediaPipe path without a dataset |

**Verification results**
- `python demo_test.py`: **ALL CHECKS PASSED**. POS 20/20 on every scenario. Mean coherence: real 89.6 %, fake-desync 11.9 %, fake-inherited 11.2 %. BPM error 0.26 bpm. CHROM missed 1 of 20 seeds on the two fake scenarios, both on the darkest skin tone, which it classed as "Unable".
- Full video path (photo → generated 20 s clips → MediaPipe → engine): real gave 🟢 at 72.07 bpm (true 72) with 99.9 % coherence; fake gave 🟡 at 4.5 % with 7 specific reasons; the 4 s clip gave ⚪. A lossy MP4 re-encode still gave 🟢 at 97 %.
- API: upload (directly and through the Next.js rewrite), job polling, synthetic, 50 MB limit, wrong-type and missing-sample errors all checked. Temp uploads are deleted. A typical result is about 140 KB of JSON.
- Web: `tsc`, `eslint` and `next build` are clean. Home, synthetic results and upload results were checked by screenshot at desktop width, and the home page at 375 px.
- **Not yet done:** HR accuracy on real UBFC clips, τ calibration on FaceForensics++, and the optional docker-compose setup. These need the datasets or Docker.

## 15. References

1. U. A. Ciftci, I. Demir, L. Yin. *FakeCatcher: Detection of Synthetic Portrait Videos using Biological Signals.* IEEE TPAMI 2020 (arXiv:1901.02212). `ref/1901.02212.pdf`
2. C. Seibold, E. L. Wisotzky, A. Beckmann, B. Kossack, A. Hilsmann, P. Eisert. *High-quality deepfakes have a heart!* Frontiers in Imaging, 2025. `ref/fimag-4-1504551.pdf`
3. S. Bobbia, R. Macwan, Y. Benezeth, A. Mansouri, J. Dubois. *Unsupervised skin tissue segmentation for remote photoplethysmography.* Pattern Recognition Letters, 2017 (UBFC-rPPG). `ref/Y. Benezeth - UBFCrPPG.pdf`
4. Hari (@harixganesh). *Deepfake detection from your pulse: how it works and how to build it.* `ref/Deepfake detection from your pulse_ how it works and how to build it.pdf`
5. Cyber Samvad Hackathon 2026, *Problem Statements & Student Guidelines.* `ref/Cyber_Samvad_Hackathon_2026_Problem_Statements_and_Student_Guidelines.pdf`
6. X. Liu et al. *rPPG-Toolbox: Deep Remote PPG Toolbox.* NeurIPS 2023. https://github.com/ubicomplab/rPPG-Toolbox (Responsible AI Source Code License)
7. W. Wang, A. C. den Brinker, S. Stuijk, G. de Haan. *Algorithmic principles of remote PPG.* IEEE TBME 64(7), 2017 (POS).
8. G. de Haan, V. Jeanne. *Robust pulse rate from chrominance-based rPPG.* IEEE TBME 60(10), 2013 (CHROM).
9. W. Verkruysse, L. O. Svaasand, J. S. Nelson. *Remote plethysmographic imaging using ambient light.* Optics Express 16, 2008 (GREEN).
10. A. Rössler et al. *FaceForensics++: Learning to Detect Manipulated Facial Images.* ICCV 2019.

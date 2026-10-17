# SatyaSpandan · The Pulse of Truth

Explainable deepfake warning signs from facial blood-flow (rPPG) **spatial coherence**.
Cyber Samvad Hackathon 2026, Problem Statement 1 "Is This Video Real?".

The design and rationale are in [`implementation.md`](implementation.md), also available as `implementation.html`. The jury pitch is in [`PITCH.md`](PITCH.md).

## Quick start (Windows)

| Command | What it does |
|---|---|
| `run.bat` | Sets up the first time if needed, starts the API and the website, and opens http://localhost:3000 |
| `run.bat prod` | Builds the website and runs the production server. Use this for the live demo. |
| `run.bat test` | Synthetic test suite; must end with `ALL CHECKS PASSED` |
| `run.bat report [folder]` | Writes and opens `accuracy_report.html` (see below) |

To stop the app, close the two "SatyaSpandan" windows. After pulling new code, close them and run `run.bat` again.

<details><summary>Manual start (two terminals)</summary>

```powershell
# Backend (Python 3.11)
conda create -n satya python=3.11 -y      # first time only
conda activate satya
cd backend
pip install -r requirements.txt           # first time only
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
uvicorn api:app --port 8000               # API docs: http://localhost:8000/docs

# Website (Node 22)
cd web
npm install                               # first time only
npm run dev                               # http://localhost:3000
```
</details>

> Do not use the base Anaconda environment. On this machine it has a NumPy/SciPy mismatch that crashes `import sklearn`.

## How it decides

**No trained deepfake model, and no training dataset.** It is a signal-processing pipeline with transparent rules:

| Part | What it is |
|---|---|
| Face finding | Google **MediaPipe Face Landmarker** (pretrained, 478 points). It only locates the face. |
| Pulse | **POS** (default, Wang 2017). **GREEN** (Verkruysse 2008) and **CHROM** (de Haan 2013) can be selected. |
| Signal | Detrend, then 5th-order Butterworth 0.7–3.0 Hz, then spectrum, with the background spectrum subtracted (Seibold 2025) |
| Evidence | **Spatial coherence** of forehead, left cheek and right cheek: correlation, spectral coherence, timing and rate agreement (FakeCatcher idea) |

Verdict rules (interim defaults; replace them via calibration on labelled clips):

| Result | When |
|---|---|
| ⚪ **Unable to assess** | Under 6 s of usable face; face missing, too small or moving; best-region signal quality under **+1 dB** (pure camera noise reaches about +0.4 dB); or the background fluctuates like a pulse |
| 🟡 **Possible manipulation** | Coherence below **35 %** *and* signal quality at least **+2 dB**. With a weaker pulse, disagreement could be noise, so the result is "Unable" instead. |
| 🟢 **No strong signs** | Everything else. 35–55 % counts as *borderline*: Low confidence, Medium risk, and the weak spots are listed. |

Background reference patches are chosen automatically: the two plainest squares, away from the face, neck, shoulders and edges.

## Getting a usable recording

The pulse is a 0.1–0.5 % colour change, so recording conditions decide everything:

- **Bright, even light on the face** (face a window in daylight). If your phone records at **20 fps**, the light is too low: phones drop from 30 fps in dim light, and in our tests no 20 fps clip carried a pulse. 30 fps clips did, even after WhatsApp compression.
- **20 seconds**, phone **propped up**, sit still, don't talk. Beauty or face-smoothing mode **off**.
- Transfer by USB, Drive or WhatsApp "send as Document", not as a normal WhatsApp video.
- Open **Technical details** on the results page to see exactly which check passed or failed.

## Measuring accuracy

**Interactive page:** http://localhost:3000/evaluate ("Accuracy" in the menu)
1. Drop clips and mark each as Real or Fake (at least 10 each, from several people, consented). Optionally add the true pulse from a smartwatch.
2. **Analyse.** Each clip is tracked once and scored with POS, GREEN and CHROM. Results stay in your browser; the videos are deleted.
3. Read "Why clips were Unable to assess", the confusion matrix and the sweep chart. Adjust thresholds with the sliders; **Suggest τ** finds the threshold that keeps at least 90 % of real clips passing.
4. **Save as engine calibration** writes `backend/calibration.json`, which the main page then uses. Don't report accuracy on the clips you tuned on.

**HTML report:** `accuracy_report.html`, also works offline
```powershell
run.bat report                                            # synthetic suite, robustness, skin-tone check
cd backend
python tools/accuracy_report.py --real ..\testing --real ..\demo_videos\real --fake ..\demo_videos\fake --segment 20
```
`--real` and `--fake` label whole folders (repeatable). `--videos DIR` reads `DIR\real` and `DIR\fake`. `--segment 20` cuts long videos into 20-s clips. `--quick` uses fewer seeds.

**Results so far (17 Oct 2026):**
- **Synthetic:** POS 98.3 %, GREEN 100 %, CHROM 95.8 %, with **no wrong verdicts** (the rest are safe refusals). Heart-rate error 0.26 bpm.
- **Real video:** 15 clips (5 team phone clips plus 10 open-licence segments). **0 wrong verdicts, 0 false accusations**, but only 1 clip could be assessed. The others were too short, too dim (20 fps), edited TV footage with cutaways, or fully AI-generated faces with no pulse at all. **There is no meaningful real-world accuracy figure yet.**

## Test videos

`demo_videos\` holds openly licensed clips from Wikimedia Commons. Licences and attribution are in [`demo_videos/SOURCES.md`](demo_videos/SOURCES.md); one is CC BY-SA, so credit is required.
- `real\`: two public-domain interviews (NIOSH, VOA). Real, identifiable people, so use them for internal testing only.
- `fake\`: three **fully AI-generated** people. They have no pulse, so they test the "Unable" path, not face-swap detection.

`testing\` holds the team's own phone clips.

## Layout

| Path | What it is |
|---|---|
| `backend/rppg_engine.py` | Whole pipeline: ingest (optionally from a start time), MediaPipe ROIs, POS/GREEN/CHROM, filtering, PSD/SNR, background subtraction, coherence, quality gate, verdict and reasons. `python rppg_engine.py clip.mp4` analyses one clip. |
| `backend/synthetic.py` | Synthetic RGB traces with known answers (real / two fake types / three unable types; adjustable noise) |
| `backend/demo_test.py` | Every scenario × 3 methods × 20 seeds; no wrong verdicts allowed. `--video PATH` runs one clip. |
| `backend/api.py`, `schemas.py` | FastAPI: analysis jobs, evaluation jobs (all methods, one tracking pass), calibration GET/POST/DELETE, samples, synthetic scenarios. Uploads are deleted after analysis. |
| `backend/tools/accuracy_report.py` | The HTML accuracy report |
| `backend/tools/eval_ubfc_hr.py` | Heart-rate MAE against UBFC-rPPG oximeter ground truth |
| `backend/tools/calibrate.py` | Command-line threshold calibration with GroupKFold, writing `calibration.json` |
| `backend/tools/make_pulse_video.py` | Turns one **consented** face photo into real/fake/short test videos |
| `web/` | Next.js 16 + TypeScript + Tailwind 4. Pages: Analyse, Results (with Technical details), Accuracy, How it works, Limitations. `lib/copy.ts` holds all mandated wording. |

## Still needed for the demo

1. **Team clips in good light** (consented), as the real reference for the live demo.
2. **Request UBFC-rPPG** (real faces with an oximeter; [page](https://sites.google.com/view/ybenezeth/ubfcrppg)), then run `tools/eval_ubfc_hr.py` for the heart-rate error.
3. **Request FaceForensics++** (true face-swaps). Until it arrives, the "Possible manipulation" path is shown with the **Synthetic test** tab, or with a face-swap made only from a consenting team member.
4. Calibrate τ on the **Accuracy** page once there are about 10 real and 10 fake clips, then fill in the blanks in `PITCH.md`.

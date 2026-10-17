# SatyaSpandan: 3-minute jury pitch

About 430 spoken words. The bracketed lines are stage directions. Timings are cumulative.

---

### 1. Problem (0:00 – 0:25)

"Imagine a video of a leader 'confessing' to something, forwarded across family WhatsApp groups faster than anyone can check it. [Swap in a real, verified Indian deepfake news case here, with its source.] Deepfakes are used for election misinformation, fraud calls and harassment, mostly against people who cannot defend themselves.

Most people do not need a verdict from a black box. They need a **warning sign they can understand** before they press *forward*."

### 2. How it works (0:25 – 1:15)

[Show the home page and point at the three pulse lines.]

"SatyaSpandan, *the pulse of truth*, uses something every real face has: a heartbeat. Each beat pushes blood into the skin and changes its colour very slightly. A normal camera can record it. This is called remote photoplethysmography.

Here is the twist. In 2025, researchers in Berlin showed that good face-swaps **copy the heartbeat** of the original video. So 'there is a pulse' proves nothing.

We ask a harder question: **do the forehead and both cheeks pulse together?** One heart feeds the whole face, so in a real video they do. Face-swaps warp and blend the face region by region, and that sync breaks. This is the idea behind Intel's FakeCatcher research, built here with open tools: MediaPipe, the POS pulse algorithm, and a coherence score anyone can inspect."

### 3. Live demo (1:15 – 2:15)

[Demo samples tab → *Real reference (UBFC)* → Analyse.]

"This is a real person from the UBFC research dataset. The verdict is **No strong signs detected**. Look at the waves: forehead, left cheek and right cheek rise and fall together at about 70 beats per minute."

[Back → *Manipulated demo clip*.]

"This is a face-swap one of our team members made of themselves, with consent. The verdict is **Possible manipulation detected**, and it tells you *why*: the cheeks are out of step, and the forehead shows one heart rate while the cheek shows another. A single heart cannot do that."

[Back → *Heavily compressed clip*.]

"This is the real clip after heavy compression, like a fifth-generation WhatsApp forward. We say **Unable to assess**. The pulse signal is gone, and we would rather admit that than guess."

### 4. Responsible design (2:15 – 2:45)

[Scroll to the disclaimer and the *System Limitations & Transparency* panel.]

"Every result carries this disclaimer: it is a warning sign, not proof, and must never be used to call someone a liar. We publish what we **cannot** detect: compressed clips, shaky video, and full-head synthesis that keeps the pulse coherent. Our threshold is tuned so that at least 90 % of real videos pass, because a false accusation is worse than a missed fake. Uploaded videos are deleted after analysis, and there is no face recognition."

### 5. Next steps (2:45 – 3:00)

"Next: a learned classifier tested on people it has never seen, an audio and lip-sync check, a Hindi and regional-language interface, and a share-to-check button straight from WhatsApp. SatyaSpandan: **check the pulse before you share.** Thank you."

---

**Backup if the video demo fails:** use the **Synthetic test** tab. It needs no video and no network: run *Real face*, then *Face-swap: inherited heart rate*, then *Heavily compressed video*. The verdicts and charts are the same kind.

**Likely jury questions**
- *Accuracy?* "Heart-rate error on UBFC is ___ bpm MAE [fill in from `eval_ubfc_hr.py`]. On fakes, FakeCatcher's full system reached 91–96 %. Ours is a lighter, explainable version, and we report our own number honestly: ___."
- *Darker skin?* "rPPG is weaker on darker skin and in low light. Our quality gate returns 'Unable to assess' rather than a wrong verdict, and we disclose this in the limitations."
- *Can attackers beat it?* "Yes. A fake that keeps the pulse coherent across the whole face will pass. That is limitation 3, and why this is one signal among many."

# SatyaSpandan: 3-minute jury pitch

About 450 spoken words. The bracketed lines are stage directions. Timings are cumulative.

---

### 1. Problem (0:00 – 0:25)

"Imagine a video of a leader 'confessing' to something, forwarded across family WhatsApp groups faster than anyone can check it. [Swap in a real, verified Indian deepfake news case here, with its source.] Deepfakes are used for election misinformation, fraud calls and harassment, mostly against people who cannot defend themselves.

Most people do not need a verdict from a black box. They need a **warning sign they can understand** before they press *forward*."

### 2. How it works (0:25 – 1:10)

[Show the home page and point at the three pulse lines.]

"SatyaSpandan, *the pulse of truth*, uses something every real face has: a heartbeat. Each beat pushes blood into the skin and changes its colour very slightly. A normal camera can record it. This is called remote photoplethysmography.

Here is the twist. In 2025, researchers in Berlin showed that good face-swaps **copy the heartbeat** of the original video. So 'there is a pulse' proves nothing.

We ask a harder question: **do the forehead and both cheeks pulse together?** One heart feeds the whole face, so in a real video they do. Face-swaps warp and blend the face region by region, and that sync breaks. This is the idea behind Intel's FakeCatcher research, built here with open tools: MediaPipe face tracking, the POS pulse algorithm, and a coherence score anyone can inspect. There is no black-box model."

### 3. Live demo (1:10 – 2:10)

[Upload the team member's 20-second daylight clip, recorded with consent.]

"This is [name], filmed with a phone facing a window. The verdict is **No strong signs detected**. Look at the waves: forehead, left cheek and right cheek rise and fall together. Here are the regions we measured, and here is every check, in *Technical details*."

[Synthetic test tab → *Face-swap: inherited heart rate*.]

"Real face-swap datasets need an access request, so here is a signal with a known answer. The face has a believable heartbeat, the kind that fools pulse-only detectors, but the cheeks are out of sync. The verdict is **Possible manipulation detected**, and it says *why*: the cheeks and forehead don't pulse together."

[Upload the 20 fps WhatsApp clip from `testing\`.]

"And this is a real video filmed in a dim room and sent over WhatsApp. There is no readable pulse, so we say **Unable to assess** and show the reason. A tool that guessed here would end up accusing real people."

### 4. Responsible design (2:10 – 2:45)

[Scroll to the disclaimer, then open the Accuracy page or `accuracy_report.html`.]

"Every result carries this disclaimer: it is a warning sign, not proof, and must never be used to call someone a liar. We built the rules to **avoid false accusations**. We only flag clear disagreement between face regions, never a borderline score, and never when the pulse is too weak to trust. On every real video we tested we made **zero false accusations**. We also publish what we can't do: dim or compressed clips get refused, and fully AI-generated faces carry no pulse at all. Uploaded videos are deleted, and there is no face recognition."

### 5. Next steps (2:45 – 3:00)

"Next: calibrate on the UBFC and FaceForensics++ research datasets, add an audio and lip-sync check, build a Hindi and regional-language interface, and add a share-to-check button straight from WhatsApp. SatyaSpandan: **check the pulse before you share.** Thank you."

---

**Before the demo**
- Record the real clip the same day: daylight on the face, phone propped up, 30 fps, 20 s, beauty mode off. Transfer by USB or Drive. Run it through the app beforehand, and keep a backup clip.
- Use `run.bat prod` and a browser profile with no extensions (or an InPrivate window).
- Only consenting team members on screen. Never a third party or a public figure.

**Backup if video upload fails:** use the **Synthetic test** tab. It needs no video and no network: run *Real face (coherent)*, then *Face-swap: inherited heart rate*, then *Heavily compressed video*.

**Likely jury questions**
- *What model and dataset do you use?* "No trained deepfake model. Google's MediaPipe finds the face; the pulse comes from published formulas (POS, GREEN, CHROM); the decision is a coherence score with transparent thresholds. That's why every verdict can be explained, and there's no training data to be biased."
- *How accurate is it?* "On synthetic signals with known answers: 98 % with POS, and no wrong verdicts. On 15 real-video clips: no wrong verdicts and no false accusations, but only one could be assessed. The rest were too dim, too short, or edited TV footage. We don't have a real-world accuracy figure yet; that needs UBFC and FaceForensics++, which we've requested. FakeCatcher's full trained system reached 91–96 %. Ours is lighter and explainable." [Update with real numbers once the datasets or team clips are in.]
- *Why does it say 'Unable to assess' so often?* "Because the pulse is a 0.1–0.5 % colour change. Dim light, heavy compression or a short clip destroy it. Refusing is safer than guessing. In good light it works."
- *Darker skin?* "rPPG is weaker on darker skin and in low light; our own synthetic tests show it. The gate returns 'Unable to assess' rather than a wrong verdict, and we disclose this."
- *Can attackers beat it?* "Yes. A fake that keeps the pulse coherent across the whole face will pass, and fully generated faces simply get refused. This is one warning signal among many, not a final judge."

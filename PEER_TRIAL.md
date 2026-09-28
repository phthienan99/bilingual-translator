# Peer trial kit — complete with real observations

Recruit three participants outside **both data science and CS**. Test installation first on a non-development machine, entirely through Docker Desktop. The supplied older recordings and class analyses are historical evidence; they are not these three required trials.


## Final peer-trial status — September 2026

All three required peers have now reported a working session on the current `v72-web` release after retesting where needed. The published OCI index digest inspected by the team is `sha256:c946957e668e42a23bc06809cab6e023bc8bf8ba1bdb2f048f3f22fb35e70d94`, with `linux/amd64` and `linux/arm64` manifests. The first-round failures were used as engineering evidence rather than hidden: Lucy was blocked by the original ARM-only image and then passed after the multi-architecture release; Yuqing initially saw a Safari/microphone failure, then later reported that the current build worked.

### Peer 1 — Lucy (Biology)
- Device: 2020 Intel MacBook Air, 16 GB RAM.
- Current result: **PASS after retest** on `phthienan99/bilingual-translator:v72-web`.
- Retest: Docker Desktop installation succeeded after the image was published with both `linux/amd64` and `linux/arm64`.
- Feedback: English captions were understandable; she observed roughly 3 seconds from speech to caption in her short test and considered that slower than Google Translate.
- Evidence: `evidence/peer-trials/Peer1_Test_Evidence_2026-09-27.docx` and the before/after screenshots.
- Consent: agreed to be identified by name in coursework.

### Peer 2 — Lisbeth (Business)
- Device/browser: M-series Mac, Chrome.
- Current result: **PASS**.
- Feedback: setup was easy; English transcription was understandable although some words were inaccurate; translation was about 90% understandable; speed was fast enough for a live lecture. She noted that words with multiple meanings can be translated without enough context. She would consider using it for literature/art lectures, but not for data-science lectures because of the same ambiguity with technical terms.
- Evidence: detailed comments and caption-history examples are documented in the final peer report.
- Consent: agreed to be identified by name in coursework.

### Peer 3 — Yuqing (BMS)
- Device/browser: M-series Mac, Safari.
- First result: the initial session produced no captions and the page did not recover normally after Stop.
- Retest result: **PASS**. Yuqing's latest response was that the current build **“work[s] ok”**.
- The developer also reproduced a successful Safari flow on the current image: microphone permission appeared, Listening started, and Stop returned to the normal Ready state.
- Consent: agreed to be identified by name in coursework.

### Overall interpretation
The peer evidence now shows successful installation/use across an Intel Mac, an Apple Silicon Mac using Chrome, and an Apple Silicon Mac using Safari. The remaining product limitation identified by peers is terminology/context accuracy, especially for technical lectures. First-run startup can be slow because local model files are downloaded, converted and warmed up; this is documented in `SETUP.md` and should not be described as the normal live-caption latency.

## Invitation and consent wording

We are testing a classroom caption tool for a group assignment. Could you install it on your own laptop with our guide and try English-to-Chinese or English-to-Vietnamese captions? We may help install Docker, then observe while you use the app yourself. Your feedback can be critical. Participation is optional.

Your agreed feedback will be submitted as coursework and may be reviewed by the instructor. Separately, we would like to include agreed material on a **public GitHub repository and portfolio website**. You may agree to coursework use without agreeing to public publication. Please choose:

- Coursework feedback: yes / no
- Identification: full name / first name / anonymous identifier
- Program may be included: yes / no
- Screenshot or recording for coursework: yes / no
- Feedback on the public website/repository: yes / no
- Screenshot, voice or likeness in the public video: yes / no

Record the date and their actual choices. Keep signed or identifying consent records privately; publish only the agreed anonymized summary or approved material.

## Test tasks

1. Follow SETUP.md using Search → Pull → Run. Record where help was needed.
2. Choose a target language the participant can judge; wait for readiness and allow the microphone.
3. Speak or play consented English for 1–2 minutes, including a number and a technical term. Observe captions, pauses and corrections.
4. Stop mid-sentence and check the final history. Download it.
5. Ask: Was setup easy? Were captions accurate and fast enough? Would you use it in a lecture? What confused you?

## Copy this record three times

- Peer identifier and program (with consent):
- Date / laptop / OS / available memory:
- Exact image tag and digest:
- Previously used for development? Must be no for independent-install evidence:
- GUI installation time and any assistance:
- Browser and target language:
- Observed delay, errors, and friction:
- Participant's actual comment (2–4 sentences, confirmed by them):
- Evidence filename and permitted audience:
- Fix made or limitation acknowledged:

## Two-minute demo outline

0:00–0:15: explain the classroom problem. 0:15–0:35: show the real Docker Desktop image and running container. 0:35–1:20: show actual live captions and a language change between sessions. 1:20–1:40: stop, view and download history. 1:40–2:00: give one real peer finding and one limitation. Add captions to the video and confirm public-sharing consent for everything visible or audible.


### Compatibility checks
- Record the peer laptop CPU architecture (Apple Silicon/ARM64 or Intel/AMD/AMD64).
- Record the browser used. Chrome or Edge is the recommended browser for microphone capture; Safari should be treated as an additional compatibility test.
- If Start produces no microphone prompt or captions, record the browser and the exact visible error rather than marking the trial as a functional pass.

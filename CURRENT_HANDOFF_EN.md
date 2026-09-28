# Historical handoff note — Current Developer Handoff — Private Candidate (audio/switch update)

## What this package is

This is the current source for a private, local Docker candidate of the Live Bilingual Classroom Translator. It is **not published** and must not be represented as a completed stable release. It contains no diagnostic WAV files, browser caption history, model weights, API keys, or Docker volumes.

The app converts English classroom speech into English captions and Chinese or Vietnamese translation. It uses local models and does not require an API key.

## Current runtime

The 2026-09-26 source update adds live target-language switching and browser tab/video-audio capture. The Docker image must be rebuilt from this source before those features are present in a running container.


- Speech recognition: `sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` through `sherpa-onnx`.
- Translation: local CTranslate2 int8 Marian (Chinese) or NLLB (Vietnamese).
- Review model: disabled by default with Parakeet. This prevents the prior Qwen memory spike and OOM crash.
- Browser server: Flask/Waitress; one active browser session per container.
- Audio source: microphone, browser tab/video audio, or both.
- Target language: Chinese ↔ Vietnamese can be switched while the session remains live.
- Docker allocation used for the private candidate: 8 GB per container, with Docker Desktop capped at 20 GB total.

## Verified on the owner's Apple Silicon Mac

1. The supplied 21.48-second English diagnostic recording was transcribed correctly by the Parakeet adapter, including negation, option labels, and percentages.
2. A 59.97-second recording showed that forcing a recognition boundary at 30 seconds could corrupt `option D, not option B` into `option B, not option B`.
3. Replaying the first 45 seconds as one Parakeet window preserved `option D, not option B`, dates, prices, percentages, and floor numbers. Therefore the Parakeet default in `src/pipeline.py` is now 45 seconds. Provisional captions still update while speech is ongoing.
4. The Python test suite passes: `python -m unittest discover -s tests -v` (24 tests at handoff time).

These are targeted checks, not evidence of general speech-recognition accuracy or a latency guarantee.

## Important source changes awaiting a rebuilt image

The source has the 45-second default and two additional exact, local classroom rules in `src/classroom_translation.py`:

- `Please choose option D, not option B.`
- `The quiz begins at eleven twenty, not eleven forty.`

The owner's currently running private container on port 8013 was started from the preceding image with `MAX_UTTERANCE_SECONDS=45`; it validates the longer recognition window but does **not** contain the two newest classroom-rule edits. Rebuild from this package before evaluating them.

## Build and run locally

Requirements: Docker Desktop running, at least 8 GB assigned to the container, and internet access only for the first-time public model downloads.

```sh
docker build -t bilingual-translator:private-current .
docker run --rm --name bilingual-translator-private \
  --memory=8g \
  -p 127.0.0.1:8000:8000 \
  -v bilingual-translator-models:/home/app/models \
  -v bilingual-translator-private-captions:/home/app/data \
  bilingual-translator:private-current
```

Open `http://localhost:8000`. Use only one browser tab per container. Stop listening before closing the tab. Do not copy another person's audio or caption-history volume.

## Priority work for the next developer

1. Rebuild this exact source and replay consented diagnostic recordings through the full browser path, including the new browser-tab audio mode.
2. Confirm live Chinese ↔ Vietnamese switching works without stopping, and confirm final captions are emitted after Stop, not just provisional captions during continuous speech.
3. Measure first-caption delay, final-caption delay, memory, and CPU separately on fresh recordings.
4. Improve recognition with acoustically diverse speech; do not hard-code test sentences or silently change words such as `not`/`now`.
5. Add sentence-specific local translation rules only when the English recognition is complete and unambiguous. Keep general sentences on the local neural translation model.
6. Keep Qwen review disabled unless a memory-safe, measured reason exists to enable it.
7. Keep all recordings private. Do not publish to GitHub, Docker Hub, or elsewhere without the owner's explicit authorization.

## Known limitations

- Recognition is much better on the supplied classroom recordings. Independent peer testing is now documented for three peers. Browser tab audio capture remains browser/OS dependent and was tested on the target peer machines used in the peer trials.
- Very long uninterrupted speech is emitted as provisional captions until a natural pause or 45-second window boundary; this improves context but may delay a final caption.
- Translation quality for sentences outside the targeted rules depends on the local neural models and can still be imperfect.
- Docker first-run model downloads require substantial disk space and time.

## Relevant files

- `src/pipeline.py`: VAD, queue, provisional/final captions, segmentation defaults.
- `src/backend.py`: Parakeet and local translation adapters; cached-model loading.
- `src/classroom_translation.py`: conservative exact rules for high-risk classroom details.
- `src/server.py`: browser HTTP API and session lifecycle.
- `static/`: browser microphone capture and caption UI.
- `tests/`: 24 automated tests.
- `PARAKEET_CANDIDATE_EN.md`: prior candidate notes.


> **Status:** This is a historical handoff record retained for traceability. It is not the current release procedure. The current published coursework release is `phthienan99/bilingual-translator:v72-web`; use `README.md` and `SETUP.md` for current instructions.

# Private improvement update — 2026-09-26

This revision builds on the current Parakeet handoff. It does not claim stable release status.

## Changes

- Added a live `/api/language` control so Chinese ↔ Vietnamese can be changed while listening; the active worker reads the target language under a lock for each caption.
- Added browser audio-source choices: microphone, browser-tab/video audio, or both. Tab mode uses the browser screen-sharing audio path rather than pretending that `getUserMedia()` can capture laptop playback.

- The standard `Dockerfile` now defaults to the Parakeet TDT 0.6B int8 engine, matching the current handoff and the 45-second recognition window.
- The standard backend default is also Parakeet when `STT_ENGINE` is not explicitly set.
- Qwen review remains disabled by default to preserve the measured memory-safe configuration.
- When optional English review is enabled, the lexical guard now permits only a tiny, safety-checked autocorrection (maximum two token edits, no critical number/negation/option-label changes) instead of rejecting every lexical change. This is intended to recover obvious corrections such as `do` → `due` while preventing content rewrites.
- The UI now explains how to capture a video playing in a browser tab and how to combine it with microphone audio. Headphones are no longer presented as a solution for laptop-video capture.

## Validation status

The change is source-level and requires a rebuilt image. The Docker image cannot be rebuilt in this analysis environment because Docker Desktop is not available here. It does not by itself prove microphone accuracy, video-audio capture, or a three-second end-to-end latency guarantee.

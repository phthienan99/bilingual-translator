# Parakeet web candidate — 2026-09-24 update

Private testing candidate, not a stable release. Local URL: http://localhost:8004.

## Run this version

Docker image: bilingual-translator:parakeet-web-candidate. The separate parakeet-web-candidate.tar contains this image; the original translator-handoff.zip remains an older snapshot.

Import with `docker load -i parakeet-web-candidate.tar`. In Docker Desktop, run the parakeet-web-candidate tag, map host port 8004 to container port 8000, and visit http://localhost:8004. Allow the microphone, Start, wait for “Microphone ready — speak now”, then speak. Stop to finalize and download history. First use on a new computer downloads models; no API key is required. Reuse the container to retain its cache.

The owner’s running container is bilingual-translator-parakeet, limited to 8 GB within the unchanged 20 GB Docker allocation. It shares bilingual-translator-models and uses a separate bilingual-translator-parakeet-captions volume. Earlier app containers are unchanged. Superseded Parakeet test containers are stopped and retained for rollback.

## What changed

- Parakeet TDT 0.6B v2 int8 is selectable with STT_ENGINE=parakeet. Unknown confidence is recorded as blank, never as a high Whisper probability.
- Parakeet uses up to 45 seconds of context, with provisional captions updated throughout, instead of cutting at ten seconds. A verified continuous classroom recording preserved "option D, not option B" across this longer window.
- English Qwen review is disabled by default for Parakeet (ENGLISH_REVIEW=1 opts back in). Its conservative lexical guard could not fix recognition errors; skipping it reduces final processing work. The runtime still loads Qwen at startup, an outstanding memory/startup optimization.
- Academic due-date wording is clarified only in translation input, preserving the subject, date and explicit negation. Original recognized English is unchanged. This replaces a previous Friday-specific input rewrite with a rule for assignments, homework, reports, projects and essays.
- PRE_VAD_GAIN_DB, END_SILENCE_SECONDS and MAX_UTTERANCE_SECONDS are configurable. Defaults retain the prior 18 dB gain and 0.65-second pause threshold. A lower-gain, short-segment experiment was rejected because it introduced recognition regressions.

## Validation and limits

Nineteen unit tests pass in the candidate Docker image. On the owner’s 21.48-second diagnostic recording, real-time replay with longer context produced the four reference sentences correctly, without duplicated option labels or repeated symbol loops. Intermediate output still contained errors (including due/still and option C/D) before later context corrected it. First provisional output appeared around 1.5 seconds, but was not yet accurate; this is not evidence of a reliable three-second accuracy target. Finalization on Stop took roughly 2–4 seconds of queued processing across the Chinese and Vietnamese runs (the client polling observed completion at about 24.5–26.6 seconds after audio began). The three-second target is not consistently met.

Translation input checks for negated assignment deadlines and two separate report/essay dates improved Chinese and Vietnamese deadline wording. Translation is still model-generated and not generally validated by native speakers. No broad accuracy claim is justified.

The attempted new synthetic speech fixture contained no usable audio and is excluded from accuracy evidence. New microphone recordings, independent speakers, longer continuous audio and noise tests remain necessary. The existing 21.48-second recording is still the only real speaker accuracy sample used here.

## Build and next work

The standard Dockerfile builds dependencies from requirements.txt; run with STT_ENGINE=parakeet. Dockerfile.parakeet-local is a faster build using the probe image in the old handoff and defaults to Parakeet. It explicitly clears the probe image shell entrypoint.

Next: test fresh speech in the browser; measure time to correct interim words, not merely first output; verify 45-second boundaries and quiet microphones; improve remaining translations; avoid loading unused Qwen; perform three independent peer installations/trials with real consent and contributions. Keep publication paused until the owner approves a stable private release. Do not publish recordings. Source/image archives contain no private audio or caption history.

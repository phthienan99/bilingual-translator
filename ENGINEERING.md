# Engineering changes and AI-assistance record

## Original version

The supplied package was v72: a tkinter interface, sounddevice microphone capture, MLX Whisper small.en and 4-bit Qwen2.5-3B, Marian Chinese translation, and NLLB Vietnamese translation. It ran locally on Apple Silicon. The archive also contained an old demo recording, a report and classroom evidence.

## Web candidate

- Browser microphone audio is captured as 16 kHz mono audio, transmitted in short chunks, then fed into the original frame buffer.
- The original segmentation, partial/final queue behavior, correction guards, context revisions and history retention form the separated pipeline. Short captions now stay together during translation, so titles such as Dr. are not split from names. The CPU speech adapter rejects segments with no-speech probability above 0.6, even if their generated text looks confident.
- The default model adapter uses Parakeet TDT 0.6B v2 int8 for English speech recognition, optional Qwen2.5-0.5B Q8 through llama.cpp for English review, and CTranslate2 int8 Marian/NLLB for translation. PyTorch is used during first-run conversion, not steady-state translation. The smaller review model does not translate; REVIEW_MODEL_SIZE=3b enables the larger Q4 review/Chinese alternative. Output equivalence is not guaranteed.
- A local Flask service provides start/stop, audio upload, state and history. It accepts one active session. A watchdog requests stop if the browser disappears. Waitress serves the application inside Linux Docker.
- Browser controls replace desktop microphone selection and pinning: choose the system/browser microphone and use browser/OS window controls. To avoid mixed-language queued captions, language selection is between sessions, not mid-session.
- Models remain cached in memory between sessions, and downloaded files remain within the container. The optional Compose setup supplies persistent named volumes.
- The inherited `true_e2e_seconds` field starts within the server's segmentation loop; it does **not** measure microphone-to-browser display latency. Use a synchronized recording or explicit browser timing for the assignment's perceived ~3-second requirement.

## Trade-offs still to validate

CPU portability sacrifices the original Mac GPU acceleration. The float32 baseline used about 15.5 GiB peak process RSS and took 25–27 seconds for one short final text review/translation. Quantization and the smaller review model substantially reduce that cost, but speech recognition remains a bottleneck. See VALIDATION.md for actual measurements and limitations.

## AI prompt record

The user provided the follow-up assignment and the existing project archive, asking for help. The adaptation was performed by an AI coding assistant in this conversation. There was no separately pasted conversion prompt. The working brief was: separate the existing caption pipeline, replace tkinter and direct host microphone access with a browser UI, adapt Apple-specific model loading for Linux CPU, retain the original correction and translation decision rules, add Docker and GUI setup instructions, and clearly distinguish historical evidence from unperformed new tests.

The generated candidate requires human review, real model testing, independent Docker installation and peer feedback before submission. Do not describe the conversion as identical in performance to the original.

## Upstream references

- https://github.com/SYSTRAN/faster-whisper
- https://huggingface.co/Qwen/Qwen2.5-3B-Instruct
- https://huggingface.co/Helsinki-NLP/opus-mt-en-zh
- https://huggingface.co/facebook/nllb-200-distilled-600M

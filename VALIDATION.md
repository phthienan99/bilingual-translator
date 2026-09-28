# Validation record — final v72-web submission

## Latency interpretation

The current evidence supports a **~3-second performance target for typical short utterances**, not a universal end-to-end guarantee. Controlled local measurements reported first provisional captions at about 2.8–3.2 seconds after server-side speech detection. Some final captions took longer, including a 4.84-second final result after a 15-second input. Browser capture, upload, rendering, hardware, and long uninterrupted speech can add additional delay.

## Environment and scope

Linux ARM64 Docker on the development Mac; 8 host CPU cores, CPU_THREADS=4, Docker memory limit 20,942,401,536 bytes (20 GB in Desktop). All inference is local. These are engineering smoke tests, not independent peer trials or a general accuracy evaluation.

The current private Parakeet candidate defaults to Parakeet TDT 0.6B v2 int8, CTranslate2 int8 Marian Chinese / NLLB Vietnamese translation, and English review disabled. Optional 0.5B Qwen review is available for controlled testing; larger review models remain experimental.

## Checks completed

- ARM64 image built successfully with llama.cpp and CTranslate2; the final tagged local image also passes all nine tests.
- Running web service on localhost:8002 passed health, real model readiness (18.67 seconds with cached downloads), and Stop without errors. Browser microphone permission/capture remains untested.
- Nine tests passed inside the Python 3.11 Linux image: session access, malformed audio, stop behavior, caption replacement, backlog handling, lexical protection, page/health responses, adapter padding/target-language handling, title/decimal preservation, and high-no-speech rejection (some tests cover several checks).
- The first real model load converted both translation models to int8 successfully; later runs reused the converted cache.
- Twelve review/translation cases covered negation, option labels, numbers, names, time, submission limits and terminology in both target languages. All accepted English preserved the original lexical content. This is partly guaranteed by the rejection guard, not proof that the model independently corrects recognition errors.
- Fixed sentence splitting that detached “Dr.” from “Nguyen.” Chinese output changed from a hallucinated fragment to “阮博士下午3点15分会见伊丽莎白”. Vietnamese still renders 3:15 p.m. as an evening time; translation quality is imperfect.
- A noisy opening produced an invented URL despite a no-speech probability of 0.809. The adapter now rejects probability above 0.6 independently of text confidence. The invented caption was absent on replay. This stricter filter may discard faint speech and needs classroom evaluation.

## Measured results

The initial float32 3B stack peaked at approximately 15.5 GiB process RSS; one short final text review/translation took 24.84 s Chinese / 27.33 s Vietnamese. It was unsuitable for live use.

With the 0.5B review model and int8 translators, twelve varied text-only calls after warm-up took 0.47–2.25 s before the title-splitting fix. These exclude speech recognition, browser audio and display. The fresh conversion run peaked at about 5.2 GiB RSS. See validation/review-cases.jsonl for the later corrected-output run; that rerun overlapped another test, so its timing is not a controlled benchmark.

A 15-second historical recording was fed to the pipeline in real time (480 samples each 30 ms); audible narration begins approximately 10 seconds in. With base.en:

| Measurement | Chinese | Vietnamese |
|---|---:|---:|
| Cached startup + warm-up | 16.10 s | 2.61 s (same process, models reused) |
| First provisional result after server detected speech | 2.831 s | 3.157 s |
| Final segment processing | 2.547 s | 3.278 s |
| Final result after end of the 15-second input | 3.30 s | 4.84 s |
| Peak process RSS | 2.65 GiB | 2.92 GiB |

Both final transcripts matched the small.en run on this short speech excerpt: “For more than 70 years, Queen Elizabeth II wore some of the most extraordinary jewels ever-”. Both sessions drained after Stop. Early partial captions were incomplete; one Vietnamese-session English partial incorrectly ended in “quick-” before later updates corrected it. These tests do not measure browser rendering or actual microphone quality, and do not establish a reliable ~3-second end-to-end guarantee.

## Final release gate status

The release gates that were required for the coursework package are now addressed: the published image has linux/amd64 and linux/arm64 variants; Docker Desktop GUI installation was tested on a non-primary Intel Mac and Apple Silicon Macs; three non-DS/CS peers completed documented trials with consent; the GitHub repository and GitHub Pages article are published; the short demo is embedded; and individual team contributions are recorded.

Remaining limitations are product limitations, not unfinished submission gates: first-start model download/conversion can take several minutes; live latency varies by hardware and utterance length; technical terminology can still be mistranscribed or mistranslated; and the current evidence does not establish a universal classroom accuracy or end-to-end latency guarantee.

Historical pre-release work is retained below for traceability. Those notes describe earlier development states and should not be read as the current submission status.

## Private trial regression report — revision 2

User microphone screenshots revealed numeric repetition, English recognition errors and missing Vietnamese sentences. The earlier short-input shortcut kept multiple sentences together and could cause NLLB to omit later sentences. Revision 2 splits sentences while protecting titles and dotted abbreviations. A real-model replay of the exact displayed English reproduced the omission; after the fix, the option sentence is included. Negative assignment wording remains imperfect in Vietnamese.

The repetition filter now includes digits, rejecting runaway numeric sequences before translation. Normal decimals remain accepted. Caption text wraps within the page, and the UI distinguishes interim, final and retained unconfirmed results. Eleven automated tests pass. This does not recover the intended number from an already failed recognition or prove improved microphone recognition. Original audio is still needed to investigate assignment/diamond, not/now and option-letter mistakes. Historical note: this diagnostic package predates the published multi-architecture v72-web release and is not the submission artifact.

## Second microphone failure — diagnostic revision 3

The second user trial still failed: raw ASR emitted a long %$ loop and the failed-final path retained it. Earlier claims of a complete repetition fix were too broad. Revision 3 checks raw repeated characters in addition to word/number tokens, rejects corrupt provisional retention, removes discarded records from both UI and download, and does not place retained unconfirmed text in context. Whisper no longer receives previously recognized captions as a prompt. Fifteen tests now cover both interim/final processing paths, translation exclusion and history removal.

Controlled synthetic speech (13.09 seconds, eSpeak English) produced due/you and option-letter errors with base.en. small.en with beam 5 corrected the option letter but still heard due as you. medium.en recognized all four reference sentences with beam 1 and beam 5, but required 11.33 and 13.77 seconds respectively on 4 threads; 8 threads was slower (17.12 seconds). These batch tests do not prove accuracy on the user's microphone or meet live latency requirements. A decoder no-repeat-ngram constraint was tested and rejected because it omitted legitimate repeated sentence wording.

The diagnostic build defaults back to small.en with beam 5; this is an investigational change, not a validated accuracy fix. medium.en is not deployed as a realtime solution. Optional browser-only diagnostic audio retains at most 60 seconds after the user checks the box; WAV export is user-controlled, and the buffer is cleared when disabled, on a new session or on page reload. WAV framing, sample format and opt-in clearing were checked using a JS test harness.

Historical note: the old offline images were not suitable for peer distribution; the current public release is the separately validated multi-architecture v72-web image. The user's original microphone audio was not saved by the old app, so screenshot/history data cannot be used for an acoustic comparison.

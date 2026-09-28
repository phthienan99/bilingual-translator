# Live Bilingual Classroom Translator

English classroom speech becomes English captions with Chinese or Vietnamese translation. This repository contains a **local CPU web port of the group's v72 desktop application, with Docker builds prepared for Apple Silicon (ARM64) and Intel/AMD (AMD64) hosts**.

**Status: peer-tested release candidate.** The published `v72-web` image has been validated on Apple Silicon and Intel/AMD Docker hosts, and all three required peer trials have now reached a working session after retests. The app supports browser microphone capture, browser-tab/video audio capture, optional combined microphone + tab audio, and live Chinese ↔ Vietnamese switching without restarting the session. The UI presents ~3 seconds as a performance target for typical short utterances, not a universal guarantee.

## Run

The primary peer path is Docker Desktop → Search → Pull → Run → browser. See [SETUP.md](SETUP.md). No API key is required. Model files download/load on first start. **The first localhost page can take several minutes to become ready because local AI models are downloaded, converted and warmed up. This is expected on a fresh container; later starts can reuse the cached models if the same container/volume is kept.** Significant RAM and disk space are required; ordinary student laptops may not meet the current configuration's needs.

Developer fallback: `docker compose up --build`. Open http://localhost:8000. One browser session per container. Stop and download history before beginning another session.

## How it works

Browser microphone or tab/video audio → 16 kHz audio → speech detection → incremental Parakeet captions → guarded optional English review → Chinese / Vietnamese translation → browser captions and history.

`src/pipeline.py` contains segmentation, VAD, conservative correction, translation guards and live target-language selection. `src/backend.py` uses Parakeet for CPU speech recognition, CTranslate2 for local translation, and optional quantized Qwen review. `src/server.py` receives audio and exposes a live language-switch endpoint. Browser assets are under `static/`.

The current Docker default uses Parakeet TDT 0.6B v2 int8 for English speech recognition, a 45-second maximum recognition window, and CTranslate2 int8 for Chinese/Vietnamese translation. English Qwen review is disabled by default because the larger review configuration previously caused a memory spike. For a controlled optional review experiment, set ENGLISH_REVIEW=1 and REVIEW_MODEL_SIZE=0.5b; REVIEW_MODEL_SIZE=3b remains an experimental, higher-memory option. The previous desktop timing field also excludes browser capture/upload/render time; perceived end-to-end latency must be measured separately. Current controlled validation is approximately 2.8–3.2 seconds for first provisional captions on short test input, while some final captions take longer.

## Release links

- Public GitHub repository: **add the final public repository URL before submission**
- GitHub Pages article: **add the final Pages URL before submission**
- Docker Hub image: `phthienan99/bilingual-translator:v72-web`
- Docker Hub repository: `phthienan99/bilingual-translator`
- Peer-trial evidence: [PEER_TRIAL.md](PEER_TRIAL.md) and `evidence/peer-trials/` in the submission ZIP

The public repository and Pages URL are intentionally left as editable placeholders until the team's final URLs are confirmed.

See [RELEASE.md](RELEASE.md), [PEER_TRIAL.md](PEER_TRIAL.md), [VALIDATION.md](VALIDATION.md), and the article draft in [docs/index.html](docs/index.html).

## License and credits

Original application: ADI205 Group 1. The team built independent prototypes and combined their strengths, rather than assigning fixed roles. Each member's prototype and adopted improvements, along with approved names, must be confirmed before publication. The supplied source had no explicit project-wide license; no new open-source license is asserted here. Team members should agree on a source-code license before publishing.

Third-party code and models retain their own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). In particular, Qwen2.5-3B has a Qwen research license and NLLB-200-distilled-600M has a CC-BY-NC-4.0 model license; this is an academic prototype, not an unrestricted commercial product. Check the upstream terms before redistributing weights. This Dockerfile downloads models at runtime rather than bundling their weights.

AI assistance was used to separate the original core, build the browser/container adaptation, and prepare documentation. See [ENGINEERING.md](ENGINEERING.md) for scope and verification limits.


## Compatibility

The published `v72-web` tag is a multi-architecture Docker image with `linux/arm64` and `linux/amd64` variants. The AMD64 variant is intended for Intel Macs and typical Intel/AMD Windows PCs. Chrome/Edge is the recommended browser for microphone capture. Safari was also successfully tested on the developer Mac; one peer previously saw a Safari-specific failure that was not reproduced on the developer machine.

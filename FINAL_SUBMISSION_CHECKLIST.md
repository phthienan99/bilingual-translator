# Final submission checklist — Live Bilingual Classroom Translator

## Release validated

- Docker Hub image: `phthienan99/bilingual-translator:v72-web`
- Published manifest: `sha256:c946957e668e42a23bc06809cab6e023bc8bf8ba1bdb2f048f3f22fb35e70d94`
- Platforms: `linux/amd64` and `linux/arm64`
- Docker Desktop GUI path: Search → Pull → Run → browser
- Host port used in peer trials: `8005` → container `8000`

## Peer trials

- Lucy — Biology, Intel Mac: PASS after multi-architecture retest.
- Lisbeth — Business, M-series Mac + Chrome: PASS.
- Yuqing — BMS, M-series Mac + Safari: PASS after retest; initial Safari session failed, later retest reported working.
- Consent for named peer coursework evidence was recorded.
- Detailed peer evidence: `PEER_TRIAL.md` and `evidence/peer-trials/`.

## First-start behavior

A fresh container may take several minutes before the app is ready because local AI models are downloaded, converted and warmed up. This is documented in `SETUP.md`. This startup delay is separate from the normal live-caption latency target.

## Before course submission

1. Insert the final public GitHub repository URL in `README.md` and the Pages article.
2. Insert the final GitHub Pages URL.
3. Add the approved short demo video to the Pages article and verify playback.
4. Confirm final team attribution/contribution wording and public-use consent for anything shown on the Pages site.
5. Push the exact reviewed source tree to GitHub, then make the submission ZIP from that same final commit.

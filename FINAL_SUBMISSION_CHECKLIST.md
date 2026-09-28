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

## Submission state

1. Final public GitHub repository URL is present in `README.md` and the Pages article.
2. Final GitHub Pages URL is present.
3. The approved short demo video is embedded in the Pages article.
4. Final team attribution is recorded in `CONTRIBUTIONS.md` and the Pages article; named peer evidence includes consent.
5. The reviewed source tree is the basis of the submission ZIP.

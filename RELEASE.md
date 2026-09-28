# Maintainer release checklist

The `v72-web` image is published and peer-tested. Before course submission, only the final public GitHub/GitHub Pages URLs, approved demo video, and final team attribution need to be inserted and verified.

1. Finish the checks in VALIDATION.md. Confirm the chosen local model plan is practical for peers' hardware. If not, agree on a model/runtime change and repeat accuracy and delay tests.
2. Agree on a project license, member credits and exact public repository/image names. Review files for private data. Historical raw CSV, report and video were intentionally not copied into this publishable candidate; add only approved evidence.
3. Sign in to GitHub and Docker Hub on your computer. Do not put tokens or passwords in source files or chat.
4. From this directory, build a multi-platform image (requires a working buildx builder):

```sh
docker login
docker buildx create --use --name bilingual-builder
docker buildx build --platform linux/amd64,linux/arm64 -t phthienan99/bilingual-translator:v72-web --push .
```

A platform build that fails must be fixed before claiming support. The published tag has been inspected and contains `linux/amd64` and `linux/arm64`. The actual published tag was also tested through Docker Desktop by peers on Intel and Apple Silicon Macs.

5. `SETUP.md` and `README.md` now identify the published Docker Hub image/tag. The multi-architecture manifest and GUI-only peer installations have been validated; keep the recorded peer evidence with the submission.
6. Three peer trials are complete with consent. The final peer evidence is in `PEER_TRIAL.md` and `evidence/peer-trials/`. The GitHub Pages article still needs the team's approved demo video and final public URLs before submission.
7. Publish the complete reviewed source:

```sh
git init
git add .
git commit -m "Package bilingual classroom translator for browser and Docker"
gh repo create REPOSITORY_NAME --public --source=. --remote=origin --push
```

8. In repository Settings → Pages, select Deploy from a branch, the actual default branch, and `/docs`. Save. Check the resulting Pages URL in a logged-out browser. GitHub Pages hosts the article; the translation app runs in the user's Docker container.
9. Add the working repository, Pages and Docker Hub links to the README and article, commit and push. Check all links and video playback again.
10. Make the source backup from the exact submitted commit: `git archive --format=zip --output=../submission-source.zip HEAD`. Check that all permitted peer evidence and demo references are tracked before archiving. Submit the public repository URL, Pages URL and this ZIP.


## v73 targeted fixes

- Build target expanded to `linux/amd64` + `linux/arm64` for Intel/AMD and Apple Silicon hosts.
- Browser microphone failures now surface a specific error; Safari receives a compatibility notice recommending Chrome/Edge.
- Stop has a bounded wait for queued audio requests so a failed capture session can return the page to a usable state instead of waiting indefinitely.

These changes are now validated against the published `v72-web` manifest and peer retests. The image contains `linux/amd64` and `linux/arm64` variants.

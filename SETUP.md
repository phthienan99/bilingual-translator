# Install with Docker Desktop — no terminal needed

**Release status: peer-tested multi-architecture release.** The published `phthienan99/bilingual-translator:v72-web` tag contains both `linux/arm64` and `linux/amd64` variants. Lucy successfully retested it on an Intel Mac after the architecture fix, and the other two peer trials also reached working sessions after retest.

## Before you begin

1. Install and open [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your computer. Follow its installer; Windows may ask you to enable WSL 2 and restart.
2. This version runs AI models locally on the CPU. For the current in-progress validation setup, have **32 GB system RAM, 20 GB available to Docker for the current test configuration, and 30 GB free disk**. The optimized ARM64 smoke test peaked at about 2.9 GiB process RSS after cached startup; first-run conversion can use more memory. This does not establish minimum hardware requirements. Low-memory laptops may be unsuitable.
3. Connect to the internet for the first model download. No API key or paid API is used. Model files are downloaded from Hugging Face; subsequent starts of the same container reuse them. Download size is large and has not yet been measured.
4. Have an up-to-date Chrome or Edge browser. Chrome/Edge is the recommended browser for microphone capture. Safari may handle microphone capture differently; if Safari does not show a microphone permission prompt, use Chrome or Edge. Video/tab-audio mode uses the browser screen-sharing picker; choose the video tab and enable **Share tab audio** when available.

## Search → Pull → Run

1. Open Docker Desktop. In its top search field, search for **`phthienan99/bilingual-translator`**.
2. Open the matching repository and pull tag **`v72-web`**. Confirm the publisher matches the name your team provided. Wait for the download.
3. Open **Images**, find that image, and click **Run**.
4. Expand the optional settings. Name the container `classroom-translator`.
5. In **Ports**, enter host port **8000** next to container port **8000/tcp**. If 8000 is already busy, use **8005** (or another free host port) and leave the container side at **8000/tcp**.
6. No environment variables are required. Optional: name `CPU_THREADS`, value `4`. The current default uses Parakeet TDT 0.6B int8 with a 45-second recognition window and local CTranslate2 translation. English Qwen review is disabled by default. Maintainers may test `ENGLISH_REVIEW=1` with `REVIEW_MODEL_SIZE=0.5b`; the 3B review model is experimental and higher-memory. Do not create a .env file.
7. Click **Run**. Open **http://localhost:8000** (or your chosen host port, such as **http://localhost:8005**) in your browser.
8. Select Chinese or Vietnamese. Click **Start listening**. **On the first run, wait for the local models to download, load, convert and warm up. This can take several minutes on a fresh container and is expected.** The page reports the current preparation state, but download percentages are not shown. Do not judge live latency until the page reports that models/audio are ready. Keeping the same container/volume avoids repeating the model download.
9. When prompted, allow browser microphone access. For video/tab-audio mode, also allow screen/tab sharing and select the tab that is playing the source audio. On macOS, enable your browser under System Settings → Privacy & Security → Microphone and Screen & System Audio Recording if needed.
10. Speak English. Read the English captions and their translation. Click **Stop** and wait for final processing. Expand **Full session history** and download it before starting again.

## Next time / troubleshooting

- Start the **existing container** under Containers to reuse model files. Deleting the container deletes its model cache and stored results unless a volume was configured. Recreating it requires another download.
- Port already in use: choose host port **8001**, leaving container port **8000**; open http://localhost:8001.
- Microphone denied: allow it in the browser address bar and operating-system permissions, then reload. Use `localhost`, not a LAN address or the container IP. Remote microphone access is not supported by this local-only app.
- Video audio is not captured: choose **Browser tab / video audio**, select the tab that contains the video, and enable **Share tab audio**. Headphones do not help microphone mode because the microphone cannot hear headphone output.
- Want both a speaker and a video: choose **Microphone + browser tab audio**. The browser will request both permissions; select the video tab and share its audio.
- No captions: check the meter, the selected system microphone, network during first load, and the page's error message. Speak for a few seconds, then pause.
- Container exits or freezes: check Docker memory allocation and its Logs tab. This CPU port has not demonstrated the original Mac version's speed. The application displays ~3 seconds as a target for typical short utterances; do not describe it as a universal guarantee.
- Loading errors: copy the error text or Docker Logs for the team. Do not repeatedly delete and recreate the container while a download/conversion is in progress. If the first run is still preparing models, wait for it to finish before evaluating normal Start/Stop behavior.
- One browser session per container. Closing the tab stops capture immediately; the server requests pipeline shutdown after approximately 30 seconds without a connected page.
- To release resources, stop the container in Docker Desktop when finished.

## Data

Microphone audio is sent from the browser to this local container, not to a speech API. Startup downloads contact model hosting services. Caption text and timing records are written inside the container. Do not publicly share classmates' speech or history without their permission.

## Optional terminal fallback (for maintainers)

Run `docker compose up --build`, then open http://localhost:8000. Compose stores models and captions in named volumes and binds the port to localhost. This is a fallback, not the peer installation path.


### CPU architecture

The published release supports both `linux/arm64` (Apple Silicon) and `linux/amd64` (Intel/AMD). If Docker Desktop reports that no matching platform is available, record the host CPU architecture and contact the team rather than changing the platform manually.

FROM python:3.11-slim-bookworm AS build
ARG TARGETARCH
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends build-essential cmake pkg-config libopenblas-dev
WORKDIR /build
COPY requirements.txt .
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      pip install --prefix=/install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0; \
    else \
      pip install --prefix=/install --no-cache-dir torch==2.6.0; \
    fi
RUN PYTHONPATH=/install/lib/python3.11/site-packages pip install --prefix=/install --no-cache-dir -r requirements.txt
RUN if [ "$TARGETARCH" = "arm64" ]; then export CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS"; else export CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS"; fi \
    && CMAKE_BUILD_PARALLEL_LEVEL=4 pip install --prefix=/install --no-cache-dir --no-deps llama-cpp-python==0.3.16

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/home/app/models DATA_DIR=/home/app/data CPU_THREADS=4 HF_HUB_DISABLE_XET=1 STT_ENGINE=parakeet MAX_UTTERANCE_SECONDS=45 ENGLISH_REVIEW=0
WORKDIR /app
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends libgomp1 libopenblas0-pthread && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app && mkdir -p /home/app/models /home/app/data && chown -R app:app /home/app
COPY --from=build /install/ /usr/local/
COPY src/ ./src/
COPY static/ ./static/
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "--threads=8", "--call", "src.entrypoint:create_app"]

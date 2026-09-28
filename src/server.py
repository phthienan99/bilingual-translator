"""One browser-controlled session per local container."""
import io
import json
import queue
import secrets
import threading
import time
from pathlib import Path

import numpy as np
from flask import Flask, request, jsonify, abort, send_file
from pipeline import PipelineWorker

app = Flask(__name__, static_folder="../static", static_url_path="/static")
app.config['MAX_CONTENT_LENGTH'] = 64000
lock = threading.RLock()
worker = None
owner = None
last_seen = 0.0
events = queue.Queue()
records = {}
status = 'Ready to load models'
error = None
level = 0

def drain():
    global status, error, level
    while True:
        try:
            name, payload = events.get_nowait()
        except queue.Empty:
            break
        if name == 'status': status = payload[0]
        elif name == 'failed': error = payload[0]
        elif name == 'volume': level = payload[0]
        elif name == 'result': records[payload[0]['utterance_id']] = payload[0]
        elif name == 'discarded': records.pop(payload[0], None)
        elif name == 'finished': status = 'Stopped'

@app.before_request
def local_only():
    # Reject remote Host values and cross-origin requests to the localhost service.
    if request.host.split(':')[0] not in ('localhost', '127.0.0.1'):
        abort(403)
    origin = request.headers.get('Origin')
    if origin and origin != request.host_url.rstrip('/'):
        abort(403)
    if request.headers.get('Sec-Fetch-Site') == 'cross-site': abort(403)
    if request.method == 'POST' and request.headers.get('X-App-Request') != '1': abort(403)

@app.get('/')
def index():
    return app.send_static_file('index.html')

def authorize():
    global last_seen
    if not owner or not secrets.compare_digest(request.headers.get('X-Session', ''), owner):
        abort(403)
    last_seen = time.monotonic()

@app.post('/api/start')
def start():
    global worker, owner, status, error, last_seen
    language = (request.get_json(silent=True) or {}).get('language')
    if language not in ('Chinese', 'Vietnamese'): abort(400)
    with lock:
        if worker and worker.is_alive():
            return jsonify(error='A session is already running. Stop it in its original tab.'), 409
        drain()
        records.clear()
        error = None
        status = 'Loading models…'
        owner = secrets.token_urlsafe(24)
        last_seen = time.monotonic()
        worker = PipelineWorker(language, events)
        worker.start()
        return jsonify(session=owner)

@app.post('/api/audio')
def audio():
    with lock:
        authorize()
        if not worker or not worker.ready.is_set() or worker._capture_stop_event.is_set(): abort(409)
        data = request.get_data()
        if not data or len(data) % 4: abort(400)
        samples = np.frombuffer(data, dtype='<f4')
        if not np.isfinite(samples).all(): abort(400)
        # Fail explicitly instead of silently overwriting live audio on overload.
        with worker._audio_lock:
            if len(worker._audio) + len(samples) > worker._audio.maxlen:
                return jsonify(error='Audio backlog is full. Stop and restart on a faster machine.'), 429
        worker._audio_callback(np.clip(samples, -1, 1).reshape(-1, 1), len(samples), None, None)
        return jsonify(ok=True)

@app.post('/api/stop')
def stop():
    with lock:
        authorize()
        if worker: worker.stop()
        return jsonify(ok=True)

@app.post('/api/language')
def language():
    """Change translation language without restarting the live session."""
    with lock:
        authorize()
        if not worker or not worker.is_alive() or worker._capture_stop_event.is_set():
            abort(409)
        value = (request.get_json(silent=True) or {}).get('language')
        if value not in ('Chinese', 'Vietnamese'):
            abort(400)
        worker.set_target_language(value)
        return jsonify(ok=True, language=value)

@app.get('/api/state')
def state():
    with lock:
        authorize()
        drain()
        current_language = None
        if worker and worker.is_alive():
            with worker._language_lock:
                current_language = worker._target_language
        return jsonify(status=status, error=error, level=level, language=current_language,
                       alive=bool(worker and worker.is_alive()),
                       ready=bool(worker and worker.ready.is_set()),
                       stopping=bool(worker and worker._capture_stop_event.is_set()),
                       records=list(records.values()))

@app.get('/api/history')
def history():
    with lock:
        authorize()
        drain()
        text = '\n\n'.join(f"{r['corrected_english']}\n{r['translation']}" for r in records.values())
        return send_file(io.BytesIO(text.encode('utf-8')), mimetype='text/plain',
                         as_attachment=True, download_name='caption-history.txt')

@app.get('/health')
def health():
    return jsonify(ok=True)

def watchdog():
    while True:
        time.sleep(5)
        with lock:
            drain()
            if worker and worker.is_alive() and time.monotonic() - last_seen > 30:
                worker.stop()

threading.Thread(target=watchdog, daemon=True).start()

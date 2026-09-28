"""CPU inference adapters; caption decision rules stay in pipeline.py."""
import os
import shutil
import tempfile
import threading
from pathlib import Path

_lock = threading.Lock()
_cached = None
REVIEW_SIZE = os.environ.get('REVIEW_MODEL_SIZE', '0.5b')
CHINESE_LLM_TRANSLATION = os.environ.get('CHINESE_LLM_TRANSLATION', '0') == '1'
_REVIEW_MODELS = {
    '3b': ('Qwen/Qwen2.5-3B-Instruct-GGUF', 'qwen2.5-3b-instruct-q4_k_m.gguf', 'Qwen/Qwen2.5-3B-Instruct'),
    '0.5b': ('Qwen/Qwen2.5-0.5B-Instruct-GGUF', 'qwen2.5-0.5b-instruct-q8_0.gguf', 'Qwen/Qwen2.5-0.5B-Instruct'),
}
GGUF_REPO, GGUF_FILE, TOKENIZER_REPO = _REVIEW_MODELS.get(REVIEW_SIZE, _REVIEW_MODELS['3b'])

class WhisperAdapter:
    def __init__(self, model):
        self.model = model

    def transcribe(self, audio, **options):
        segments, _ = self.model.transcribe(
            audio, language='en', task='transcribe', beam_size=5,
            max_new_tokens=160,
            temperature=0.0, condition_on_previous_text=False,
            initial_prompt=options.get('initial_prompt'), vad_filter=False)
        # Whisper's default allows confident text to override no-speech scores.
        # A prompted noise clip produced a fluent invented URL with p=0.81.
        # Reject high no-speech probability independently of text confidence.
        segments = [s for s in segments if s.no_speech_prob <= 0.6]
        return {'text': ' '.join(s.text for s in segments),
                'segments': [{'avg_logprob': s.avg_logprob} for s in segments]}

class ParakeetAdapter:
    """English-only offline recognizer; no Whisper confidence scores are available."""
    model_name = 'sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8'

    def __init__(self, threads=4):
        import sherpa_onnx
        import tarfile
        import requests
        from filelock import FileLock
        base = Path(os.environ.get('HF_HOME', '/home/app/models')) / 'parakeet-v2-int8'
        base.mkdir(parents=True, exist_ok=True)
        names = ('encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt')
        with FileLock(str(base / '.download.lock')):
            if not all((base / n).is_file() and (base / n).stat().st_size for n in names):
                if os.environ.get('HF_HUB_OFFLINE') == '1':
                    raise RuntimeError('Parakeet model is not cached; download it before offline use.')
                url = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/' + self.model_name + '.tar.bz2'
                with tempfile.TemporaryDirectory(dir=base) as temporary:
                    temporary = Path(temporary)
                    archive = temporary / 'model.tar.bz2'
                    with requests.get(url, stream=True, timeout=60) as response:
                        response.raise_for_status()
                        with archive.open('wb') as output:
                            for chunk in response.iter_content(1024 * 1024):
                                output.write(chunk)
                    with tarfile.open(archive) as bundle:
                        for member in bundle:
                            name = Path(member.name).name
                            if member.isfile() and name in names:
                                with bundle.extractfile(member) as source, (temporary / name).open('wb') as output:
                                    shutil.copyfileobj(source, output)
                    if not all((temporary / n).is_file() and (temporary / n).stat().st_size for n in names):
                        raise RuntimeError('Incomplete Parakeet model archive')
                    for name in names:
                        os.replace(temporary / name, base / name)
        self.model = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(base / names[0]), decoder=str(base / names[1]),
            joiner=str(base / names[2]), tokens=str(base / names[3]),
            model_type='nemo_transducer', num_threads=threads)

    def transcribe(self, audio, **options):
        stream = self.model.create_stream()
        stream.accept_waveform(16000, audio)
        self.model.decode_stream(stream)
        return {'text': stream.result.text.strip(), 'segments': []}

class TranslationAdapter:
    def __init__(self, path, tokenizer, language, threads):
        import ctranslate2
        self.tokenizer = tokenizer
        self.language = language
        self.engine = ctranslate2.Translator(str(path), device='cpu',
                    compute_type='int8', intra_threads=threads)

    def generate(self, input_ids, attention_mask=None, **options):
        sources = []
        for i, row in enumerate(input_ids.tolist()):
            ids = [value for j, value in enumerate(row)
                   if attention_mask is None or attention_mask[i, j].item()]
            sources.append(self.tokenizer.convert_ids_to_tokens(ids))
        prefix = options.get('forced_bos_token_id')
        prefixes = ([[self.tokenizer.convert_ids_to_tokens(prefix)]] * len(sources)
                    if prefix is not None else None)
        results = self.engine.translate_batch(sources, target_prefix=prefixes,
            beam_size=options.get('num_beams', 1),
            max_decoding_length=options.get('max_new_tokens', 160),
            disable_unk=self.language == 'Chinese')
        return [self.tokenizer.convert_tokens_to_ids(r.hypotheses[0]) for r in results]

def generate(model, tokenizer, *, prompt, max_tokens, verbose=False):
    result = model.create_completion(prompt=prompt, max_tokens=max_tokens,
        temperature=0, top_p=1, repeat_penalty=1,
        stop=['<|im_end|>', '<|endoftext|>'])
    return result['choices'][0]['text']

def converted_model(model_id, language):
    import ctranslate2
    from ctranslate2.converters import TransformersConverter
    from filelock import FileLock
    # CTranslate2 4.8 calls this dtype; Transformers 4.48 calls it torch_dtype.
    class CompatibleConverter(TransformersConverter):
        def load_model(self, model_class, model_name_or_path, **kwargs):
            if 'dtype' in kwargs:
                kwargs['torch_dtype'] = kwargs.pop('dtype')
            return super().load_model(model_class, model_name_or_path, **kwargs)
    base = Path(os.environ.get('HF_HOME', '/home/app/models')) / 'ct2-v1'
    base.mkdir(parents=True, exist_ok=True)
    destination = base / language
    with FileLock(str(base / (language + '.lock'))):
        if (destination / '.complete').exists() and ctranslate2.contains_model(str(destination)):
            return destination
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            build = Path(temporary) / 'model'
            CompatibleConverter(model_id).convert(str(build), quantization='int8')
            (build / '.complete').write_text(model_id + '\n', encoding='utf-8')
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(build, destination)
    return destination

def load_backend(worker):
    global _cached
    if REVIEW_SIZE not in _REVIEW_MODELS:
        raise ValueError('REVIEW_MODEL_SIZE must be 0.5b or 3b')
    # The smaller local model is optional for complete Chinese captions.  Keep
    # the dedicated translator as the automatic fallback when its JSON output
    # is absent or invalid.
    from pipeline import (STT_MODEL, CHINESE_TRANSLATION_MODEL,
                          VIETNAMESE_TRANSLATION_MODEL, REVIEW_ENABLED)
    worker._allow_llm_translation = REVIEW_ENABLED and (
        REVIEW_SIZE == '3b' or CHINESE_LLM_TRANSLATION
    )
    worker._llm_model_name = (
        GGUF_REPO + '/' + GGUF_FILE if REVIEW_ENABLED else 'disabled'
    )
    import torch
    import webrtcvad
    from transformers import AutoTokenizer
    threads = max(1, int(os.environ.get('CPU_THREADS', '4')))
    torch.set_num_threads(threads)
    with _lock:
        if _cached is None:
            offline = os.environ.get('HF_HUB_OFFLINE', '0') == '1'
            worker.status.emit('Loading English speech recognition model…')
            engine = os.environ.get('STT_ENGINE', 'parakeet')
            if engine == 'parakeet':
                stt = ParakeetAdapter(threads)
            elif engine == 'whisper':
                from faster_whisper import WhisperModel
                stt = WhisperAdapter(WhisperModel(STT_MODEL, device='cpu', compute_type='int8',
                                     cpu_threads=threads, local_files_only=offline))
            else:
                raise ValueError('STT_ENGINE must be whisper or parakeet')
            llm = tokenizer = None
            if REVIEW_ENABLED:
                from huggingface_hub import hf_hub_download
                from llama_cpp import Llama, LlamaRAMCache
                worker.status.emit('Loading quantized English review model…')
                path = hf_hub_download(GGUF_REPO, GGUF_FILE, local_files_only=offline)
                tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_REPO, local_files_only=offline)
                llm = Llama(model_path=path, n_ctx=2048, n_threads=threads, n_batch=256, verbose=False)
                llm.set_cache(LlamaRAMCache(capacity_bytes=512 * 1024**2))
            tokenizers, models = {}, {}
            for language, model_id in [('Chinese', CHINESE_TRANSLATION_MODEL),
                                       ('Vietnamese', VIETNAMESE_TRANSLATION_MODEL)]:
                worker.status.emit(f'Preparing {language} translation model (first run converts weights)…')
                opts = {'src_lang': 'eng_Latn'} if language == 'Vietnamese' else {}
                tokenizers[language] = AutoTokenizer.from_pretrained(model_id, local_files_only=offline, **opts)
                path = converted_model(model_id, language)
                models[language] = TranslationAdapter(path, tokenizers[language], language, threads)
            _cached = stt, llm, tokenizer, tokenizers, models
        (worker._mlx_whisper, worker._llm, worker._tokenizer,
         worker._translation_tokenizers, worker._translation_models) = _cached
    worker._torch = torch
    worker._translation_device = torch.device('cpu')
    worker._generate = generate
    worker._vad = webrtcvad.Vad(1)

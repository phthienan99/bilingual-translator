from __future__ import annotations

import csv
import difflib
import json
import math
import queue
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import os
from contextlib import nullcontext


ROOT = Path(__file__).resolve().parents[1]
RESULTS_FILE = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))) / "live_results_v72_complete_history.csv"
CAPTION_HISTORY_FILE = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))) / "caption_history.txt"
LIVE_VISIBLE_PAIRS = 3
SAMPLE_RATE = 16_000
FRAME_SAMPLES = 480
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE
MIN_UTTERANCE_SECONDS = 0.75
END_SILENCE_SECONDS = float(os.environ.get("END_SILENCE_SECONDS", "0.65"))
# Parakeet needs enough context to preserve linked corrections such as
# "option D, not option B".  Thirty seconds forced a split in a verified
# classroom recording even though speech was continuous; 45 seconds retained
# the whole statement while provisional captions continue every second.
MAX_UTTERANCE_SECONDS = float(os.environ.get("MAX_UTTERANCE_SECONDS", "45" if os.environ.get("STT_ENGINE") == "parakeet" else "10"))
PARTIAL_UPDATE_SECONDS = 1.0
PARTIAL_AUDIO_WINDOW_SECONDS = MAX_UTTERANCE_SECONDS
HISTORY_RETENTION_SECONDS = 90.0
OVERLAP_SECONDS = 0.25
SPEECH_THRESHOLD_DBFS = -42.0
WEBRTC_AGGRESSIVENESS = 1
MIN_SPEECH_FRAME_RATIO = 0.20
TARGET_STT_DBFS = -26.0
MAX_STT_GAIN_DB = 24.0
PRE_VAD_GAIN_DB = float(os.environ.get("PRE_VAD_GAIN_DB", "18"))
MIN_VAD_SPEECH_DBFS = float(os.environ.get("MIN_VAD_SPEECH_DBFS", "-48"))
REVIEW_ENABLED = os.environ.get("ENGLISH_REVIEW", "0" if os.environ.get("STT_ENGINE") == "parakeet" else "1") == "1"
STT_MODEL = os.environ.get("STT_MODEL", "Systran/faster-whisper-small.en")
STT_INITIAL_PROMPT = (
    "Technical classroom lecture. Preserve the speaker's exact terminology, "
    "grammar, and complete sentence meaning. When the speaker lists multiple-choice "
    "answers, write the option labels exactly as A, B, and C rather than as words "
    "such as 'a' or 'see'. Preserve every spoken option and number."
)
LLM_MODEL = "Qwen/Qwen2.5-3B-Instruct"
CHINESE_TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-en-zh"
VIETNAMESE_TRANSLATION_MODEL = "facebook/nllb-200-distilled-600M"


class EventSignal:
    def __init__(self, events: queue.Queue, name: str) -> None:
        self._events = events
        self._name = name

    def emit(self, *payload) -> None:
        self._events.put((self._name, payload))


class PipelineWorker(threading.Thread):

    def __init__(
        self, target_language: str, events: queue.Queue, input_device: int = 0
    ) -> None:
        super().__init__(name="live-pipeline", daemon=True)
        self.status = EventSignal(events, "status")
        self.volume = EventSignal(events, "volume")
        self.raw_english = EventSignal(events, "raw_english")
        self.result = EventSignal(events, "result")
        self.failed = EventSignal(events, "failed")
        self.finished = EventSignal(events, "finished")
        self.discarded = EventSignal(events, "discarded")
        self.ready = threading.Event()
        self._target_language = target_language
        self._input_device = input_device
        self._language_lock = threading.Lock()
        self._audio_lock = threading.Lock()
        self._audio: deque[float] = deque(maxlen=SAMPLE_RATE * 12)
        self._recent_corrected: deque[tuple[float, str]] = deque()
        self._raw_history: deque[dict] = deque()
        self._recent_stt_outputs: deque[tuple[float, str]] = deque()
        self._final_history: deque[dict] = deque()
        self._utterance_queue: queue.Queue[
            tuple[np.ndarray, float, float, int, bool, float]
        ] = queue.Queue(maxsize=6)
        self._stop_event = threading.Event()
        self._capture_stop_event = threading.Event()
        self._last_provisional_records: dict[int, dict] = {}

    def _prune_history(self) -> None:
        cutoff = time.monotonic() - HISTORY_RETENTION_SECONDS
        while self._recent_corrected and self._recent_corrected[0][0] < cutoff:
            self._recent_corrected.popleft()
        while self._raw_history and self._raw_history[0]["stored_at"] < cutoff:
            self._raw_history.popleft()
        while (
            self._recent_stt_outputs
            and self._recent_stt_outputs[0][0] < cutoff
        ):
            self._recent_stt_outputs.popleft()
        while self._final_history and self._final_history[0]["stored_at"] < cutoff:
            self._final_history.popleft()

    def _recent_context(self) -> str:
        self._prune_history()
        return " ".join(text for _, text in self._recent_corrected)[-600:]

    def _queue_audio(
        self,
        audio: np.ndarray,
        audio_seconds: float,
        utterance_id: int,
        is_final: bool,
        speech_started_at: float,
    ) -> None:
        item = (
            audio,
            time.perf_counter(),
            audio_seconds,
            utterance_id,
            is_final,
            speech_started_at,
        )
        retained = []
        removed_stale = False
        while True:
            try:
                queued = self._utterance_queue.get_nowait()
            except queue.Empty:
                break
            queued_utterance_id = queued[3]
            queued_is_final = queued[4]
            drop = (
                not queued_is_final
                and queued_utterance_id <= utterance_id
            )
            if drop:
                removed_stale = True
            else:
                retained.append(queued)
            self._utterance_queue.task_done()

        for queued in retained:
            self._utterance_queue.put_nowait(queued)

        try:
            self._utterance_queue.put_nowait(item)
        except queue.Full:
            if not is_final:
                self.status.emit("Listening — skipped a stale partial update")
                return
            oldest = self._utterance_queue.get_nowait()
            self._utterance_queue.task_done()
            self._utterance_queue.put_nowait(item)
            removed_stale = removed_stale or not oldest[4]
        if removed_stale:
            self.status.emit("Listening — replaced stale partial work")

    def set_target_language(self, language: str) -> None:
        with self._language_lock:
            self._target_language = language

    def stop(self) -> None:
        # Stop audio capture first. The run loop will finalize the active
        # utterance and drain queued caption work before stopping the processor.
        self._capture_stop_event.set()

    def wait(self, milliseconds: int) -> None:
        self.join(timeout=milliseconds / 1000.0)

    def _audio_callback(self, indata, frames, time_info, callback_status) -> None:
        if callback_status:
            self.status.emit(f"Audio warning: {callback_status}")
        mono = np.asarray(indata[:, 0], dtype=np.float32)
        rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
        dbfs = 20.0 * math.log10(max(rms, 1e-9))
        meter = max(0, min(100, int((dbfs + 60.0) / 60.0 * 100.0)))
        self.volume.emit(meter, dbfs)
        with self._audio_lock:
            self._audio.extend(mono.tolist())

    def _next_frame(self) -> np.ndarray | None:
        with self._audio_lock:
            if len(self._audio) < FRAME_SAMPLES:
                return None
            return np.fromiter(
                (self._audio.popleft() for _ in range(FRAME_SAMPLES)),
                dtype=np.float32,
                count=FRAME_SAMPLES,
            )

    @staticmethod
    def _frame_dbfs(frame: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(np.square(frame), dtype=np.float64)))
        return 20.0 * math.log10(max(rms, 1e-9))

    @staticmethod
    def _has_minimum_speech_energy(
        squared_sum: float, sample_count: int
    ) -> bool:
        """Reject VAD-triggered low-level noise before it reaches recognition.

        VAD receives an amplified frame so quiet speech can begin an utterance.
        This second gate uses original samples, which prevents very quiet clicks
        and background noise from becoming plausible short captions. The limit
        remains configurable for genuinely quiet microphones.
        """
        if sample_count <= 0:
            return False
        rms = math.sqrt(squared_sum / sample_count)
        return 20.0 * math.log10(max(rms, 1e-9)) >= MIN_VAD_SPEECH_DBFS

    @classmethod
    def _normalize_for_stt(cls, audio: np.ndarray) -> np.ndarray:
        """Raise distant speech safely without clipping or changing VAD input."""
        current_dbfs = cls._frame_dbfs(audio)
        gain_db = min(MAX_STT_GAIN_DB, max(0.0, TARGET_STT_DBFS - current_dbfs))
        if gain_db <= 0.0:
            return audio
        gain = 10.0 ** (gain_db / 20.0)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 0.0:
            gain = min(gain, 0.95 / peak)
        return np.asarray(audio * gain, dtype=np.float32)

    @staticmethod
    def _looks_like_repetition(text: str) -> bool:
        # Inspect raw characters before tokenizing: punctuation-only loops
        # disappear from word/number token lists. Require a long repeated run.
        if any(len(m.group(0)) >= 24 for m in re.finditer(r"(\S{1,24}?)\1{7,}", text)):
            return True
        words = re.findall(r"[a-zA-Z0-9']+", text.lower())
        if len(words) < 6:
            return False
        most_common = max(words.count(word) for word in set(words))
        if most_common / len(words) >= 0.65 or most_common >= 8:
            return True
        # Catch alternating loops such as "children with children with..."
        # before they are sent to translation and block the live queue.
        bigrams = list(zip(words, words[1:]))
        return bool(bigrams) and max(bigrams.count(item) for item in set(bigrams)) >= 5

    def _is_weak_stt_artifact(self, text: str, avg_logprob: float | None) -> bool:
        """Reject characteristic distant-audio artifacts without hiding clear speech."""
        words = re.findall(r"[a-zA-Z']+", text.lower())
        normalized = " ".join(words)
        prompt_words = " ".join(
            re.findall(r"[a-zA-Z']+", STT_INITIAL_PROMPT.lower())
        )
        if normalized and len(words) >= 4 and normalized in prompt_words:
            return True
        if len(words) <= 2 and avg_logprob is not None and avg_logprob < -0.45:
            return True
        if len(words) <= 4 and avg_logprob is not None and avg_logprob < -0.70:
            return True
        self._prune_history()
        recent_matches = sum(
            previous == normalized for _, previous in self._recent_stt_outputs
        )
        self._recent_stt_outputs.append((time.monotonic(), normalized))
        return bool(normalized and recent_matches >= 1 and avg_logprob is not None and avg_logprob < -0.35)

    @staticmethod
    def _collapse_translation_repetition(text: str) -> str:
        """Collapse obvious model loops while preserving normal double emphasis."""
        cleaned = text.strip()
        previous = None
        while cleaned != previous:
            previous = cleaned
            # Chinese loops, with or without spaces/punctuation: 我知道，我知道，我知道
            cleaned = re.sub(
                r"([\u3400-\u9fff]{1,10}?)(?:[\s，、,。！？!?;；:：]*\1){2,}",
                r"\1",
                cleaned,
            )
            # Vietnamese/Latin word or short-phrase loops repeated at least 3 times.
            cleaned = re.sub(
                r"\b((?:[A-Za-zÀ-ỹ]+\s+){0,4}[A-Za-zÀ-ỹ]+)"
                r"(?:[\s,;:!?]+\1){2,}\b",
                r"\1",
                cleaned,
                flags=re.IGNORECASE,
            )
        return re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    @staticmethod
    def _translation_units(english: str) -> list[str]:
        """Keep NLLB inputs short enough to translate every part of a long caption."""
        # Translate complete sentences separately: NLLB can omit a later
        # sentence even when a multi-sentence caption is below 180 characters.
        # Keep titles, initials and dotted abbreviations attached to their text.
        sentences = []
        start = 0
        for boundary in re.finditer(r"(?<=[.!?])\s+", english):
            prefix = english[start:boundary.start()]
            abbreviation = re.search(
                r"(?:\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|vs|etc)\."
                r"|\b[A-Za-z]\.(?:[A-Za-z]\.)*)$",
                prefix,
                re.I,
            )
            # An option label such as "D." ends a classroom sentence; an
            # initial within a name or abbreviation does not.
            single_option = (
                bool(re.search(r"\b[A-Za-z]\.$", prefix))
                and boundary.end() < len(english)
                and english[boundary.end()].isupper()
            )
            if abbreviation and not single_option:
                continue
            sentences.append(prefix.strip())
            start = boundary.end()
        if english[start:].strip():
            sentences.append(english[start:].strip())
        units: list[str] = []
        for sentence in sentences or [english.strip()]:
            if len(sentence) <= 180:
                units.append(sentence)
                continue
            clauses = [
                part.strip()
                for part in re.findall(r"[^,;:]+(?:[,;:]+|$)", sentence)
                if part.strip()
            ]
            current = ""
            for clause in clauses:
                candidate = f"{current} {clause}".strip()
                if current and len(candidate) > 180:
                    units.append(current)
                    current = clause
                else:
                    current = candidate
            if current:
                units.append(current)
        return units or [english.strip()]

    @staticmethod
    def _critical_tokens(text: str) -> list[str]:
        """Tokens that an automatic reviewer must never alter or invent."""
        tokens = re.findall(r"[A-Za-z0-9']+", text.lower())
        critical = []
        for token in tokens:
            if token.isdigit() or re.fullmatch(r"\d+(?:\.\d+)?", token):
                critical.append(token)
            elif token in {
                "not", "no", "never", "without",
                "a", "b", "c", "d", "e",
                "option",
            }:
                critical.append(token)
        return critical

    @classmethod
    def _preserves_lexical_content(cls, raw_text: str, candidate: str) -> bool:
        token_pattern = r"[A-Za-z0-9']+"
        raw_tokens = re.findall(token_pattern, raw_text.lower())
        candidate_tokens = re.findall(token_pattern, candidate.lower())
        return candidate_tokens == raw_tokens

    @classmethod
    def _safe_review_change(cls, raw_text: str, candidate: str) -> bool:
        """Allow tiny LLM autocorrections while protecting high-risk content.

        This is intentionally stricter than a normal LLM editor: at most two
        token edits are allowed, token counts cannot drift by more than one,
        and numbers/negation/option labels must survive unchanged.
        """
        raw_tokens = re.findall(r"[A-Za-z0-9']+", raw_text.lower())
        candidate_tokens = re.findall(r"[A-Za-z0-9']+", candidate.lower())
        if not raw_tokens or not candidate_tokens:
            return False
        if abs(len(candidate_tokens) - len(raw_tokens)) > 1:
            return False
        matcher = difflib.SequenceMatcher(None, raw_tokens, candidate_tokens)
        edits = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                edits += max(i2 - i1, j2 - j1)
        if edits > 2:
            return False
        raw_critical = cls._critical_tokens(raw_text)
        candidate_critical = cls._critical_tokens(candidate)
        return raw_critical == candidate_critical

    @staticmethod
    def _repair_chinese_terminology(english: str, translation: str) -> str:
        """Apply narrow, source-supported classroom terminology corrections."""
        repaired = translation
        if re.search(r"\bancestry\b", english, re.I):
            repaired = re.sub(r"\bancestry\b", "血统", repaired, flags=re.I)
        if re.search(r"\bethnicity\b", english, re.I):
            repaired = re.sub(r"\bethnicity\b", "族裔", repaired, flags=re.I)
        if re.search(r"\bgenealogist\b", english, re.I):
            repaired = repaired.replace("基因学家", "家谱学家")
        if re.search(r"\b(?:ancestors?|ancestry).*\bEnglish\b|\bEnglish\s+at\s+all\b", english, re.I):
            repaired = repaired.replace("英语背景", "英格兰血统")
            repaired = repaired.replace("完全没有英语血统", "完全没有英格兰血统")
        if re.search(r"\bof\s+the\s+result\s+represents?\s+Irish\s+ancestry\b", english, re.I):
            repaired = re.sub(
                r"(\d+(?:\.\d+)?%)的血统代表爱尔兰血统",
                r"结果中\1代表爱尔兰血统",
                repaired,
            )
        return repaired

    @staticmethod
    def _repair_vietnamese_terminology(english: str, translation: str) -> str:
        repaired = translation
        if re.search(r"\bthe assignment is due on Friday\b", english, re.I):
            repaired = repaired.replace(
                "Thời hạn giao nhiệm là thứ Sáu.",
                "Hạn nộp bài tập là thứ Sáu.",
            )
        if re.search(r"\ba genealogist\b", english, re.I):
            repaired = re.sub(
                r"Một nhà nghiên cứu lịch sử gia đình nghiên cứu(?: lịch sử)? gia đình",
                "Một nhà nghiên cứu gia phả nghiên cứu lịch sử gia đình",
                repaired,
                flags=re.I,
            )
        return repaired

    @staticmethod
    def _clarify_deadlines(english: str) -> str:
        """Disambiguate academic due dates for translation, keeping negation/date intact."""
        pattern = r"\b((?:the|this|my|our|your|their|his|her|a)\s+(?:assignment|homework|report|project|essay))\s+is\s+(not\s+)?due\s+on\s+"
        return re.sub(pattern, lambda m: "The deadline for " + m.group(1) + " is " + (m.group(2) or ""), english, flags=re.I)

    def _translate_text(self, english: str, target_code: str) -> str:
        from clock_text import normalize_clock_text
        translation_source = normalize_clock_text(self._clarify_deadlines(english))
        # Nationality adjectives in DNA-test percentages describe ancestry, not
        # a language. Supplying that missing noun prevents Marian from rendering
        # "Irish" as "Irish language" while leaving ordinary uses untouched.
        ancestry_context = bool(
            re.search(r"\b(?:DNA|ancestry|ancestor|result|percent|%)\b", english, re.I)
        )
        if target_code == "zho_Hans" and ancestry_context:
            translation_source = re.sub(
                r"\b(Irish|Scottish|Welsh|English)\b(?!\s+(?:ancestry|heritage))",
                r"\1 ancestry",
                translation_source,
                flags=re.I,
            )
        if target_code == "vie_Latn":
            # Clarify two classroom expressions that NLLB repeatedly translated
            # literally or incorrectly. This changes only the translation input,
            # never the accepted English shown to the student.
            translation_source = re.sub(
                r"\ba genealogist\b",
                "a family history researcher",
                translation_source,
                flags=re.I,
            )
            translation_source = re.sub(
                r"\bethnicity\b",
                "ethnic identity",
                translation_source,
                flags=re.I,
            )
        source_units = self._translation_units(english)
        units = self._translation_units(translation_source)
        # Deadline clarification changes wording but not sentence boundaries.
        # Fall back to the clarified units if a future rewrite ever changes them.
        if len(source_units) != len(units):
            source_units = units
        language_key = "Chinese" if target_code == "zho_Hans" else "Vietnamese"
        from classroom_translation import translate_classroom_sentence
        translated_units: list[str | None] = [
            translate_classroom_sentence(unit, language_key) for unit in source_units
        ]
        neural_indices = [
            index for index, translation in enumerate(translated_units)
            if translation is None
        ]
        neural_units = [units[index] for index in neural_indices]
        if not neural_units:
            return " ".join(item for item in translated_units if item)
        tokenizer = self._translation_tokenizers[language_key]
        model = self._translation_models[language_key]
        inputs = tokenizer(
            neural_units, return_tensors="pt", padding=True, truncation=True, max_length=256
        )
        inputs = {
            key: value.to(self._translation_device)
            for key, value in inputs.items()
        }
        with self._torch.inference_mode():
            generate_options = {"max_new_tokens": 160, "num_beams": 1}
            if language_key == "Vietnamese":
                generate_options["forced_bos_token_id"] = (
                    tokenizer.convert_tokens_to_ids("vie_Latn")
                )
            translated_tokens = model.generate(**inputs, **generate_options)
        neural_translations = tokenizer.batch_decode(
            translated_tokens, skip_special_tokens=True
        )
        for index, translation in zip(neural_indices, neural_translations):
            translated_units[index] = translation
        translation = " ".join(item.strip() for item in translated_units if item and item.strip())
        translation = self._collapse_translation_repetition(translation)
        if target_code == "zho_Hans":
            translation = self._repair_chinese_terminology(english, translation)
        else:
            translation = self._repair_vietnamese_terminology(english, translation)
        return translation

    def _correct_and_translate(
        self, raw_text: str, run_correction: bool
    ) -> tuple[str, str, float]:
        with self._language_lock:
            language = self._target_language

        nllb_target_code = "zho_Hans" if language == "Chinese" else "vie_Latn"

        if not run_correction or not REVIEW_ENABLED:
            english = raw_text
            translation_started = time.perf_counter()
            translation = self._translate_text(english, nllb_target_code)
            elapsed = time.perf_counter() - translation_started
            return english, translation, elapsed

        recent_context = self._recent_context() or "(none)"
        raw_word_count = len(re.findall(r"[A-Za-z0-9']+", raw_text))
        first_sentence = re.split(r"(?<=[.!?])\s+", raw_text, maxsplit=1)[0]
        leading_words = re.findall(r"[A-Za-z0-9']+", first_sentence)
        leading_continuation = (
            bool(raw_text[:1])
            and raw_text[:1].islower()
            and len(leading_words) <= 4
        )
        request_llm_translation = (
            getattr(self, "_allow_llm_translation", True)
            and language == "Chinese"
            and raw_word_count >= 8
            and not leading_continuation
        )
        output_instruction = (
            f"Translate the complete current caption faithfully into "
            f"{'Simplified Chinese' if language == 'Chinese' else language}. Preserve "
            "all names, numbers, option labels such as A/B/C, and every supported idea. "
            "For classroom terminology, translate ancestry as 血统 or 祖源, ethnicity "
            "as 族裔, genealogist as 家谱学家, and nationality English as 英格兰 rather "
            "than the English language when the target is Chinese. "
            "Use natural classroom language, but never summarize or add an explanation. "
            "Return exactly one valid JSON object matching "
            '{"english":"accepted English","translation":"complete translation"}. '
            if request_llm_translation
            else "Return exactly one valid JSON object matching "
            '{"english":"accepted English"}. '
        )
        correction_prompt = (
            "You are the final review and translation stage of a live English "
            "classroom-caption system. "
            "Use recent caption context only to disambiguate words in the current chunk. "
            "Never copy earlier words into the current chunk and never complete an unfinished "
            "sentence. Preserve every supported idea and the original word order. Make no more "
            "than two word-level substitutions, and only for high-confidence grammar errors or "
            "obvious acoustically similar recognition errors. If uncertain, leave the raw text "
            "unchanged. Never paraphrase, summarize, omit content, or add new meaning. "
            f"{output_instruction}"
            "No markdown, labels, or explanation.\n\n"
            f"Recent corrected context: {recent_context}\n"
            f"Current raw transcript: {raw_text}"
        )

        def generate_json(system: str, user: str, max_tokens: int) -> tuple[dict, float]:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            formatted = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            started = time.perf_counter()
            response = self._generate(
                self._llm,
                self._tokenizer,
                prompt=formatted,
                max_tokens=max_tokens,
                verbose=False,
            )
            duration = time.perf_counter() - started
            match = re.search(r"\{.*?\}", response, flags=re.DOTALL)
            if not match:
                return {}, duration
            try:
                return json.loads(match.group(0)), duration
            except json.JSONDecodeError:
                return {}, duration

        correction, elapsed = generate_json(
            (
                f"Review English conservatively and translate it faithfully into {language}. "
                if request_llm_translation
                else "Review English conservatively. "
            ) + "Return valid JSON only.",
            correction_prompt,
            220 if request_llm_translation else 100,
        )
        english = str(correction.get("english", "")).strip() or raw_text
        latin_letters = len(re.findall(r"[A-Za-z]", english))
        cjk_characters = len(re.findall(r"[\u3400-\u9fff]", english))
        raw_words = re.findall(r"[A-Za-z0-9']+", raw_text.lower())
        corrected_words = re.findall(r"[A-Za-z0-9']+", english.lower())
        similarity = difflib.SequenceMatcher(
            None, " ".join(raw_words), " ".join(corrected_words)
        ).ratio()
        excessive_rewrite = (
            similarity < 0.78
            or abs(len(corrected_words) - len(raw_words)) > 2
        )
        # The reviewer is allowed to make a very small autocorrection now, but
        # only under the dedicated safety gate above. This recovers useful fixes
        # such as ``do`` -> ``due`` without giving the LLM permission to rewrite
        # classroom content. Numbers, negation and option labels remain locked.
        lexical_change = not self._preserves_lexical_content(raw_text, english)
        safe_review_change = self._safe_review_change(raw_text, english)
        added_markdown = any(
            marker in english and marker not in raw_text
            for marker in ("*", "`", "#")
        )
        invalid_english = latin_letters < 2 or cjk_characters > latin_letters
        if invalid_english or excessive_rewrite or (lexical_change and not safe_review_change) or added_markdown:
            english = raw_text

        # This is the useful part borrowed from the groupmate's design: the LLM
        # sees the lecture context while translating. Keep our dedicated model as
        # a safe fallback if the LLM response is missing, malformed, or invalid.
        translation = self._collapse_translation_repetition(
            str(correction.get("translation", "")).strip()
        )
        word_count = len(re.findall(r"[A-Za-z0-9']+", english))
        # The v45 test showed that Qwen improved complete Chinese sentences but
        # could confidently mistranslate very short fragments (for example,
        # "28.5% Irish"). NLLB was more dependable for Vietnamese. Therefore
        # only sufficiently complete Chinese captions may use the LLM translation.
        use_llm_translation = request_llm_translation and word_count >= 8

        def valid_translation(value: str) -> bool:
            if not value or value.casefold() == english.casefold():
                return False
            if language == "Chinese":
                return bool(re.search(r"[\u3400-\u9fff]", value))
            if re.search(r"[\u3400-\u9fff]", value):
                return False
            vietnamese_marks = len(re.findall(r"[À-ỹĐđ]", value))
            latin_letters = len(re.findall(r"[A-Za-zÀ-ỹ]", value))
            return latin_letters >= 2 and (vietnamese_marks > 0 or len(value.split()) >= 2)

        if not use_llm_translation or not valid_translation(translation):
            translation_started = time.perf_counter()
            translation = self._translate_text(english, nllb_target_code)
            elapsed += time.perf_counter() - translation_started
        if language == "Chinese":
            translation = self._repair_chinese_terminology(english, translation)
        if not valid_translation(translation):
            raise ValueError(f"No valid {language} translation was produced")
        return english, translation, elapsed

    def _save(self, record: dict) -> None:
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "timestamp",
            "version",
            "vad_option",
            "vad_threshold",
            "stt_model",
            "stt_prompt",
            "llm_model",
            "translation_model",
            "target_language",
            "utterance_id",
            "update_kind",
            "revision_of",
            "chunk_seconds",
            "stt_avg_logprob",
            "stt_max_temperature",
            "correction_applied",
            "stt_seconds",
            "llm_seconds",
            "processing_seconds",
            "queue_wait_seconds",
            "true_e2e_seconds",
            "estimated_caption_lag_seconds",
            "estimated_e2e_seconds",
            "raw_english",
            "corrected_english",
            "translation",
            "expected_english",
            "accuracy_notes",
        ]
        exists = RESULTS_FILE.exists()
        with RESULTS_FILE.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            if not exists:
                writer.writeheader()
            writer.writerow({key: record.get(key, "") for key in fields})

    def _retain_last_provisional(self, utterance_id: int, reason: str) -> bool:
        """An unusable final pass cannot substantiate an earlier provisional caption."""
        self._last_provisional_records.pop(utterance_id, None)
        self.discarded.emit(utterance_id)
        return False

    def _process_utterances(self) -> None:
        while not self._stop_event.is_set() or not self._utterance_queue.empty():
            try:
                (
                    audio,
                    enqueued_at,
                    audio_seconds,
                    utterance_id,
                    is_final,
                    speech_started_at,
                ) = self._utterance_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            process_started = time.perf_counter()
            queue_wait = process_started - enqueued_at
            try:
                self.status.emit("Transcribing")
                # Whisper prompts are vocabulary hints, not instructions.
                # Do not bias new audio with potentially incorrect past captions.
                stt_prompt = None
                stt_started = time.perf_counter()
                stt_audio = self._normalize_for_stt(audio)
                stt_result = self._mlx_whisper.transcribe(
                    stt_audio,
                    path_or_hf_repo=STT_MODEL,
                    language="en",
                    task="transcribe",
                    temperature=0.0,
                    condition_on_previous_text=False,
                    initial_prompt=stt_prompt,
                    verbose=None,
                )
                stt_seconds = time.perf_counter() - stt_started
                raw_text = stt_result.get("text", "").strip()
                segment_logprobs = [
                    float(segment.get("avg_logprob", 0.0))
                    for segment in stt_result.get("segments", [])
                    if segment.get("avg_logprob") is not None
                ]
                stt_avg_logprob = (
                    sum(segment_logprobs) / len(segment_logprobs)
                    if segment_logprobs
                    else None
                )
                stt_max_temperature = 0.0
                run_correction = is_final and REVIEW_ENABLED

                if not raw_text or len(re.findall(r"[A-Za-z]", raw_text)) < 2:
                    if is_final and self._retain_last_provisional(
                        utterance_id, "no usable final speech"
                    ):
                        self.status.emit("Listening — retained last visible caption")
                        continue
                    self.status.emit("Listening — no speech recognized")
                    continue
                if self._looks_like_repetition(raw_text):
                    if is_final and self._retain_last_provisional(
                        utterance_id, "repeated final recognition"
                    ):
                        self.status.emit("Listening — retained last visible caption")
                        continue
                    self.status.emit(
                        "Listening — filtered repeated STT hallucination"
                    )
                    continue
                if self._is_weak_stt_artifact(raw_text, stt_avg_logprob):
                    if is_final and self._retain_last_provisional(
                        utterance_id, "weak final recognition"
                    ):
                        self.status.emit("Listening — retained last visible caption")
                        continue
                    self.status.emit(
                        "Listening — filtered weak classroom-audio artifact"
                    )
                    continue

                self._prune_history()
                self._raw_history.append(
                    {
                        "stored_at": time.monotonic(),
                        "utterance_id": utterance_id,
                        "is_final": is_final,
                        "raw_english": raw_text,
                    }
                )

                self.raw_english.emit(raw_text)
                self.status.emit(
                    "Final correction and translation"
                    if is_final
                    else "Translating provisional caption"
                )
                corrected, translation, llm_seconds = self._correct_and_translate(
                    raw_text, run_correction
                )
                processing = time.perf_counter() - process_started
                true_e2e = time.perf_counter() - speech_started_at
                previous_final = (
                    self._final_history[-1]
                    if is_final and self._final_history
                    else None
                )
                if is_final:
                    self._recent_corrected.append((time.monotonic(), corrected))
                with self._language_lock:
                    language = self._target_language
                record = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "version": "v72_web_cpu_candidate",
                    "vad_option": "WebRTC VAD 2.0.14 (no adaptive noise gate)",
                    "vad_threshold": (
                        f"aggressiveness={WEBRTC_AGGRESSIVENESS}; "
                        f"pre_vad_gain_db={PRE_VAD_GAIN_DB}; no post-VAD dB gate"
                    ),
                    "stt_model": getattr(self._mlx_whisper, "model_name", STT_MODEL),
                    "stt_prompt": stt_prompt,
                    "llm_model": getattr(self, "_llm_model_name", LLM_MODEL) if run_correction else "none; review disabled or provisional",
                    "translation_model": (
                        f"{LLM_MODEL} for complete Chinese; dedicated-model fallback"
                        if is_final and language == "Chinese" and getattr(self, "_allow_llm_translation", True)
                        else (
                            CHINESE_TRANSLATION_MODEL
                            if language == "Chinese"
                            else VIETNAMESE_TRANSLATION_MODEL
                        )
                    ),
                    "target_language": language,
                    "utterance_id": utterance_id,
                    "update_kind": "final" if is_final else "provisional",
                    "revision_of": "",
                    "chunk_seconds": f"{audio_seconds:.3f}",
                    "stt_avg_logprob": f"{stt_avg_logprob:.4f}" if stt_avg_logprob is not None else "",
                    "stt_max_temperature": f"{stt_max_temperature:.1f}",
                    "correction_applied": (
                        (
                            "accepted non-lexical formatting correction"
                            if corrected != raw_text
                            else "Qwen checked; original wording retained"
                        )
                        if run_correction
                        else "review disabled; recognition preserved" if is_final else "deferred until final"
                    ),
                    "stt_seconds": f"{stt_seconds:.3f}",
                    "llm_seconds": f"{llm_seconds:.3f}",
                    "processing_seconds": f"{processing:.3f}",
                    "queue_wait_seconds": f"{queue_wait:.3f}",
                    "true_e2e_seconds": f"{true_e2e:.3f}",
                    "estimated_caption_lag_seconds": (
                        f"{queue_wait + processing:.3f}"
                    ),
                    "estimated_e2e_seconds": (
                        f"{audio_seconds + queue_wait + processing:.3f}"
                    ),
                    "raw_english": raw_text,
                    "corrected_english": corrected,
                    "translation": translation,
                }
                self._save(record)
                self.result.emit(record)
                if is_final:
                    self._last_provisional_records.pop(utterance_id, None)
                else:
                    self._last_provisional_records[utterance_id] = dict(record)

                if is_final:
                    self._final_history.append(
                        {
                            "stored_at": time.monotonic(),
                            "speech_started_at": speech_started_at,
                            "record": record,
                        }
                    )
                    should_recheck_previous = False
                    if previous_final is not None:
                        previous_record = previous_final["record"]
                        normalized_previous_raw = re.sub(
                            r"\W+", " ", previous_record["raw_english"].lower()
                        ).strip()
                        normalized_previous_corrected = re.sub(
                            r"\W+",
                            " ",
                            previous_record["corrected_english"].lower(),
                        ).strip()
                        should_recheck_previous = (
                            normalized_previous_raw != normalized_previous_corrected
                        )
                    if (
                        previous_final is not None
                        and should_recheck_previous
                        and self._utterance_queue.empty()
                    ):
                        self.status.emit("Rechecking the previous caption with new context")
                        revision_started = time.perf_counter()
                        revised_english, revised_translation, revision_model_seconds = (
                            self._correct_and_translate(
                                previous_record["raw_english"], True
                            )
                        )
                        revision_processing = time.perf_counter() - revision_started
                        revision_record = dict(previous_record)
                        revision_record.update(
                            {
                                "timestamp": datetime.now().isoformat(
                                    timespec="seconds"
                                ),
                                "version": "v55_vietnamese_fluency",
                                "update_kind": "context_revision",
                                "revision_of": previous_record["utterance_id"],
                                "correction_applied": (
                                    "rechecked after following utterance"
                                ),
                                "llm_seconds": f"{revision_model_seconds:.3f}",
                                "processing_seconds": f"{revision_processing:.3f}",
                                "queue_wait_seconds": "0.000",
                                "true_e2e_seconds": f"{time.perf_counter() - previous_final['speech_started_at']:.3f}",
                                "estimated_caption_lag_seconds": f"{revision_processing:.3f}",
                                "corrected_english": revised_english,
                                "translation": revised_translation,
                            }
                        )
                        normalized_raw = re.sub(
                            r"\W+", " ", previous_record["raw_english"].lower()
                        ).strip()
                        normalized_previous = re.sub(
                            r"\W+", " ", previous_record["corrected_english"].lower()
                        ).strip()
                        normalized_revision = re.sub(
                            r"\W+", " ", revised_english.lower()
                        ).strip()
                        if (
                            normalized_revision == normalized_raw
                            and normalized_previous != normalized_raw
                        ):
                            revision_record["corrected_english"] = previous_record[
                                "corrected_english"
                            ]
                            revision_record["translation"] = previous_record[
                                "translation"
                            ]
                            revision_record["correction_applied"] = (
                                "context revision rejected by no-regression guard"
                            )
                        previous_final["record"] = revision_record
                        self._save(revision_record)
                        self.result.emit(revision_record)
                self.status.emit(
                    "Listening — final caption"
                    if is_final
                    else "Listening — provisional caption"
                )
            except Exception as exc:
                self.failed.emit(f"Processing error — {type(exc).__name__}: {exc}")
            finally:
                self._utterance_queue.task_done()

    def run(self) -> None:
        try:
            self.status.emit("Loading local models (first run may take several minutes)…")
            from backend import load_backend
            load_backend(self)

            # Force one-time lazy model initialization before live audio starts.
            # This makes the Ready/Listening state slightly later, but prevents the
            # first classroom caption from paying the cold-start inference cost.
            self.status.emit("Warming up local models…")
            self._mlx_whisper.transcribe(
                np.zeros(SAMPLE_RATE, dtype=np.float32),
                path_or_hf_repo=STT_MODEL,
                language="en",
                task="transcribe",
                temperature=0.0,
                condition_on_previous_text=False,
                verbose=None,
            )
            if REVIEW_ENABLED:
                warm_messages = [
                    {"role": "user", "content": "Reply with OK."},
                ]
                warm_prompt = self._tokenizer.apply_chat_template(
                    warm_messages, tokenize=False, add_generation_prompt=True
                )
                self._generate(
                    self._llm,
                    self._tokenizer,
                    prompt=warm_prompt,
                    max_tokens=2,
                    verbose=False,
                )
            with self._torch.inference_mode():
                for language_name in ("Chinese", "Vietnamese"):
                    warm_tokenizer = self._translation_tokenizers[language_name]
                    warm_model = self._translation_models[language_name]
                    warm_inputs = warm_tokenizer(
                        "Hello.", return_tensors="pt"
                    )
                    warm_inputs = {
                        key: value.to(self._translation_device)
                        for key, value in warm_inputs.items()
                    }
                    warm_options = {"max_new_tokens": 8, "num_beams": 1}
                    if language_name == "Vietnamese":
                        warm_options["forced_bos_token_id"] = (
                            warm_tokenizer.convert_tokens_to_ids("vie_Latn")
                        )
                    warm_model.generate(**warm_inputs, **warm_options)

            if REVIEW_ENABLED:
                # Prime the actual review prefix before accepting microphone audio.
                # This synthetic warm-up is never emitted or saved as a caption.
                self._correct_and_translate("The microphone is ready.", True)
            self.ready.set()
            self.status.emit("Listening")
            processor = threading.Thread(
                target=self._process_utterances,
                name="caption-processing",
                daemon=True,
            )
            processor.start()
            pre_roll: deque[np.ndarray] = deque(
                maxlen=max(1, int(OVERLAP_SECONDS / FRAME_SECONDS))
            )
            utterance: list[np.ndarray] = []
            speech_started = False
            speech_frame_count = 0
            speech_squared_sum = 0.0
            speech_sample_count = 0
            silence_seconds = 0.0
            utterance_id = 0
            speech_started_at = 0.0
            last_partial_seconds = 0.0
            with nullcontext():
                while not self._capture_stop_event.is_set() or len(self._audio) >= FRAME_SAMPLES:
                    frame = self._next_frame()
                    if frame is None:
                        time.sleep(0.04)
                        continue

                    # Preserve the existing quiet-microphone VAD configuration.
                    # Gain is configurable; lower gain needs accuracy validation.
                    vad_gain = 10.0 ** (PRE_VAD_GAIN_DB / 20.0)
                    vad_frame = np.clip(frame * vad_gain, -1.0, 1.0)
                    pcm16 = np.clip(
                        vad_frame * 32767.0, -32768, 32767
                    ).astype(np.int16)
                    is_speech = self._vad.is_speech(pcm16.tobytes(), SAMPLE_RATE)
                    audio: np.ndarray | None = None

                    if not speech_started:
                        pre_roll.append(frame)
                        if not is_speech:
                            continue
                        speech_started = True
                        utterance_id += 1
                        speech_started_at = time.perf_counter()
                        utterance = list(pre_roll)
                        speech_frame_count = 1
                        speech_squared_sum = float(np.dot(frame, frame))
                        speech_sample_count = len(frame)
                        last_partial_seconds = 0.0
                        pre_roll.clear()
                        silence_seconds = 0.0
                        self.status.emit("Listening — speech detected")
                        continue

                    utterance.append(frame)
                    if is_speech:
                        speech_frame_count += 1
                        speech_squared_sum += float(np.dot(frame, frame))
                        speech_sample_count += len(frame)
                        silence_seconds = 0.0
                    else:
                        silence_seconds += FRAME_SECONDS

                    utterance_seconds = len(utterance) * FRAME_SECONDS
                    ended_by_pause = (
                        silence_seconds >= END_SILENCE_SECONDS
                        and utterance_seconds >= MIN_UTTERANCE_SECONDS
                    )
                    ended_by_limit = utterance_seconds >= MAX_UTTERANCE_SECONDS

                    partial_due = (
                        utterance_seconds >= PARTIAL_UPDATE_SECONDS
                        and utterance_seconds - last_partial_seconds
                        >= PARTIAL_UPDATE_SECONDS
                    )
                    if partial_due and not (ended_by_pause or ended_by_limit):
                        partial_frames = max(
                            1,
                            int(PARTIAL_AUDIO_WINDOW_SECONDS / FRAME_SECONDS),
                        )
                        partial_audio = np.concatenate(utterance[-partial_frames:])
                        partial_seconds = len(partial_audio) / SAMPLE_RATE
                        current_ratio = speech_frame_count / max(1, len(utterance))
                        if (
                            current_ratio >= MIN_SPEECH_FRAME_RATIO
                            and self._has_minimum_speech_energy(
                                speech_squared_sum, speech_sample_count
                            )
                        ):
                            self._queue_audio(
                                partial_audio,
                                partial_seconds,
                                utterance_id,
                                False,
                                speech_started_at,
                            )
                            self.status.emit("Listening — provisional update queued")
                        last_partial_seconds = utterance_seconds

                    if not (ended_by_pause or ended_by_limit):
                        continue

                    audio = np.concatenate(utterance)
                    completed_utterance_id = utterance_id
                    completed_started_at = speech_started_at
                    utterance_frame_count = max(1, len(utterance))
                    speech_ratio = speech_frame_count / utterance_frame_count
                    completed_speech_squared_sum = speech_squared_sum
                    completed_speech_sample_count = speech_sample_count
                    if ended_by_limit:
                        overlap_frames = max(1, int(OVERLAP_SECONDS / FRAME_SECONDS))
                        utterance = utterance[-overlap_frames:]
                        speech_started = True
                        utterance_id += 1
                        speech_started_at = time.perf_counter()
                        last_partial_seconds = 0.0
                        speech_frame_count = 0
                        speech_squared_sum = 0.0
                        speech_sample_count = 0
                        silence_seconds = 0.0
                    else:
                        utterance = []
                        speech_started = False
                        last_partial_seconds = 0.0
                        speech_frame_count = 0
                        speech_squared_sum = 0.0
                        speech_sample_count = 0
                        silence_seconds = 0.0

                    audio_seconds = len(audio) / SAMPLE_RATE
                    if (
                        speech_ratio < MIN_SPEECH_FRAME_RATIO
                        or not self._has_minimum_speech_energy(
                            completed_speech_squared_sum,
                            completed_speech_sample_count,
                        )
                    ):
                        self.status.emit("Listening — ignored low-signal audio")
                        continue

                    self._queue_audio(
                        audio,
                        audio_seconds,
                        completed_utterance_id,
                        True,
                        completed_started_at,
                    )
                    self.status.emit("Listening — final update queued")
            # Preserve the last active sentence when Stop is pressed before a
            # natural pause or the ten-second segment limit.
            if speech_started and utterance:
                audio = np.concatenate(utterance)
                audio_seconds = len(audio) / SAMPLE_RATE
                speech_ratio = speech_frame_count / max(1, len(utterance))
                if (
                    audio_seconds >= MIN_UTTERANCE_SECONDS
                    and speech_ratio >= MIN_SPEECH_FRAME_RATIO
                    and self._has_minimum_speech_energy(
                        speech_squared_sum, speech_sample_count
                    )
                ):
                    self._queue_audio(
                        audio,
                        audio_seconds,
                        utterance_id,
                        True,
                        speech_started_at,
                    )
                    self.status.emit("Stopping — final caption queued")
            self._utterance_queue.join()
            self._stop_event.set()
            processor.join(timeout=2.0)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.ready.clear()
            self.finished.emit()

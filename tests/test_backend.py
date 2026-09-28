import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from backend import TranslationAdapter

class Tokenizer:
    tokens = {0:'<pad>',1:'hello',2:'</s>',3:'vie_Latn',4:'translated'}
    def convert_ids_to_tokens(self, ids):
        return [self.tokens[x] for x in ids] if isinstance(ids,list) else self.tokens[ids]
    def convert_tokens_to_ids(self, tokens):
        return [{v:k for k,v in self.tokens.items()}[t] for t in tokens]

class Engine:
    def translate_batch(self, sources, **options):
        self.sources, self.options = sources, options
        return [type('Result',(),{'hypotheses':[['vie_Latn','translated','</s>']]})() for _ in sources]

class AdapterTests(unittest.TestCase):
    def test_low_raw_energy_is_rejected_after_vad_amplification(self):
        from pipeline import PipelineWorker
        self.assertFalse(PipelineWorker._has_minimum_speech_energy(1e-8, 480))
        # A normal -30 dBFS voice frame remains eligible.
        self.assertTrue(PipelineWorker._has_minimum_speech_energy(0.001 * 480, 480))

    def test_clock_context_preserves_times_and_other_numbers(self):
        from clock_text import normalize_clock_text as norm
        for source, expected in [
            ('The meeting starts at three fifteen, not three fifty.', 'The meeting starts at 3:15, not 3:50.'),
            ('The class ends at nine oh five, not nine forty-five.', 'The class ends at 9:05, not 9:45.'),
            ('The lecture begins at 12.40, not 12.14.', 'The lecture begins at 12:40, not 12:14.')]:
            self.assertEqual(norm(source), expected)
        for source in ['The price is 3.15, not 3.50.', 'The value is 28.5%.', 'The class ends at 25.75.', 'The meeting starts at 3.150 dollars.']:
            self.assertEqual(norm(source), source)

    def test_classroom_translation_preserves_critical_meaning(self):
        from classroom_translation import translate_classroom_sentence
        cases = [
            ('The report is due on Tuesday, not Thursday.', 'Chinese', '报告截止日期是星期二，不是星期四。'),
            ('Please select option C, not option A.', 'Vietnamese', 'Vui lòng chọn phương án C, không phải phương án A.'),
            ('Select option B, not option D.', 'Vietnamese', 'Vui lòng chọn phương án B, không phải phương án D.'),
            ('Please choose option D, not option B.', 'Chinese', '请选择选项D，不是选项B。'),
            ('The meeting starts at three fifteen, not three fifty.', 'Chinese', '会议在3:15开始，不是3:50。'),
            ('The quiz begins at eleven twenty, not eleven forty.', 'Chinese', '测验在11:20开始，不是11:40。'),
            ('The price is forty two dollars and fifty cents.', 'Vietnamese', 'Giá là 42 đô la và 50 xu.'),
            ('The temperature decreased from eighteen degrees to thirteen degrees.', 'Chinese', '温度从18度下降到13度。'),
        ]
        for source, language, expected in cases:
            self.assertEqual(translate_classroom_sentence(source, language), expected)
        self.assertIsNone(translate_classroom_sentence('The price is 28.5 percent.', 'Chinese'))

    def test_classroom_rules_can_be_combined_with_other_sentences(self):
        from classroom_translation import translate_classroom_sentence
        units = ['The report is due on Tuesday, not Thursday.', 'The value is 28.5%, not 25%.']
        translations = [translate_classroom_sentence(unit, 'Chinese') for unit in units]
        self.assertEqual(translations[0], '报告截止日期是星期二，不是星期四。')
        self.assertIsNone(translations[1])

    def test_empty_final_discards_even_fluent_provisional(self):
        import queue
        from unittest.mock import Mock
        from pipeline import PipelineWorker
        events = queue.Queue(); w = PipelineWorker('Chinese', events); w._save = Mock()
        w._last_provisional_records[3] = {'raw_english': 'Unsubstantiated fluent sentence.'}
        self.assertFalse(w._retain_last_provisional(3, 'no usable final speech'))
        self.assertEqual(events.get_nowait(), ('discarded', (3,)))
        w._save.assert_not_called()
        self.assertNotIn(3, w._last_provisional_records)

    def test_deadline_clarification_preserves_negation_and_date(self):
        from pipeline import PipelineWorker
        clarify = PipelineWorker._clarify_deadlines
        self.assertEqual(clarify('Our report is due on Tuesday.'), 'The deadline for Our report is Tuesday.')
        self.assertEqual(clarify('My essay is not due on Monday.'), 'The deadline for My essay is not Monday.')
        for text in ['The train is due on Monday.', 'The assignment is not yet due.', 'This is due to rain.']:
            self.assertEqual(clarify(text), text)

    def test_safe_review_change_allows_small_autocorrection_but_locks_critical_tokens(self):
        from pipeline import PipelineWorker
        self.assertTrue(PipelineWorker._safe_review_change(
            'The assignment is do on Friday.',
            'The assignment is due on Friday.'
        ))
        self.assertTrue(PipelineWorker._safe_review_change(
            'Please choose option B, not option D.',
            'Please choose option B, not option D.'
        ))
        self.assertFalse(PipelineWorker._safe_review_change(
            'Please choose option B, not option D.',
            'Please choose option A, not option D.'
        ))
        self.assertFalse(PipelineWorker._safe_review_change(
            'The value is 28.5 percent, not 25 percent.',
            'The value is 85 percent, not 25 percent.'
        ))

    def test_disabled_review_preserves_words_and_skips_generator(self):
        import queue
        from unittest.mock import Mock, patch
        from pipeline import PipelineWorker
        worker = PipelineWorker('Chinese', queue.Queue())
        worker._generate = Mock(side_effect=AssertionError('review should not run'))
        worker._translate_text = Mock(return_value='translation')
        with patch('pipeline.REVIEW_ENABLED', False):
            english, translation, elapsed = worker._correct_and_translate('Do not select A.', True)
        self.assertEqual(english, 'Do not select A.')
        self.assertEqual(translation, 'translation')
        worker._generate.assert_not_called()

    def test_missing_confidence_is_unknown_and_keeps_normal_speech(self):
        import queue
        from pipeline import PipelineWorker
        worker = PipelineWorker('Chinese', queue.Queue())
        self.assertFalse(worker._is_weak_stt_artifact('Select B.', None))
        self.assertFalse(worker._is_weak_stt_artifact('Select B.', None))
        self.assertTrue(worker._is_weak_stt_artifact('Select B.', -0.8))

    def test_parakeet_returns_text_without_invented_confidence(self):
        from backend import ParakeetAdapter
        from types import SimpleNamespace
        from unittest.mock import Mock
        stream = SimpleNamespace(result=SimpleNamespace(text=' Hello. '), accept_waveform=Mock())
        adapter = ParakeetAdapter.__new__(ParakeetAdapter)
        adapter.model = SimpleNamespace(create_stream=lambda: stream, decode_stream=Mock())
        samples = np.zeros(16000, dtype=np.float32)
        result = adapter.transcribe(samples, initial_prompt='must be ignored')
        self.assertEqual(result, {'text': 'Hello.', 'segments': []})
        stream.accept_waveform.assert_called_once_with(16000, samples)
        adapter.model.decode_stream.assert_called_once_with(stream)

    def test_digit_loop_rejected_but_normal_numbers_preserved(self):
        from pipeline import PipelineWorker
        self.assertTrue(PipelineWorker._looks_like_repetition('The value is 28.' + '8.' * 40))
        self.assertFalse(PipelineWorker._looks_like_repetition('The value is 28.5 percent, not 25 percent.'))

    def test_multiple_sentences_keep_options_separate(self):
        from pipeline import PipelineWorker
        sentences = ['The diamond is still on Friday.', 'The diamond is not still on Friday.', 'Select option B, not option B.']
        self.assertEqual(PipelineWorker._translation_units(' '.join(sentences)), sentences)
        self.assertEqual(PipelineWorker._translation_units('Dr. Nguyen is here. Select option D.'), ['Dr. Nguyen is here.', 'Select option D.'])
        self.assertEqual(PipelineWorker._translation_units('Select option B, not option D. The value is 28.5%.'), ['Select option B, not option D.', 'The value is 28.5%.'])

    def test_symbol_loops_rejected_and_valid_symbols_allowed(self):
        from pipeline import PipelineWorker
        for loop in ['%$' * 80, '8.' * 40, 'abc!?' * 12]:
            self.assertTrue(PipelineWorker._looks_like_repetition('The value is 20' + loop))
        for text in ['It costs $20, not $25.', 'The value is 28.5%, not 25%.', 'Select option B, not option D.']:
            self.assertFalse(PipelineWorker._looks_like_repetition(text))

    def test_corrupt_partial_cannot_be_retained_or_used_as_context(self):
        import queue
        from unittest.mock import Mock
        from pipeline import PipelineWorker
        events=queue.Queue(); w=PipelineWorker('Chinese',events); w._save=Mock()
        w._last_provisional_records[1]={'raw_english':'The value is 20'+'%$'*80}
        self.assertFalse(w._retain_last_provisional(1,'failed final'))
        w._save.assert_not_called()
        self.assertEqual(events.get_nowait(),('discarded',(1,)))
        self.assertEqual(w._recent_context(),'')

    def test_loop_never_reaches_translation_or_history(self):
        import queue, time
        from types import SimpleNamespace
        from unittest.mock import Mock
        from pipeline import PipelineWorker
        for text in ['The value is 20' + '%$'*80, 'The value is 28.' + '8.'*40]:
            for final in (False, True):
                events=queue.Queue(); w=PipelineWorker('Chinese',events)
                w._mlx_whisper=SimpleNamespace(transcribe=lambda *a, **k: {'text':text,'segments':[]})
                w._save=Mock();w._correct_and_translate=Mock()
                w._utterance_queue.put((np.zeros(16000,dtype=np.float32),time.perf_counter(),1.,1,final,time.perf_counter()))
                w._stop_event.set();w._process_utterances()
                w._correct_and_translate.assert_not_called();w._save.assert_not_called()
                self.assertFalse(any(name in ('result','raw_english') for name,payload in list(events.queue)))

    def test_noise_rejected_despite_fluent_transcript(self):
        from backend import WhisperAdapter
        from types import SimpleNamespace
        noise = SimpleNamespace(text='Invented URL', no_speech_prob=0.81, avg_logprob=-0.87)
        speech = SimpleNamespace(text='Actual speech', no_speech_prob=0.1, avg_logprob=-0.2)
        model = SimpleNamespace(transcribe=lambda *a, **k: (iter([noise, speech]), None))
        self.assertEqual(WhisperAdapter(model).transcribe(np.zeros(16000))['text'], 'Actual speech')

    def test_short_caption_keeps_titles_and_decimals_together(self):
        from pipeline import PipelineWorker
        caption = 'Dr. Nguyen measured 28.5 percent at 3:15 p.m.'
        self.assertEqual(PipelineWorker._translation_units(caption), [caption])

    def test_padding_and_target_language_preserved(self):
        adapter = TranslationAdapter.__new__(TranslationAdapter)
        adapter.tokenizer, adapter.language, adapter.engine = Tokenizer(), 'Vietnamese', Engine()
        result = adapter.generate(np.array([[1,2,0],[1,1,2]]),
            attention_mask=np.array([[1,1,0],[1,1,1]]),forced_bos_token_id=3,max_new_tokens=80)
        self.assertEqual(adapter.engine.sources,[['hello','</s>'],['hello','hello','</s>']])
        self.assertEqual(adapter.engine.options['target_prefix'],[['vie_Latn'],['vie_Latn']])
        self.assertEqual(adapter.engine.options['max_decoding_length'],80)
        self.assertEqual(result,[[3,4,2],[3,4,2]])

if __name__=='__main__': unittest.main()

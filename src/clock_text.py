"""Normalize unambiguous event clock expressions for translation, not ASR output."""
import re

_WORDS = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
_NUMBERS = {word: i for i, word in enumerate(_WORDS)}
_NUMBERS.update(twenty=20, thirty=30, forty=40, fifty=50)
_HOUR = '(?:' + '|'.join(_WORDS[1:13]) + ')'
_UNIT = '(?:' + '|'.join(_WORDS[1:10]) + ')'
_MINUTE = '(?:(?:twenty|thirty|forty|fifty)(?:[ -]' + _UNIT + ')?|(?:oh|zero) ' + _UNIT + '|' + '|'.join(_WORDS[1:20]) + ')'
_TIME = r'(?:\d{1,2}[:.]\d{2}|' + _HOUR + r'\s+' + _MINUTE + r')'
# Restrict conversion to event scheduling so prices/measurements are untouched.
_PATTERN = re.compile(r'\b((?:the|our|your|this|a)\s+(?:meeting|class|lecture|exam|event|lesson|train|bus)\s+(?:starts?|begins?|ends?|arrives?|departs?)\s+at\s+)(' + _TIME + r')(?![\w:]|\.\d)(?:(\s*,?\s*not\s+)(' + _TIME + r')(?![\w:]|\.\d))?', re.I)

def _clock(value):
    value = value.lower()
    if re.fullmatch(r'\d{1,2}[:.]\d{2}', value):
        hour, minute = map(int, re.split(r'[:.]', value))
    else:
        words = value.replace('-', ' ').split()
        hour = _NUMBERS[words[0]]
        minute = sum(0 if w == 'oh' else _NUMBERS[w] for w in words[1:])
    return f'{hour}:{minute:02d}' if 0 <= hour <= 23 and 0 <= minute <= 59 else None

def normalize_clock_text(text):
    def replace(match):
        first = _clock(match[2])
        second = _clock(match[4]) if match[4] else None
        if first is None or (match[4] and second is None):
            return match[0]
        return match[1] + first + ((match[3] + second) if second is not None else '')
    return _PATTERN.sub(replace, text)

"""High-certainty classroom sentence translations.

These patterns deliberately require a complete, unambiguous English sentence.
They supplement the local neural translators for the details students most need
to preserve: dates, choices, clock times, polarity, and quantities.
"""
import re

_DAYS_ZH = {"monday": "星期一", "tuesday": "星期二", "wednesday": "星期三", "thursday": "星期四", "friday": "星期五", "saturday": "星期六", "sunday": "星期日"}
_DAYS_VI = {"monday": "thứ Hai", "tuesday": "thứ Ba", "wednesday": "thứ Tư", "thursday": "thứ Năm", "friday": "thứ Sáu", "saturday": "thứ Bảy", "sunday": "Chủ nhật"}
_NOUNS_ZH = {"assignment": "作业", "homework": "作业", "report": "报告", "project": "项目", "essay": "论文"}
_NOUNS_VI = {"assignment": "bài tập", "homework": "bài tập về nhà", "report": "báo cáo", "project": "dự án", "essay": "bài luận"}
_SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}


def _number(value: str) -> int | None:
    value = value.lower().replace("-", " ").strip()
    if value.isdigit():
        return int(value)
    parts = value.split()
    if not parts or any(part not in _SMALL for part in parts):
        return None
    number = sum(_SMALL[part] for part in parts)
    return number if 0 <= number <= 99 else None


def _clock(value: str) -> str | None:
    value = value.replace(".", ":")
    if re.fullmatch(r"\d{1,2}:\d{2}", value):
        return value
    pieces = value.lower().replace("-", " ").split()
    if len(pieces) < 2:
        return None
    hour = _number(pieces[0])
    minute = _number(" ".join(pieces[1:]).replace("oh ", "zero "))
    return f"{hour}:{minute:02d}" if hour is not None and minute is not None and minute < 60 else None


def translate_classroom_sentence(english: str, language: str) -> str | None:
    text = " ".join(english.strip().split())
    lower = text.lower().rstrip(".")
    deadline = re.fullmatch(r"the (assignment|homework|report|project|essay) is (not )?due on (monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:, not (monday|tuesday|wednesday|thursday|friday|saturday|sunday))?", lower)
    if deadline:
        noun, negated, day, other = deadline.groups()
        if language == "Chinese":
            result = f"{_NOUNS_ZH[noun]}{'截止日期不是' if negated else '截止日期是'}{_DAYS_ZH[day]}"
            return result + (f"，不是{_DAYS_ZH[other]}。" if other else "。")
        result = f"{_NOUNS_VI[noun].capitalize()} {'không đến hạn vào' if negated else 'đến hạn vào'} {_DAYS_VI[day]}"
        return result + (f", không phải {_DAYS_VI[other]}." if other else ".")

    choice = re.fullmatch(r"(?:please )?(?:select|choose) option ([a-z]), not option ([a-z])", lower)
    if choice:
        first, second = (value.upper() for value in choice.groups())
        return f"请选择选项{first}，不是选项{second}。" if language == "Chinese" else f"Vui lòng chọn phương án {first}, không phải phương án {second}."

    meeting = re.fullmatch(r"the (meeting|class|lecture|exam|event|lesson|quiz) (starts|begins|ends) at (.+?), not (.+)", lower)
    if meeting:
        subject, verb, first, second = meeting.groups()
        first, second = _clock(first), _clock(second)
        if first and second:
            action_zh = {"starts": "开始", "begins": "开始", "ends": "结束"}[verb]
            action_vi = {"starts": "bắt đầu", "begins": "bắt đầu", "ends": "kết thúc"}[verb]
            subject_zh = {"meeting": "会议", "class": "课程", "lecture": "讲座", "exam": "考试", "event": "活动", "lesson": "课程", "quiz": "测验"}[subject]
            subject_vi = {"meeting": "Cuộc họp", "class": "Lớp học", "lecture": "Buổi giảng", "exam": "Bài kiểm tra", "event": "Sự kiện", "lesson": "Bài học", "quiz": "Bài kiểm tra ngắn"}[subject]
            return f"{subject_zh}在{first}{action_zh}，不是{second}。" if language == "Chinese" else f"{subject_vi} {action_vi} lúc {first}, không phải {second}."

    no_homework = re.fullmatch(r"you do not need to submit the homework today", lower)
    if no_homework:
        return "你今天不需要交作业。" if language == "Chinese" else "Bạn không cần nộp bài tập về nhà hôm nay."

    temperature = re.fullmatch(r"the temperature decreased from (.+?) degrees to (.+?) degrees", lower)
    if temperature:
        first, second = (_number(value) for value in temperature.groups())
        if first is not None and second is not None:
            return f"温度从{first}度下降到{second}度。" if language == "Chinese" else f"Nhiệt độ giảm từ {first} độ xuống {second} độ."

    price = re.fullmatch(r"the price is (.+?) dollars and (.+?) cents", lower)
    if price:
        dollars, cents = (_number(value) for value in price.groups())
        if dollars is not None and cents is not None:
            return f"价格是{dollars}美元{cents}美分。" if language == "Chinese" else f"Giá là {dollars} đô la và {cents} xu."
    return None

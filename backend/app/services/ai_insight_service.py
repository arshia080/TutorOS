"""AI performance insights (product spec section 20).

Database -> analytics engine -> structured student profile -> AI -> natural
language insight. The AI provider only ever sees the small structured profile
dict below -- never raw DB rows -- and its response is checked for invented
numeric claims before being shown to anyone.
"""

import re

from app.ai.base import AIProvider, AIProviderError
from app.services.analytics_service import TopicPerformance

NUMBER_PATTERN = re.compile(r"\d+\.?\d*")
NUMBER_TOLERANCE = 1.0
MAX_REGENERATION_ATTEMPTS = 2


def build_topic_profile(perf: TopicPerformance, student_name: str) -> dict:
    return {
        "student": student_name,
        "topic": perf.topic_name,
        "mastery": perf.mastery_score,
        "recent_accuracy": perf.recent_accuracy,
        "historical_accuracy": perf.historical_accuracy,
        "trend": perf.trend.value,
        "questions_attempted": perf.questions_attempted,
    }


def _allowed_numbers(profile: dict) -> set[float]:
    numbers = {float(v) for v in profile.values() if isinstance(v, (int, float))}
    # Trivial/structural numbers that show up in any percentage-based writing
    # regardless of the input (e.g. "out of 100%") aren't a fabricated claim.
    numbers |= {0.0, 100.0}
    return numbers


def _numbers_in(text: str) -> list[float]:
    return [float(m) for m in NUMBER_PATTERN.findall(text)]


def validate_no_invented_numbers(text: str, profile: dict) -> bool:
    allowed = _allowed_numbers(profile)
    for n in _numbers_in(text):
        if not any(abs(n - a) <= NUMBER_TOLERANCE or abs(round(n) - round(a)) <= NUMBER_TOLERANCE for a in allowed):
            return False
    return True


def _build_prompt(profile: dict, retry: bool) -> str:
    base = (
        "You are helping a teacher understand one student's performance on one topic. "
        "Here is the ONLY data you know about this student -- a structured profile computed "
        "by the school's analytics system:\n\n"
        f"{profile}\n\n"
        "Write a 2-3 sentence explanation of what these numbers mean for the teacher. "
        "Use ONLY the numbers given above -- do not calculate, estimate, round to a different "
        "value, or invent any other statistic (no percentages, counts, or comparisons that "
        "aren't already in the data). Do not claim attendance affects performance -- you were "
        "not given attendance data."
    )
    if retry:
        base += (
            "\n\nYour previous answer included a number that was not in the data above. "
            "Rewrite it using only the exact numbers given."
        )
    return base


def generate_topic_insight(provider: AIProvider, perf: TopicPerformance, student_name: str) -> str:
    profile = build_topic_profile(perf, student_name)

    for attempt in range(MAX_REGENERATION_ATTEMPTS):
        text = provider.generate_text(_build_prompt(profile, retry=attempt > 0))
        if validate_no_invented_numbers(text, profile):
            return text

    raise AIProviderError(
        "The AI's explanation included numbers not present in the underlying data twice in a "
        "row and was withheld rather than shown with potentially fabricated statistics."
    )

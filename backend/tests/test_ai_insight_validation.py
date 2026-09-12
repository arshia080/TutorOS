from app.services.ai_insight_service import build_topic_profile, validate_no_invented_numbers
from app.services.analytics_service import TopicPerformance
from app.models.analytics import TrendDirection


def _perf(**overrides) -> TopicPerformance:
    defaults = dict(
        topic_id="00000000-0000-0000-0000-000000000000",
        topic_name="Trigonometry",
        questions_attempted=12,
        accuracy=57.5,
        recent_accuracy=63.33,
        historical_accuracy=40.0,
        difficulty_adjusted_accuracy=57.5,
        consistency_score=70.42,
        mastery_score=55.88,
        mastery_category="Needs Improvement",
        trend=TrendDirection.IMPROVING,
    )
    defaults.update(overrides)
    return TopicPerformance(**defaults)


def test_grounded_text_passes():
    perf = _perf()
    profile = build_topic_profile(perf, "Rahul")
    text = (
        "Rahul's mastery in Trigonometry is 55.88%, which is Needs Improvement. "
        "His recent accuracy of 63.33% is well above his historical accuracy of 40.0%, "
        "consistent with the improving trend across 12 attempted questions."
    )
    assert validate_no_invented_numbers(text, profile) is True


def test_fabricated_number_rejected():
    perf = _perf()
    profile = build_topic_profile(perf, "Rahul")
    text = "Rahul has improved by 25% over the last 10 tests, a huge leap forward."
    # 25 and 10 are not present in (or close to) the profile's numbers.
    assert validate_no_invented_numbers(text, profile) is False


def test_rounded_number_within_tolerance_passes():
    perf = _perf()
    profile = build_topic_profile(perf, "Rahul")
    # The model rounds 63.33 -> 63 and 55.88 -> 56; both should be tolerated.
    text = "Rahul's recent accuracy is around 63% and his overall mastery is about 56%."
    assert validate_no_invented_numbers(text, profile) is True


def test_structural_numbers_always_allowed():
    perf = _perf()
    profile = build_topic_profile(perf, "Rahul")
    text = "Rahul is at 0% in some sub-areas but capped at 100% elsewhere, averaging around his mastery score."
    assert validate_no_invented_numbers(text, profile) is True


def test_questions_attempted_count_is_grounded():
    perf = _perf(questions_attempted=37)
    profile = build_topic_profile(perf, "Rahul")
    text = "Across 37 attempted questions, Rahul shows steady improvement."
    assert validate_no_invented_numbers(text, profile) is True
    text_wrong = "Across 50 attempted questions, Rahul shows steady improvement."
    assert validate_no_invented_numbers(text_wrong, profile) is False

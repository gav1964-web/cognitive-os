from runtime.token_aware_matcher import match_marker, marker_matches


def test_matches_ordered_russian_inflections_with_bounded_gap():
    result = match_marker(
        "Напиши программу, которая сложит значения второй колонки CSV.",
        "сложить вторую колонку csv",
    )

    assert result.matched is True
    assert result.strategy == "ordered_token_inflection"


def test_matches_changed_verb_ending():
    assert marker_matches(
        "Напиши CLI, которая форматирует JSON красиво.",
        "форматировать json",
    )


def test_rejects_reordered_or_distant_tokens():
    assert not marker_matches("Вторую CSV колонку не складывай.", "сложить вторую колонку csv")
    assert not marker_matches(
        "Сложить все полученные из внешнего сервиса значения второй колонки CSV.",
        "сложить вторую колонку csv",
    )


def test_single_token_fuzzy_match_is_not_allowed():
    assert not marker_matches("отсортирует", "сортировать")

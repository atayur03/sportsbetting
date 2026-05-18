from execution.run import normalize_strategy_name


def test_normalize_strategy_name_leaves_explicit_choice_unchanged_without_flag():
    assert normalize_strategy_name("underdog") == "underdog"
    assert normalize_strategy_name("inverted_underdog") == "inverted_underdog"


def test_normalize_strategy_name_toggles_inversion_with_flag():
    assert normalize_strategy_name("underdog", inverted=True) == "inverted_underdog"
    assert normalize_strategy_name("inverted_underdog", inverted=True) == "underdog"

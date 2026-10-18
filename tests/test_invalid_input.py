"""Host strings with lone surrogates reach the engine as replacement characters."""

import carve


def test_lone_surrogate_is_replaced_once_across_render_targets():
    source = "A\ud800B"
    for target in (carve.to_html, carve.to_markdown, carve.to_plain_text, carve.to_carve):
        result = target(source)
        assert "A\ufffdB" in result
        assert result.count("\ufffd") == 1


def test_valid_astral_character_is_preserved():
    assert "A\U0001f680B" in carve.to_html("A\U0001f680B")
    assert "A\U0001f680B" in carve.to_html("A\ud83d\ude80B")

import carve
import pytest


def test_lowercase_heading_ids_is_opt_in():
    assert 'id="Mixed-Case"' in carve.to_html("# Mixed Case")
    assert 'id="mixed-case"' in carve.to_html("# Mixed Case", lowercase_heading_ids=True)


def test_positions_stay_on_for_the_ast_entry_points():
    """`parse` has always returned spans, and adding the keyword must not
    change that. Falling back to the ENGINE default here would strip `pos`
    from every existing caller's tree - a change that looks like a default
    and behaves like a removal."""
    assert "pos" in carve.parse("hello")["children"][0]
    assert "pos" not in carve.parse("hello", positions=False)["children"][0]


def test_positions_is_opt_in_for_html():
    """HTML rendering is the other way round: the engine's default governs,
    because nothing here ever forced it."""
    assert "data-pos" not in carve.to_html("hello")


def test_mention_url_reaches_renderer():
    assert 'href="https://example.com/{}"' in carve.to_html(
        "Hello @alice", mention_url="https://example.com/{}"
    )


def test_unknown_keyword_is_rejected_by_python():
    with pytest.raises(TypeError):
        carve.to_html("hello", lowercase_heading_id=True)

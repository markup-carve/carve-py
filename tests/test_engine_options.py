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


# --- The non-HTML targets take the engine options too (#53) -----------------
#
# `to_markdown`, `to_plain_text` and `to_ansi` hardcoded `EngineOptions::default()`
# until this landed, so nothing above reached them. Two headings differing only
# in case is what makes `lowercase_heading_ids` visible in a target that emits
# no ids of its own: lowercasing collides them, the second heading is
# deduplicated to a different id, and every `</#foo>` crossref in the document
# resolves to the FIRST heading instead of the second.
COLLIDING_HEADINGS = "# Foo\n\n## FOO\n\nSee </#foo> and </#FOO>.\n"

NON_HTML_TARGETS = [carve.to_markdown, carve.to_plain_text, carve.to_ansi]


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_lowercase_heading_ids_reaches_the_non_html_targets(render):
    default = render(COLLIDING_HEADINGS)
    lowercased = render(COLLIDING_HEADINGS, lowercase_heading_ids=True)
    assert default != lowercased
    # The crossrefs resolve to the second heading by default and to the first
    # once the ids are lowercased, so the rendered link text changes with them.
    assert "FOO" in default
    assert default.count("FOO") > lowercased.count("FOO")


def test_lowercase_heading_ids_reaches_the_markdown_id_attribute():
    """Markdown is the one non-HTML target that writes the id out, so it can
    assert the id itself rather than the crossref text it resolves."""
    # Markdown writes the id only where something references it, so the
    # document has to carry the crossref that makes the anchor load-bearing.
    referenced = "# Mixed Case\n\nSee </#mixed-case> here.\n"
    assert "{#Mixed-Case}" in carve.to_markdown(referenced)
    assert "{#mixed-case}" in carve.to_markdown(
        referenced, lowercase_heading_ids=True
    )


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_an_engine_option_is_not_swallowed_by_the_fast_path(render):
    """The fast path returns the engine's no-options entry point. Before the
    guard learned about engine options it was taken whenever there were no
    extensions and no profile - which accepted `lowercase_heading_ids` and
    silently ignored it. This is the case that has NO extensions and NO profile,
    so it is the one the shortcut would have eaten."""
    assert render(COLLIDING_HEADINGS, lowercase_heading_ids=True) != render(
        COLLIDING_HEADINGS
    )


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_the_default_path_is_unchanged(render):
    """An omitted keyword keeps exactly what the function did before, on the
    fast path and on the `render` path alike."""
    assert render(COLLIDING_HEADINGS) == render(
        COLLIDING_HEADINGS,
        lowercase_heading_ids=None,
        positions=None,
        sections=None,
        source_lines=None,
        mention_url=None,
        tag_url=None,
        profile_base_host=None,
    )


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_engine_options_are_keyword_only_on_the_non_html_targets(render):
    """Positionally they would collide with `extensions` and `profile`, which
    are the two positional parameters these three have always taken."""
    with pytest.raises(TypeError):
        render("hello", None, None, True)


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_an_unknown_keyword_is_rejected_on_the_non_html_targets(render):
    with pytest.raises(TypeError):
        render("hello", lowercase_heading_id=True)

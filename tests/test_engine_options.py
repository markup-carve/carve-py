import carve
import pytest


def test_lowercase_heading_ids_is_opt_in():
    assert 'id="Mixed-Case"' in carve.to_html("# Mixed Case")
    # C2-H-131 and C2-H-137: headingIds names the 0.2 option.
    assert 'id="mixed-case"' in carve.to_html("# Mixed Case", {"headingIds": "lower"})


def test_positions_stay_on_for_the_ast_entry_points():
    """`parse` has always returned spans, and adding the keyword must not
    change that. Falling back to the ENGINE default here would strip `pos`
    from every existing caller's tree - a change that looks like a default
    and behaves like a removal."""
    # C2-T-005: the JSON boundary encloses the tree in a result record.
    assert "pos" in carve.parse("hello")["tree"]["children"][0]
    assert "pos" not in carve.parse("hello", positions=False)["tree"]["children"][0]


def test_positions_is_opt_in_for_html():
    """HTML rendering is the other way round: the engine's default governs,
    because nothing here ever forced it."""
    assert "data-pos" not in carve.to_html("hello")


def test_mention_url_reaches_renderer():
    # C2-H-126: social templates use the name placeholder.
    assert 'href="https://example.com/alice"' in carve.to_html(
        "Hello @alice", {"social": {"mentionUrl": "https://example.com/{name}"}}
    )


def test_unknown_keyword_is_rejected_by_python():
    with pytest.raises(TypeError):
        carve.to_html("hello", lowercase_heading_id=True)


# --- The 0.2 parse options and export entry ------------------------------
#
# Heading IDs are chosen during parse. The three export helpers use the tree
# writer, while parse options travel through the 0.2 parse call.
COLLIDING_HEADINGS = "# Foo\n\n## FOO\n\nSee </#foo> and </#FOO>.\n"

# The lower-case reference supplies a source that exposes the heading ID
# option in the parsed tree.
LOWERCASE_CROSSREF = "# Mixed Case\n\nSee </#mixed-case> here.\n"

NON_HTML_TARGETS = [carve.to_markdown, carve.to_plain_text, carve.to_ansi]


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_heading_id_option_reaches_parse_before_writer(render):
    default = carve.parse(LOWERCASE_CROSSREF)['tree']
    lowered = carve.parse(LOWERCASE_CROSSREF, {'headingIds': 'lower'})['tree']
    assert default['children'][0]['generatedId'] == 'Mixed-Case'
    assert lowered['children'][0]['generatedId'] == 'mixed-case'
    target = render.__name__[3:].replace('plain_text', 'plain')
    assert carve.write(lowered, target)['output'] == render(LOWERCASE_CROSSREF)


def test_markdown_writer_reaches_the_public_tree():
    source = '# Mixed Case\n\nSee </#Mixed-Case> here.\n'
    tree = carve.parse(source)['tree']
    assert tree['children'][0]['generatedId'] == 'Mixed-Case'
    assert carve.write(tree, 'markdown')['output'] == carve.to_markdown(source)
    assert '# Mixed Case' in carve.to_markdown(source)


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_writer_helpers_refuse_retired_heading_option(render):
    tree = carve.parse(COLLIDING_HEADINGS, {'headingIds': 'lower'})['tree']
    ids = [node['generatedId'] for node in tree['children'] if node['type'] == 'heading']
    assert ids == ['foo', 'foo-2']
    with pytest.raises(TypeError, match='lowercase_heading_ids'):
        render(COLLIDING_HEADINGS, lowercase_heading_ids=True)


@pytest.mark.parametrize("render", NON_HTML_TARGETS, ids=lambda f: f.__name__)
def test_the_default_path_is_unchanged(render):
    target = render.__name__[3:].replace('plain_text', 'plain')
    assert render(COLLIDING_HEADINGS) == carve.write(carve.parse(COLLIDING_HEADINGS)['tree'], target)['output']


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

import pytest

from corpus_population import EXAMPLE_PAGES, declared_corpus_size, require_whole_corpus


SOURCE = '````text\n::: compare\n```carve\nfake\n```\n```html\nfake\n```\n:::\n````\n::: compare no-render\n````carve\n::: compare\n```html\nliteral\n```\n:::\n````\n```html\n<p>first</p>\n```\n```carve\nsecond\n```\n```html\n<p>second</p>\n```\n:::\n'


def source_tree(tmp_path, source):
    examples = tmp_path / "resources" / "examples"
    examples.mkdir(parents=True)
    for page in EXAMPLE_PAGES:
        (examples / page).write_text(source if page == "core.md" else "", encoding="utf-8")
    return tmp_path / "tests" / "corpus"


def test_multiple_pairs_and_literal_fences(tmp_path):
    corpus = source_tree(tmp_path, SOURCE)
    assert declared_corpus_size(corpus) == 2
    require_whole_corpus(corpus, 2, "complete")
    with pytest.raises(AssertionError):
        require_whole_corpus(corpus, 1, "truncated")


@pytest.mark.parametrize("source", [
    "::: compare\n```carve\nx\n```\n:::\n",
    "::: compare\n```carve\nx\n```\n```html\nx\n```\n",
    "::: compare\n:::\n",
])
def test_invalid_source_is_refused(tmp_path, source):
    with pytest.raises(AssertionError):
        declared_corpus_size(source_tree(tmp_path, source))

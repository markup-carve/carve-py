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


THREE_PAIRS = """::: compare
```carve
one
```
```html
<p>one</p>
```
````carve
```carve
literal, not a pair
```
````
```html
<p>two</p>
```
```carve
three
```
```html
<p>three</p>
```
:::
"""


def test_one_block_holding_three_pairs(tmp_path):
    assert declared_corpus_size(source_tree(tmp_path, THREE_PAIRS)) == 3


@pytest.mark.parametrize("source", [
    "::: compare\n```carve\nx\n```\n:::\n",
    "::: compare\n```carve\nx\n```\n```html\nx\n```\n",
    "::: compare\n:::\n",
])
def test_invalid_source_is_refused(tmp_path, source):
    with pytest.raises(AssertionError):
        declared_corpus_size(source_tree(tmp_path, source))


def test_edge_case_sections_in_their_own_files(tmp_path):
    examples = tmp_path / "resources" / "examples"
    sections = examples / "edge-cases"
    sections.mkdir(parents=True)
    (examples / "core.md").write_text(THREE_PAIRS, encoding="utf-8")
    (examples / "extensions.md").write_text("", encoding="utf-8")
    (sections / "README.md").write_text(THREE_PAIRS, encoding="utf-8")
    (sections / "0002-second.md").write_text(SOURCE, encoding="utf-8")
    distinct = THREE_PAIRS.replace("one", "four").replace("literal", "fenced").replace("three", "six")
    (sections / "0001-first.md").write_text("---\npage: tables\n---\n\n" + distinct, encoding="utf-8")
    assert declared_corpus_size(tmp_path / "tests" / "corpus") == 8


def test_an_input_repeated_across_sections_counts_once(tmp_path):
    examples = tmp_path / "resources" / "examples"
    sections = examples / "edge-cases"
    sections.mkdir(parents=True)
    (examples / "core.md").write_text(THREE_PAIRS, encoding="utf-8")
    (examples / "extensions.md").write_text("", encoding="utf-8")
    (sections / "0001-first.md").write_text(THREE_PAIRS, encoding="utf-8")
    (sections / "0002-crlf.md").write_text(THREE_PAIRS.replace("::: compare", "::: compare crlf"), encoding="utf-8")
    assert declared_corpus_size(tmp_path / "tests" / "corpus") == 6


def test_an_empty_section_directory_is_refused(tmp_path):
    examples = tmp_path / "resources" / "examples"
    (examples / "edge-cases").mkdir(parents=True)
    (examples / "core.md").write_text(THREE_PAIRS, encoding="utf-8")
    (examples / "extensions.md").write_text("", encoding="utf-8")
    with pytest.raises(pytest.fail.Exception):
        declared_corpus_size(tmp_path / "tests" / "corpus")

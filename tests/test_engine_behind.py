"""engine-behind.txt reads what carve-rs declares, and writes back what it reads."""

import engine_behind

CORPUS_RS = '''
const AHEAD_OF_PIN: &[(&str, &str, &str)] = &[];

#[rustfmt::skip]
const BEHIND_ON_PAIR: &[(&str, &str, &str)] = &[
    (
        "1-a-pair",
        "carve#1: a \\"quoted\\" reason",
        r##"<p>a "b"</p>

<p>c</p>"##,
    ),
    // a comment between entries
    ("2-b", "carve#2", r#"<hr>"#),
];
'''


def test_reads_both_tables_and_keeps_inner_blank_lines():
    assert engine_behind.from_engine_source(CORPUS_RS) == {
        "1-a-pair": '<p>a "b"</p>\n\n<p>c</p>',
        "2-b": "<hr>",
    }


def test_write_then_load_round_trips(tmp_path):
    declared = engine_behind.from_engine_source(CORPUS_RS)
    path = tmp_path / "engine-behind.txt"
    engine_behind.write(declared, path)
    assert engine_behind.load(path) == declared


def test_the_committed_ledger_loads():
    for slug, html in engine_behind.load().items():
        assert slug and html, slug

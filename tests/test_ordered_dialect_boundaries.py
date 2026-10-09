import json
from pathlib import Path

import carve
import pytest


CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "ordered-dialect-boundaries.json").read_text(encoding="utf-8")
)
assert len(CASES) == 17


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_ordered_dialect_boundaries(case):
    source = case["source"]
    assert carve.to_html(source).rstrip("\n") == case["html"]
    assert carve.to_carve(source, strict=True) == source
    imported = carve.from_html(case["inputHtml"])
    assert imported["value"] == source
    assert imported["report"]["diagnostics"] == []
    assert carve.to_html(imported["value"]).rstrip("\n") == case["html"]


def test_article_retains_raw_payload_as_code():
    assert carve.to_html("``` =html\n<b>x</b>\n```", profile="article") == (
        '<pre><code class="language-html">&lt;b&gt;x&lt;/b&gt;\n</code></pre>'
    )


def test_markdown_retains_authored_ordered_delimiters():
    cases = json.loads(
        (Path(__file__).parent / "fixtures" / "markdown-ordered-delimiters.json").read_text(encoding="utf-8")
    )
    assert len(cases) == 3
    for case in cases:
        imported = carve.from_markdown(case["markdown"])
        assert imported["value"] == case["source"], case["name"]
        assert carve.to_html(imported["value"]).rstrip("\n") == case["html"], case["name"]
        assert imported["report"]["diagnostics"]
        assert all(row["fidelity"] == "preserved" for row in imported["report"]["diagnostics"])

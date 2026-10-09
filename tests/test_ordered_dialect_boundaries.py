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

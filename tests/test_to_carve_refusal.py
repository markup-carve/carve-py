import pytest

import carve

# One level past the parse cap the over-cap flattening hands the writer a code
# value whose first line ends in a space, which the block layer strips, so the
# writer cannot spell the tree back (carve-rs#2326).
REFUSED = "> " * 201 + "`code \n" + "> " * 201 + "more`\n"


def test_refusal_is_indistinguishable_from_canonical_by_default():
    assert carve.to_carve(REFUSED) == REFUSED


def test_strict_reports_the_refusal():
    with pytest.raises(ValueError) as excinfo:
        carve.to_carve(REFUSED, strict=True)
    assert "cannot spell" in str(excinfo.value)


def test_strict_returns_the_same_source_the_writer_accepts():
    source = "# Hi\n\n\nBody"
    assert carve.to_carve(source, strict=True) == carve.to_carve(source)

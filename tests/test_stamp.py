"""Reading the provenance marker `carve fmt --stamp` writes.

The marker format is the contract, not any one API, so the fixtures below are the
literal bytes carve-php, carve-js and carve-rs write. A divergence in any writer
fails here rather than in the field.
"""

import carve
import pytest

FROM_PHP = "# Hi\n\n%% carve-version: 0.1; generated-by: carve-php 0.1.0\n"
FROM_JS = "# Hi\n\n%% carve-version: 0.1; generated-by: carve-js 0.1.0\n"
BLOCK_FROM_RS = "# Hi\n\n%%%\ncarve-version: 0.1\ngenerated-by: carve-rs 0.1.1\n%%%\n"
OLD = "# Hi\n\n%% carve-version: 0.0.9; generated-by: x\n"


@pytest.mark.parametrize(
    ("source", "writer"),
    [(FROM_PHP, "carve-php 0.1.0"), (FROM_JS, "carve-js 0.1.0"), (BLOCK_FROM_RS, "carve-rs 0.1.1")],
)
def test_read_stamp_reads_every_engines_marker(source, writer):
    assert carve.read_stamp(source) == {"version": "0.1", "generated_by": writer}


def test_read_stamp_returns_none_for_an_unstamped_document():
    assert carve.read_stamp("# Hi\n\nNo marker.\n") is None


def test_read_stamp_does_not_mistake_a_trailing_comment_for_a_marker():
    """Keeps "no marker" from quietly meaning "parsing gave up"."""
    assert carve.read_stamp("# Hi\n\n%% just a note\n") is None


def test_read_stamp_reports_an_unrecorded_writer_as_none():
    assert carve.read_stamp("# Hi\n\n%% carve-version: 0.1\n") == {
        "version": "0.1",
        "generated_by": None,
    }


def test_needs_review_for_older_and_unstamped_documents():
    assert carve.needs_review(OLD) is True
    # Unknown provenance: assuming a document is current is the unsafe direction.
    assert carve.needs_review("# Hi\n") is True


def test_needs_review_is_false_for_a_current_document():
    assert carve.needs_review(FROM_PHP) is False


def test_needs_review_accepts_an_explicit_target_version():
    # Spec versions carry two segments and engine versions three, so a
    # segment-count comparison would call every stamped document stale.
    assert carve.needs_review(FROM_PHP, "0.1.0") is False
    # "0.10" sorts before "0.9" as text, but 10 > 9.
    assert carve.needs_review("a\n\n%% carve-version: 0.9; generated-by: x\n", "0.10") is True

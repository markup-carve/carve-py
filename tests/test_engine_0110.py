"""Engine 0.1.10 behavior exposed by the Python binding."""

import carve


def test_empty_destinations_remain_links_and_images():
    assert '<a href="">x</a>' in carve.to_html("[x]()")
    assert '<img src="" alt="alt">' in carve.to_html("![alt]()")
    assert carve.to_carve("[x]()") == "[x]()\n"


def test_csv_and_tsv_table_bodies_render_as_tables():
    for format, body in (("csv", "A,B\n1,2"), ("tsv", "A\tB\n1\t2")):
        source = "{table}\n```" + format + "\n" + body + "\n```"
        assert "<table>" in carve.to_html(source)
        assert carve.to_carve(source) == source + "\n"


def test_plain_text_list_continuation_keeps_its_content_column():
    source = "- first\n\n  continuation\n"
    assert carve.to_plain_text(source) == source

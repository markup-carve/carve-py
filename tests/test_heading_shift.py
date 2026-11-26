import carve
import pytest


def test_heading_shift_adds_to_every_heading_level():
    # carve#6325: headingShift is a core render option; ids keep the authored text.
    html = carve.render("= Chapter\n\n== Section\n", {"headingShift": 1})["html"]
    assert "<h2>Chapter</h2>" in html
    assert "<h3>Section</h3>" in html
    assert 'id="Chapter"' in html


def test_heading_shift_zero_is_the_default():
    source = "= Chapter\n"
    assert carve.render(source, {"headingShift": 0}) == carve.render(source)


def test_heading_shift_reaches_the_native_host_path():
    html = carve.render_with_host("= Chapter\n", {"headingShift": 2}, transforms=[lambda tree: tree])["html"]
    assert "<h3>Chapter</h3>" in html


@pytest.mark.parametrize("value", [-1, 6, 1.5, "1", True])
def test_heading_shift_outside_0_to_5_is_refused(value):
    with pytest.raises(Exception):
        carve.render("= Chapter\n", {"headingShift": value})


@pytest.mark.parametrize("value", [-1, 6, 1.5, "1"])
def test_heading_shift_outside_0_to_5_is_refused_on_the_host_path(value):
    with pytest.raises(Exception):
        carve.render_with_host("= Chapter\n", {"headingShift": value}, transforms=[lambda tree: tree])


def test_heading_level_shift_extension_is_gone():
    # carve#6325 replaces the carve.headingLevelShift extension with the core option.
    assert "carve.headingLevelShift" not in carve.extensions()
    with pytest.raises(carve.CarveError):
        carve.to_html("# Hi", extensions=["carve.headingLevelShift"])

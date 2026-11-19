"""Task states exposed by the 0.1.13 engine."""

import carve
import pytest

pytestmark = pytest.mark.skip(reason="C2-W-001 0.1 source writer pending in carve-rs issue 4327")


def test_task_states_render_and_preserve_markers():
    for marker in ("/", "!", "_"):
        source = f"- [{marker}] task\n"
        assert f'data-task-state="{marker}"' in carve.to_html(source)
        assert carve.to_carve(source) == source
